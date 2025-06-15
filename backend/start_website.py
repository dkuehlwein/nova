"""
Nova Backend Server

Provides REST API endpoints for the Nova frontend.
This backend serves the kanban board functionality with PostgreSQL backend
and provides native LangChain tools for Nova agent integration.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.api_endpoints import router as api_router
from api.chat_endpoints import router as chat_router
from database.database import db_manager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Nova Backend Server...")
    
    # Note: Database tables are created automatically via SQLAlchemy
    # since we're using a persistent PostgreSQL instance.
    # Use init_db script for explicit table creation if needed.
    
    # Start prompt file watching for hot-reload
    try:
        from utils.prompt_loader import start_nova_prompt_watching
        start_nova_prompt_watching()
        logger.info("Started watching Nova system prompt file for changes")
    except Exception as e:
        logger.error(f"Failed to start prompt watching: {e}")
    
    # Initialize PostgreSQL connection pool for chat checkpointer
    pg_pool = None
    try:
        from config import settings
        
        # Check if we should force memory checkpointer
        if settings.FORCE_MEMORY_CHECKPOINTER:
            logger.info("FORCE_MEMORY_CHECKPOINTER is enabled, using MemorySaver for chat checkpointer")
            app.state.pg_pool = None
        elif settings.DATABASE_URL:
            try:
                from psycopg_pool import AsyncConnectionPool
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                
                connection_kwargs = {
                    "autocommit": True,
                    "prepare_threshold": 0,
                }
                
                logger.info("Setting up PostgreSQL connection pool for chat checkpointer...")
                pg_pool = AsyncConnectionPool(
                    conninfo=settings.DATABASE_URL,
                    max_size=20,
                    kwargs=connection_kwargs,
                    open=False  # Will open explicitly
                )
                
                await pg_pool.open()
                
                # Setup checkpointer tables
                async with pg_pool.connection() as conn:
                    checkpointer = AsyncPostgresSaver(conn)
                    await checkpointer.setup()
                    logger.info("PostgreSQL checkpointer tables set up successfully")
                
                # Store the pool in app state for use by endpoints
                app.state.pg_pool = pg_pool
                logger.info("PostgreSQL connection pool ready for chat checkpointer")
                
            except ImportError:
                logger.warning("PostgreSQL checkpointer packages not available, chat will use MemorySaver")
                app.state.pg_pool = None
            except Exception as e:
                logger.error(f"Failed to setup PostgreSQL connection pool: {e}")
                app.state.pg_pool = None
        else:
            logger.info("No DATABASE_URL configured, chat will use MemorySaver")
            app.state.pg_pool = None
            
    except Exception as e:
        logger.error(f"Error during PostgreSQL setup: {e}")
        app.state.pg_pool = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down Nova Backend Server...")
    
    # Stop prompt file watching
    try:
        from utils.prompt_loader import stop_nova_prompt_watching
        stop_nova_prompt_watching()
        logger.info("Stopped watching Nova system prompt file")
    except Exception as e:
        logger.error(f"Error stopping prompt watching: {e}")
    
    # Close PostgreSQL connection pool
    if hasattr(app.state, 'pg_pool') and app.state.pg_pool:
        try:
            await app.state.pg_pool.close()
            logger.info("PostgreSQL connection pool closed")
        except Exception as e:
            logger.error(f"Error closing PostgreSQL pool: {e}")
    
    await db_manager.close()


# Create FastAPI app
app = FastAPI(
    title="Nova Backend Server",
    description="Core Nova backend with REST API and LangChain tools",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware for frontend
default_cors_origins = "http://localhost:3000,http://localhost:3001,http://172.29.172.59:3000"
cors_origins = os.getenv("CORS_ORIGINS", default_cors_origins).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router)
app.include_router(chat_router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "nova-backend",
        "version": "2.0.0",
        "description": "Nova Backend Server with PostgreSQL backend and LangChain tools",
        "endpoints": {
            "api": "/api/ (for frontend)",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        async with db_manager.get_session() as session:
            await session.execute(text("SELECT 1"))
        
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "nova-backend",
        "version": "2.0.0",
        "database": db_status,
        "endpoints": {
            "api_available": True
        }
    }


async def main():
    """Main entry point."""
    from config import settings
    
    # Use config values with environment variable fallback
    port = int(os.getenv("PORT", settings.CHAT_AGENT_PORT))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Database URL: {os.getenv('DATABASE_URL', 'postgresql://nova:nova_dev_password@localhost:5432/nova_kanban')}")
    
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info"
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main()) 