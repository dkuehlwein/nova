"""
Nova Core Agent Service

This service runs the proactive task processing loop that monitors kanban lanes
and autonomously processes tasks using AI.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from dotenv import load_dotenv

# Load environment variables FIRST before importing config
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from agent.core_agent import CoreAgent
from utils.service_manager import ServiceManager, create_prompt_updated_handler
from utils.logging import RequestLoggingMiddleware, configure_logging
from config import settings

# Configure logging based on settings (after environment is loaded)
configure_logging(
    service_name="core-agent",
    log_level=settings.LOG_LEVEL,
    enable_json=settings.LOG_JSON,
    enable_file_logging=settings.LOG_FILE_ENABLED,
    log_file_path=settings.LOG_FILE_PATH,
    max_file_size=settings.LOG_FILE_MAX_SIZE_MB * 1024 * 1024,  # Convert MB to bytes
    backup_count=settings.LOG_FILE_BACKUP_COUNT
)

# Configure LangSmith tracing
os.environ["LANGSMITH_TRACING"] = "true"

# Global instances
service_manager = ServiceManager("core-agent")
core_agent: Optional[CoreAgent] = None
agent_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    global core_agent, agent_task
    
    # Startup
    service_manager.logger.info("Starting Nova Core Agent Service...")
    
    try:
        # Start prompt watching
        await service_manager.start_prompt_watching()
        
        # Initialize PostgreSQL pool via ServiceManager
        await service_manager.init_pg_pool()
        
        # Initialize the core agent with the shared pool
        core_agent = CoreAgent(pg_pool=service_manager.pg_pool)
        await core_agent.initialize()
        
        # Create prompt update handler
        async def reload_core_agent():
            await core_agent.reload_agent()
        
        event_handler = await create_prompt_updated_handler(reload_core_agent)
        
        # Start Redis bridge for agent reloading
        await service_manager.start_redis_bridge(app, event_handler)
        
        # Start the agent processing loop
        agent_task = asyncio.create_task(core_agent.run_loop())
        
        service_manager.logger.info("Nova Core Agent Service started successfully")
        
    except Exception as e:
        service_manager.logger.error(f"Failed to start core agent: {e}")
        raise
    
    yield
    
    # Shutdown
    service_manager.logger.info("Shutting down Nova Core Agent Service...")
    
    # Stop services
    await service_manager.stop_prompt_watching()
    await service_manager.stop_redis_bridge(app)
    
    # Shutdown core agent
    if core_agent:
        try:
            await asyncio.wait_for(core_agent.shutdown(), timeout=10.0)
        except asyncio.TimeoutError:
            service_manager.logger.warning("Core agent shutdown timed out")
    
    # Cancel agent task
    if agent_task and not agent_task.done():
        agent_task.cancel()
        try:
            await asyncio.wait_for(agent_task, timeout=5.0)
        except asyncio.CancelledError:
            service_manager.logger.info("Agent task cancelled successfully")
        except asyncio.TimeoutError:
            service_manager.logger.warning("Agent task cancellation timed out")
    
    # Cleanup resources
    await service_manager.cleanup_mcp()
    await service_manager.cleanup_database()
    await service_manager.close_pg_pool()
    
    service_manager.logger.info("Nova Core Agent Service shutdown complete")


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
        "status": "running" if core_agent and core_agent.is_running else "stopped"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if not core_agent:
        raise HTTPException(status_code=503, detail="Core agent not initialized")
    
    try:
        status = await core_agent.get_status()
        return {
            "status": "healthy",
            "agent_status": status.status.value,
            "current_task": str(status.current_task_id) if status.current_task_id else None,
            "started_at": status.started_at.isoformat() if status.started_at else None,
            "last_activity": status.last_activity.isoformat() if status.last_activity else None,
            "error": status.last_error
        }
    except Exception as e:
        service_manager.logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")


@app.get("/status")
async def get_agent_status():
    """Get detailed agent status."""
    if not core_agent:
        raise HTTPException(status_code=503, detail="Core agent not initialized")
    
    try:
        status = await core_agent.get_status()
        recent_tasks = await core_agent.get_recent_task_history(limit=10)
        
        return {
            "agent_status": status.status.value,
            "current_task_id": str(status.current_task_id) if status.current_task_id else None,
            "started_at": status.started_at.isoformat() if status.started_at else None,
            "last_activity": status.last_activity.isoformat() if status.last_activity else None,
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
        service_manager.logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@app.post("/pause")
async def pause_agent():
    """Pause the agent."""
    if not core_agent:
        raise HTTPException(status_code=503, detail="Core agent not initialized")
    
    try:
        await core_agent.pause()
        return {"message": "Agent paused successfully"}
    except Exception as e:
        service_manager.logger.error(f"Failed to pause agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause agent: {str(e)}")


@app.post("/resume")
async def resume_agent():
    """Resume the agent."""
    if not core_agent:
        raise HTTPException(status_code=503, detail="Core agent not initialized")
    
    try:
        await core_agent.resume()
        return {"message": "Agent resumed successfully"}
    except Exception as e:
        service_manager.logger.error(f"Failed to resume agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume agent: {str(e)}")


@app.post("/process-task/{task_id}")
async def force_process_task(task_id: str):
    """Force process a specific task."""
    if not core_agent:
        raise HTTPException(status_code=503, detail="Core agent not initialized")
    
    try:
        result = await core_agent.force_process_task(task_id)
        return {"message": result}
    except Exception as e:
        service_manager.logger.error(f"Failed to process task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process task: {str(e)}")


async def main():
    """Run the core agent service."""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8001,  # Different port from main website
        log_config=None  # Use our custom logging
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main()) 