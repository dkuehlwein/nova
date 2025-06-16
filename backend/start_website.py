"""
Nova Backend Server

Provides REST API endpoints for the Nova frontend with kanban board functionality
and native LangChain tools for Nova agent integration.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.api_endpoints import router as api_router
from api.chat_endpoints import router as chat_router
from api.websocket_endpoints import router as websocket_router
from api.mcp_endpoints import router as mcp_router
from api.admin_endpoints import router as admin_router
from api.config_endpoints import router as config_router
from utils.service_manager import ServiceManager, create_prompt_updated_handler
from utils.logging import RequestLoggingMiddleware

# Load environment variables
load_dotenv()

# Global instances
service_manager = ServiceManager("chat-agent")


async def create_website_event_handler():
    """Create event handler for website service (WebSocket + chat agent reloading)."""
    from utils.websocket_manager import websocket_manager
    from api.chat_endpoints import clear_chat_agent_cache
    
    async def handle_event(event):
        # Always broadcast to WebSocket clients
        await websocket_manager.broadcast_event(event)
        
        # Handle agent reloading for prompt updates
        if event.type == "prompt_updated":
            try:
                service_manager.logger.info(
                    f"Prompt updated, reloading chat agent: {event.data.get('prompt_file')}",
                    extra={
                        "data": {
                            "event_id": event.id,
                            "prompt_file": event.data.get('prompt_file'),
                            "source": event.source
                        }
                    }
                )
                clear_chat_agent_cache()
                service_manager.logger.info("Chat agent cache cleared - will use updated prompt on next request")
            except Exception as e:
                service_manager.logger.error(f"Failed to reload chat agent: {e}")
    
    return handle_event


async def setup_postgresql_pool(app):
    """Setup PostgreSQL connection pool for chat checkpointer."""
    try:
        from config import settings
        
        if settings.FORCE_MEMORY_CHECKPOINTER:
            service_manager.logger.info("FORCE_MEMORY_CHECKPOINTER is enabled, using MemorySaver for chat checkpointer")
            app.state.pg_pool = None
            return
        
        if not settings.DATABASE_URL:
            service_manager.logger.info("No DATABASE_URL configured, chat will use MemorySaver")
            app.state.pg_pool = None
            return
        
        try:
            from psycopg_pool import AsyncConnectionPool
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }
            
            service_manager.logger.info("Setting up PostgreSQL connection pool for chat checkpointer...")
            pg_pool = AsyncConnectionPool(
                conninfo=settings.DATABASE_URL,
                max_size=20,
                kwargs=connection_kwargs,
                open=False
            )
            
            await pg_pool.open()
            
            # Setup checkpointer tables
            async with pg_pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                await checkpointer.setup()
                service_manager.logger.info("PostgreSQL checkpointer tables set up successfully")
            
            app.state.pg_pool = pg_pool
            service_manager.logger.info("PostgreSQL connection pool ready for chat checkpointer")
            
        except ImportError:
            service_manager.logger.warning("PostgreSQL checkpointer packages not available, chat will use MemorySaver")
            app.state.pg_pool = None
        except Exception as e:
            service_manager.logger.error(f"Failed to setup PostgreSQL connection pool: {e}")
            app.state.pg_pool = None
            
    except Exception as e:
        service_manager.logger.error(f"Error during PostgreSQL setup: {e}")
        app.state.pg_pool = None


async def cleanup_postgresql_pool(app):
    """Clean up PostgreSQL connection pool."""
    if hasattr(app.state, 'pg_pool') and app.state.pg_pool:
        try:
            await app.state.pg_pool.close()
            service_manager.logger.info("PostgreSQL connection pool closed")
        except Exception as e:
            service_manager.logger.error(f"Error closing PostgreSQL pool: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    service_manager.logger.info("Starting Nova Backend Server...")
    
    try:
        # Start prompt watching
        await service_manager.start_prompt_watching()
        
        # Setup PostgreSQL pool
        await setup_postgresql_pool(app)
        
        # Create event handler for WebSocket broadcasting and agent reloading
        event_handler = await create_website_event_handler()
        
        # Start Redis bridge
        await service_manager.start_redis_bridge(app, event_handler)
        
        service_manager.logger.info("Nova Backend Server started successfully")
        
    except Exception as e:
        service_manager.logger.error(f"Failed to start server: {e}")
        raise
    
    yield
    
    # Shutdown
    service_manager.logger.info("Shutting down Nova Backend Server...")
    
    # Stop services
    await service_manager.stop_prompt_watching()
    await service_manager.stop_redis_bridge(app)
    
    # Cleanup resources
    await service_manager.cleanup_redis()
    await cleanup_postgresql_pool(app)
    await service_manager.cleanup_database()
    
    service_manager.logger.info("Nova Backend Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Nova Backend API",
    description="Backend API for Nova kanban board with AI agent integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware, service_name="chat-agent")

# Include routers
app.include_router(api_router)
app.include_router(chat_router)
app.include_router(websocket_router)
app.include_router(mcp_router)
app.include_router(admin_router)
app.include_router(config_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "nova-backend",
        "version": "1.0.0",
        "description": "Nova Backend API - Kanban board with AI agent integration",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        from database.database import db_manager
        from sqlalchemy import text
        
        # Test database connection
        async with db_manager.get_session() as session:
            await session.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "service": "nova-backend",
            "version": "1.0.0",
            "database": "connected",
            "chat_checkpointer": "postgresql" if hasattr(app.state, 'pg_pool') and app.state.pg_pool else "memory"
        }
    except Exception as e:
        service_manager.logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "service": "nova-backend", 
            "version": "1.0.0",
            "database": "error",
            "error": str(e)
        }


async def main():
    """Run the backend server."""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None  # Use our custom logging
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main()) 