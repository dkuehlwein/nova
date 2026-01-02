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

# Load environment variables FIRST before importing config
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.api_endpoints import router as api_router
from api.chat_endpoints import router as chat_router
from api.websocket_endpoints import router as websocket_router
from api.mcp_endpoints import router as mcp_router
from api.config_endpoints import router as file_config_router
from api.system_endpoints import router as system_router
from api.prompt_endpoints import router as prompt_router
from api.memory_endpoints import router as memory_router
from api.settings_endpoints import router as user_settings_router
from api.llm_endpoints import router as llm_router
from api.tool_permissions_endpoints import router as tool_permissions_router
from api.skill_endpoints import router as skill_router
from utils.service_manager import ServiceManager
from utils.logging import RequestLoggingMiddleware, configure_logging
from config import settings

# Configure logging based on settings (after environment is loaded)
configure_logging(
    service_name="chat-agent",
    log_level=settings.LOG_LEVEL,
    enable_json=settings.LOG_JSON,
    enable_file_logging=settings.LOG_FILE_ENABLED,
    log_file_path=settings.LOG_FILE_PATH,
    max_file_size=settings.LOG_FILE_MAX_SIZE_MB * 1024 * 1024,  # Convert MB to bytes
    backup_count=settings.LOG_FILE_BACKUP_COUNT
)

# Global instances
service_manager = ServiceManager("chat-agent")

# Make service_manager available to other modules
def get_service_manager():
    """Get the global service manager instance."""
    return service_manager


async def create_website_event_handler():
    """Create event handler for website service (WebSocket + chat agent reloading)."""
    from utils.websocket_manager import websocket_manager
    from agent.chat_agent import clear_chat_agent_cache
    from utils.event_handlers import create_unified_event_handler
    
    return create_unified_event_handler(
        service_name="chat-agent",
        clear_cache_func=clear_chat_agent_cache,
        websocket_broadcast_func=websocket_manager.broadcast_event
    )


# PostgreSQL pool management is now handled by ServiceManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    service_manager.logger.info("Starting Nova Backend Server...")
    
    try:
        # Initialize unified configuration system
        from utils.config_registry import initialize_configs, start_config_watchers
        service_manager.logger.info("Initializing unified configuration system...")
        initialize_configs()
        start_config_watchers()
        
        # Ensure database is initialized before starting services
        await service_manager.ensure_database_initialized()
        
        # Initialize PostgreSQL pool via ServiceManager
        await service_manager.init_pg_pool()
        
        # Start health monitor service
        from services.health_monitor import health_monitor
        await health_monitor.start()
        service_manager.logger.info("Health monitor service started")
        
        # Create event handler for WebSocket broadcasting and agent reloading
        event_handler = await create_website_event_handler()
        
        # Start Redis bridge
        await service_manager.start_redis_bridge(app, event_handler)
        
        # Initialize LLM models
        service_manager.logger.info("Initializing LLM models...")
        try:
            from services.llm_service import llm_service
            from database.database import db_manager
            
            async with db_manager.get_session() as session:
                success = await llm_service.initialize_default_models_in_litellm(session)
                if success:
                    service_manager.logger.info("Successfully initialized working LLM models")
                else:
                    service_manager.logger.warning("Model initialization completed with issues")
        except Exception as e:
            service_manager.logger.error(f"Failed to initialize LLM models: {e}")
            # Don't fail startup if model initialization fails
        
        service_manager.logger.info("Nova Backend Server started successfully")
        
    except Exception as e:
        service_manager.logger.error(f"Failed to start server: {e}")
        raise
    
    yield
    
    # Shutdown
    service_manager.logger.info("Shutting down Nova Backend Server...")
    
    # Stop services
    from utils.config_registry import stop_config_watchers
    stop_config_watchers()
    await service_manager.stop_redis_bridge(app)
    
    # Stop health monitor
    from services.health_monitor import health_monitor
    await health_monitor.stop()
    service_manager.logger.info("Health monitor service stopped")
    
    # Cleanup resources
    await service_manager.cleanup_redis()
    await service_manager.cleanup_memory()    # Add memory cleanup
    await service_manager.close_pg_pool()
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
app.add_middleware(RequestLoggingMiddleware, service_name="website")

# Include routers
app.include_router(api_router)
app.include_router(chat_router)
app.include_router(websocket_router)
app.include_router(mcp_router)
app.include_router(system_router)
app.include_router(file_config_router)
app.include_router(prompt_router)
app.include_router(memory_router)
app.include_router(user_settings_router)
app.include_router(llm_router)
app.include_router(tool_permissions_router)
app.include_router(skill_router)


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
            "chat_checkpointer": "postgresql" if service_manager.pg_pool else "memory"
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
    
    # Log server startup using our structured logging
    service_manager.logger.info("Starting uvicorn server", extra={"data": {"host": "0.0.0.0", "port": 8000}})
    
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main()) 