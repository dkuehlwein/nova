"""
Nova Core Agent Service

This service runs the proactive task processing loop that monitors kanban lanes
and autonomously processes tasks using AI. It shares the same database and
infrastructure as the chat service but runs independently.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from sqlalchemy import text

from agent.core_agent import CoreAgent
from database.database import db_manager
from utils.logging import configure_logging, get_logger, RequestLoggingMiddleware

# Load environment variables
load_dotenv()

# Configure structured logging
configure_logging(
    service_name="core-agent",
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    enable_json=os.getenv("LOG_FORMAT", "json").lower() == "json"
)
logger = get_logger("startup")

# Reduce verbosity of third-party libraries
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("mcp.client").setLevel(logging.WARNING)
logging.getLogger("mcp.client.streamable_http").setLevel(logging.WARNING)

# Configure LangSmith tracing
os.environ["LANGSMITH_TRACING"] = "true"
# API key should be set in environment: LANGSMITH_API_KEY=ls_...
# Project name can be set: LANGSMITH_PROJECT="Nova Core Agent"

# Global core agent instance
core_agent: Optional[CoreAgent] = None
agent_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    global core_agent, agent_task
    
    # Startup
    logger.info("Starting Nova Core Agent Service...")
    
    # Start prompt file watching for hot-reload
    try:
        from utils.prompt_loader import start_nova_prompt_watching
        start_nova_prompt_watching()
        logger.info("Started watching Nova system prompt file for changes")
    except Exception as e:
        logger.error(f"Failed to start prompt watching: {e}")
    
    try:
        # Initialize the core agent
        core_agent = CoreAgent()
        await core_agent.initialize()
        
        # Start the agent processing loop in background
        agent_task = asyncio.create_task(core_agent.run_loop())
        
        logger.info("Nova Core Agent Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start core agent: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Nova Core Agent Service...")
    
    # Stop prompt file watching
    try:
        from utils.prompt_loader import stop_nova_prompt_watching
        stop_nova_prompt_watching()
        logger.info("Stopped watching Nova system prompt file")
    except Exception as e:
        logger.error(f"Error stopping prompt watching: {e}")
    
    # Shutdown core agent with timeout
    if core_agent:
        try:
            await asyncio.wait_for(core_agent.shutdown(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("Core agent shutdown timed out")
    
    # Cancel agent task with timeout
    if agent_task and not agent_task.done():
        agent_task.cancel()
        try:
            await asyncio.wait_for(agent_task, timeout=5.0)
        except asyncio.CancelledError:
            logger.info("Agent task cancelled successfully")
        except asyncio.TimeoutError:
            logger.warning("Agent task cancellation timed out")
    
    # Clean up MCP connections
    try:
        from mcp_client import mcp_manager
        await asyncio.wait_for(mcp_manager.cleanup(), timeout=3.0)
    except asyncio.TimeoutError:
        logger.warning("MCP client cleanup timed out")
    except Exception as e:
        logger.debug(f"MCP cleanup error: {e}")
    
    # Close database connections with timeout
    try:
        await asyncio.wait_for(db_manager.close(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Database shutdown timed out")
    
    logger.info("Nova Core Agent Service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Nova Core Agent Service",
    description="Proactive task processing service for Nova",
    version="1.0.0",
    lifespan=lifespan
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware, service_name="core-agent")


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "nova-core-agent",
        "version": "1.0.0",
        "description": "Nova Core Agent Service - Autonomous task processor",
        "endpoints": {
            "status": "/status",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    global core_agent
    
    try:
        # Test database connection
        async with db_manager.get_session() as session:
            await session.execute(text("SELECT 1"))
        
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Check agent status
    agent_status = "unknown"
    if core_agent:
        try:
            status = await core_agent.get_status()
            agent_status = status.status.value
        except Exception as e:
            logger.error(f"Agent status check failed: {e}")
            agent_status = "error"
    
    return {
        "status": "healthy" if db_status == "healthy" and agent_status != "error" else "degraded",
        "service": "nova-core-agent",
        "version": "1.0.0",
        "database": db_status,
        "agent_status": agent_status,
        "is_processing": agent_status == "processing"
    }


@app.get("/status")
async def get_agent_status():
    """Get detailed agent status."""
    global core_agent
    
    if not core_agent:
        raise HTTPException(status_code=503, detail="Core agent not initialized")
    
    try:
        status = await core_agent.get_status()
        recent_tasks = await core_agent.get_recent_task_history(limit=5)
        
        return {
            "agent_id": str(status.id),
            "status": status.status.value,
            "started_at": status.started_at.isoformat(),
            "last_activity": status.last_activity.isoformat() if status.last_activity else None,
            "current_task_id": str(status.current_task_id) if status.current_task_id else None,
            "total_tasks_processed": status.total_tasks_processed,
            "error_count": status.error_count,
            "last_error": status.last_error,
            "recent_tasks": [
                {
                    "id": str(task.id),
                    "title": task.title,
                    "status": task.status.value,
                    "updated_at": task.updated_at.isoformat()
                }
                for task in recent_tasks
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent status")


@app.post("/pause")
async def pause_agent():
    """Pause the core agent."""
    global core_agent
    
    if not core_agent:
        raise HTTPException(status_code=503, detail="Core agent not initialized")
    
    try:
        await core_agent.pause()
        return {"message": "Core agent paused"}
    except Exception as e:
        logger.error(f"Failed to pause agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to pause agent")


@app.post("/resume")
async def resume_agent():
    """Resume the core agent."""
    global core_agent
    
    if not core_agent:
        raise HTTPException(status_code=503, detail="Core agent not initialized")
    
    try:
        await core_agent.resume()
        return {"message": "Core agent resumed"}
    except Exception as e:
        logger.error(f"Failed to resume agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to resume agent")


@app.post("/process-task/{task_id}")
async def force_process_task(task_id: str):
    """Force process a specific task (for testing/debugging)."""
    global core_agent
    
    if not core_agent:
        raise HTTPException(status_code=503, detail="Core agent not initialized")
    
    try:
        result = await core_agent.force_process_task(task_id)
        return {"message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to force process task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process task")


async def main():
    """Main entry point."""
    from config import settings
    
    # Use config values with environment variable fallback
    port = int(os.getenv("CORE_AGENT_PORT", settings.CORE_AGENT_PORT))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Nova Core Agent Service on {host}:{port}")
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