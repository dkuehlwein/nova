"""
Service Manager Utilities

Common utilities for managing Nova services including startup, shutdown,
Redis event handling, and PostgreSQL connection pool management.

ServiceManager provides centralized PostgreSQL connection pool management
for Nova services following the "one shared pool per service" pattern:

- Each service (chat-agent, core-agent) gets its own ServiceManager instance
- Each ServiceManager owns a single PostgreSQL connection pool 
- Connection pools are properly opened during service startup and closed during shutdown
- Services share the pool across all their LangGraph checkpointers for efficiency
- PostgreSQL checkpointer is mandatory - no fallbacks to in-memory storage

This eliminates connection pool proliferation and "Event loop is closed" errors
while providing proper resource management and service isolation.
"""

import asyncio
import os
from typing import Optional, Callable, Any, Dict
from contextlib import asynccontextmanager

from utils.logging import configure_logging, get_logger


class ServiceManager:
    """Manages common service lifecycle operations."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = get_logger(f"{service_name}-startup")
        self.pg_pool: Optional[Any] = None  # AsyncConnectionPool instance
        
        # Reduce verbosity of third-party libraries
        import logging
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("mcp").setLevel(logging.WARNING)
        logging.getLogger("mcp.client").setLevel(logging.WARNING)
        logging.getLogger("mcp.client.streamable_http").setLevel(logging.WARNING)
    
    async def init_pg_pool(self):
        """Initialize PostgreSQL connection pool.
        
        Returns:
            The created pool instance
            
        Raises:
            ValueError: If DATABASE_URL is not configured
            RuntimeError: If PostgreSQL packages are not available or connection fails
        """
        try:
            from config import settings
            
            if not settings.DATABASE_URL:
                raise ValueError("DATABASE_URL is required - PostgreSQL checkpointer is mandatory")
            
            try:
                from psycopg_pool import AsyncConnectionPool
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                
                connection_kwargs = {
                    "autocommit": True,
                    "prepare_threshold": 0,
                }
                
                self.logger.info("Creating PostgreSQL connection pool", extra={
                    "data": {
                        "service": self.service_name,
                        "database_url_set": bool(settings.DATABASE_URL)
                    }
                })
                
                # Create pool with open=False to avoid deprecated constructor warning
                self.pg_pool = AsyncConnectionPool(
                    conninfo=settings.DATABASE_URL,
                    max_size=20,
                    kwargs=connection_kwargs,
                    open=False
                )
                
                # Open the pool
                await self.pg_pool.open()
                
                # Create temporary checkpointer to ensure tables are set up
                temp_saver = AsyncPostgresSaver(self.pg_pool)
                await temp_saver.setup()
                
                self.logger.info("PostgreSQL connection pool ready", extra={
                    "data": {
                        "service": self.service_name,
                        "pool_id": id(self.pg_pool),
                        "max_size": 20
                    }
                })
                
                return self.pg_pool
                
            except ImportError as e:
                self.logger.error("PostgreSQL checkpointer packages not available", extra={"data": {"error": str(e)}})
                raise RuntimeError(f"PostgreSQL checkpointer packages not available: {e}")
            except Exception as e:
                self.logger.error("Failed to create PostgreSQL connection pool", extra={
                    "data": {
                        "service": self.service_name,
                        "error": str(e)
                    }
                })
                raise RuntimeError(f"Failed to create PostgreSQL connection pool: {e}")
                
        except Exception as e:
            if isinstance(e, (ValueError, RuntimeError)):
                raise  # Re-raise ValueError and RuntimeError as-is
            self.logger.error("Error during PostgreSQL pool initialization", extra={
                "data": {
                    "service": self.service_name,
                    "error": str(e)
                }
            })
            raise RuntimeError(f"Error during PostgreSQL pool initialization: {e}")
    
    async def close_pg_pool(self):
        """Close PostgreSQL connection pool."""
        if self.pg_pool is not None:
            try:
                self.logger.info("Closing PostgreSQL connection pool", extra={
                    "data": {
                        "service": self.service_name,
                        "pool_id": id(self.pg_pool)
                    }
                })
                await self.pg_pool.close()
                self.pg_pool = None
                self.logger.info("PostgreSQL connection pool closed successfully")
            except Exception as e:
                self.logger.error("Error closing PostgreSQL pool", extra={
                    "data": {
                        "service": self.service_name,
                        "error": str(e)
                    }
                })
                # Set to None even on error to prevent retry attempts
                self.pg_pool = None
    

    
    async def start_redis_bridge(self, app, event_handler: Callable[[Any], Any]):
        """Start Redis event bridge with custom event handler.
        
        Args:
            app: FastAPI app instance to store the task
            event_handler: Async function to handle each Redis event
        """
        try:
            from utils.redis_manager import subscribe
            
            async def redis_bridge():
                """Background task to handle Redis events."""
                try:
                    async for event in subscribe():
                        await event_handler(event)
                except Exception as e:
                    self.logger.error("Redis bridge error", extra={"data": {"error": str(e)}})
            
            # Start the background task
            bridge_task = asyncio.create_task(redis_bridge())
            app.state.redis_bridge_task = bridge_task
            self.logger.info("Started Redis event bridge")
            
        except Exception as e:
            self.logger.error("Failed to start Redis event bridge", extra={"data": {"error": str(e)}})
            app.state.redis_bridge_task = None
    
    async def stop_redis_bridge(self, app):
        """Stop Redis event bridge."""
        if hasattr(app.state, 'redis_bridge_task') and app.state.redis_bridge_task:
            try:
                app.state.redis_bridge_task.cancel()
                await asyncio.wait_for(app.state.redis_bridge_task, timeout=5.0)
                self.logger.info("Stopped Redis event bridge")
            except asyncio.CancelledError:
                self.logger.info("Redis bridge task cancelled successfully")
            except asyncio.TimeoutError:
                self.logger.warning("Redis bridge task shutdown timed out")
            except Exception as e:
                self.logger.error("Error stopping Redis bridge task", extra={"data": {"error": str(e)}})
    
    async def cleanup_mcp(self):
        """Clean up MCP connections."""
        try:
            from mcp_client import mcp_manager
            await asyncio.wait_for(mcp_manager.cleanup(), timeout=3.0)
        except asyncio.TimeoutError:
            self.logger.warning("MCP client cleanup timed out")
        except Exception as e:
            self.logger.debug("MCP cleanup error", extra={"data": {"error": str(e)}})
    
    async def cleanup_database(self):
        """Clean up database connections."""
        try:
            from database.database import db_manager
            await asyncio.wait_for(db_manager.close(), timeout=5.0)
        except asyncio.TimeoutError:
            self.logger.warning("Database shutdown timed out")
    
    async def cleanup_redis(self):
        """Close Redis connections."""
        try:
            from utils.redis_manager import close_redis
            await close_redis()
            self.logger.info("Closed Redis connection")
        except Exception as e:
            self.logger.error("Error closing Redis connection", extra={"data": {"error": str(e)}})
    
    async def cleanup_memory(self):
        """Clean up memory/Graphiti connections."""
        try:
            from memory.graphiti_manager import close_graphiti_client
            await asyncio.wait_for(close_graphiti_client(), timeout=5.0)
            self.logger.info("Closed memory/Graphiti connection")
        except asyncio.TimeoutError:
            self.logger.warning("Memory cleanup timed out")
        except Exception as e:
            self.logger.debug("Memory cleanup error", extra={"data": {"error": str(e)}})
    
    async def ensure_database_initialized(self):
        """Ensure database is initialized by checking if core tables exist.
        
        If tables don't exist, runs the existing init_db.py initialization.
        """
        try:
            from database.database import db_manager
            from sqlalchemy import text
            
            self.logger.info("Checking database initialization status...")
            
            # Simple check - try to query tasks table
            try:
                async with db_manager.get_session() as session:
                    await session.execute(text("SELECT 1 FROM tasks LIMIT 1"))
                self.logger.info("Database already initialized")
                # Always sync schema to pick up new models (create_all is safe - uses checkfirst)
                await db_manager.create_tables()
                return

            except Exception:
                # Tables don't exist - run init_db
                self.logger.info("Database needs initialization, running init_db...")
                from init_db import init_database
                await init_database()
                self.logger.info("Database initialization completed")
                
        except Exception as e:
            self.logger.error("Database initialization failed", extra={"data": {"error": str(e)}})
            raise RuntimeError(f"Database initialization failed: {e}")


async def create_prompt_updated_handler(reload_callback: Callable[[], Any]):
    """Create a Redis event handler for prompt updates.
    
    Args:
        reload_callback: Async function to call when prompt is updated
        
    Returns:
        Event handler function
    """
    logger = get_logger("redis-events")
    
    async def handle_event(event):
        # Handle agent reloading for prompt updates
        if event.type == "prompt_updated":
            try:
                logger.info(
                    "Prompt updated, reloading agent",
                    extra={
                        "data": {
                            "event_id": event.id,
                            "prompt_file": event.data.get('prompt_file'),
                            "source": event.source
                        }
                    }
                )
                await reload_callback()
                logger.info("Agent reloaded with updated prompt")
            except Exception as e:
                logger.error("Failed to reload agent", extra={"data": {"error": str(e)}})
    
    return handle_event


def create_postgres_checkpointer(pg_pool):
    """Create a PostgreSQL checkpointer from a connection pool.
    
    Args:
        pg_pool: AsyncConnectionPool instance
        
    Returns:
        AsyncPostgresSaver instance
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    return AsyncPostgresSaver(pg_pool) 