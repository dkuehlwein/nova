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
from utils.service_manager import ServiceManager, create_prompt_updated_handler
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
                # Clear the global agent cache (this also clears tools cache internally)
                clear_chat_agent_cache()
                
                service_manager.logger.info("Chat agent cache cleared - all chats will use updated prompt")
            except Exception as e:
                service_manager.logger.error(f"Failed to reload chat agent: {e}")
        
        # Handle agent reloading for MCP server changes
        elif event.type == "mcp_toggled":
            try:
                service_manager.logger.info(
                    f"MCP server toggled, reloading chat agent: {event.data.get('server_name')} -> {event.data.get('enabled')}",
                    extra={
                        "data": {
                            "event_id": event.id,
                            "server_name": event.data.get('server_name'),
                            "enabled": event.data.get('enabled'),
                            "source": event.source
                        }
                    }
                )
                # Clear the chat agent cache - MCP client will fetch fresh tools automatically
                clear_chat_agent_cache()
                
                service_manager.logger.info("Chat agent cache cleared - all chats will use updated MCP tools")
            except Exception as e:
                service_manager.logger.error(f"Failed to reload chat agent after MCP toggle: {e}")
    
    return handle_event


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
        
        # Initialize PostgreSQL pool via ServiceManager
        await service_manager.init_pg_pool()
        
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
    from utils.config_registry import stop_config_watchers
    stop_config_watchers()
    await service_manager.stop_redis_bridge(app)
    
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