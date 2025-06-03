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
    # Only create tables if explicitly needed for development.
    if os.getenv("CREATE_TABLES", "false").lower() == "true":
        try:
            await db_manager.create_tables()
            logger.info("Database tables created/verified")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Nova Backend Server...")
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
    # Use standard Nova environment variables
    port = int(os.getenv("PORT", 8000))
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