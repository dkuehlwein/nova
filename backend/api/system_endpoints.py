"""
System Management API Endpoints

Provides system-level functionality including health monitoring, 
service management, and development utilities.
"""

import subprocess
from typing import Dict, Any, List
import asyncio
import aiohttp

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from utils.logging import get_logger
from mcp_client import mcp_manager
from api.mcp_endpoints import get_mcp_servers
from database.database import db_manager
from sqlalchemy import text

logger = get_logger("system-api")
router = APIRouter(prefix="/api/system", tags=["System Management"])

# Allowed services for restart operations (security measure)
ALLOWED_SERVICES = {
    "mcp_gmail",
    "redis", 
    "postgres",
    "chat-agent",
    "core-agent"
}


class ServiceRestartRequest(BaseModel):
    """Optional request body for service restart (currently unused but ready for future params)"""
    force: bool = False


class ServiceRestartResponse(BaseModel):
    """Response for service restart operations"""
    service_name: str
    status: str  # "success" | "error"
    message: str
    stdout: str
    stderr: str
    exit_code: int


class SystemHealthSummary(BaseModel):
    """System health summary for navbar display"""
    overall_status: str  # "operational", "degraded", "critical"
    chat_agent_status: str
    core_agent_status: str
    mcp_servers_healthy: int
    mcp_servers_total: int
    database_status: str


async def check_database_health() -> str:
    """Check database health using existing database manager."""
    try:
        async with db_manager.get_session() as session:
            await session.execute(text("SELECT 1"))
        return "healthy"
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return "unhealthy"


async def check_core_agent_health() -> str:
    """Check core agent health via its dedicated health endpoint."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3.0)) as session:
            async with session.get("http://localhost:8001/health") as response:
                if response.status == 200:
                    data = await response.json()
                    return "healthy" if data.get("status") == "healthy" else "degraded"
                else:
                    return "unhealthy"
    except Exception as e:
        logger.warning(f"Core agent health check failed: {e}")
        return "unhealthy"


@router.get("/system-health-summary", response_model=SystemHealthSummary)
async def get_system_health_summary():
    """
    Get aggregated system health summary for navbar display.
    
    Checks actual health endpoints for accurate status reporting.
    """
    try:
        # Use existing MCP server health check
        mcp_data = await get_mcp_servers()
        mcp_servers_healthy = mcp_data.healthy_servers
        mcp_servers_total = mcp_data.enabled_servers
        
        # Check database using existing database manager
        database_status = await check_database_health()
        
        # Check core agent health via its endpoint
        core_agent_status = await check_core_agent_health()
        
        # Chat agent is healthy if we can reach this endpoint (since this runs on chat agent service)
        chat_agent_status = "healthy"
        
        # Determine overall status
        overall_status = "operational"
        
        # Critical if any core service is unhealthy
        if (core_agent_status == "unhealthy" or database_status == "unhealthy"):
            overall_status = "critical"
        # Degraded if core agent is degraded or some MCP servers are down
        elif (core_agent_status == "degraded" or 
              (mcp_servers_total > 0 and mcp_servers_healthy < mcp_servers_total)):
            overall_status = "degraded"
        
        logger.info(f"System health summary: {overall_status} (chat: {chat_agent_status}, core: {core_agent_status}, db: {database_status}, mcp: {mcp_servers_healthy}/{mcp_servers_total})")
        
        return SystemHealthSummary(
            overall_status=overall_status,
            chat_agent_status=chat_agent_status,
            core_agent_status=core_agent_status,
            mcp_servers_healthy=mcp_servers_healthy,
            mcp_servers_total=mcp_servers_total,
            database_status=database_status
        )
        
    except Exception as e:
        logger.error(f"Failed to get system health summary: {e}")
        return SystemHealthSummary(
            overall_status="critical",
            chat_agent_status="unknown",
            core_agent_status="unknown", 
            mcp_servers_healthy=0,
            mcp_servers_total=0,
            database_status="unknown"
        )


@router.post("/restart/{service_name}", response_model=ServiceRestartResponse)
async def restart_service(service_name: str, request: ServiceRestartRequest = ServiceRestartRequest()):
    """
    Restart a specific service using docker-compose.
    
    This is a development-only endpoint for convenience during development.
    In production, service restarts should be handled by proper deployment tools.
    
    Args:
        service_name: Name of the service to restart (must be in ALLOWED_SERVICES)
        request: Optional request parameters (currently unused)
    
    Returns:
        ServiceRestartResponse with operation details and output
    
    Raises:
        HTTPException: If service is not allowed or restart fails
    """
    
    # Sanitize service name against allowed services
    if service_name not in ALLOWED_SERVICES:
        logger.warning(f"Attempted to restart unauthorized service: {service_name}")
        raise HTTPException(
            status_code=400,
            detail=f"Service '{service_name}' is not allowed for restart. Allowed services: {', '.join(sorted(ALLOWED_SERVICES))}"
        )
    
    logger.info(f"Attempting to restart service: {service_name}")
    
    try:
        # Execute docker-compose restart command
        cmd = ["docker-compose", "restart", service_name]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout for restart operations
        )
        
        # Determine status based on exit code
        status = "success" if result.returncode == 0 else "error"
        
        if status == "success":
            message = f"Service '{service_name}' restarted successfully"
            logger.info(f"Service {service_name} restarted successfully")
        else:
            message = f"Service '{service_name}' restart failed with exit code {result.returncode}"
            logger.error(f"Service {service_name} restart failed: {result.stderr}")
        
        return ServiceRestartResponse(
            service_name=service_name,
            status=status,
            message=message,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            exit_code=result.returncode
        )
        
    except subprocess.TimeoutExpired:
        error_msg = f"Service '{service_name}' restart timed out after 60 seconds"
        logger.error(error_msg)
        raise HTTPException(status_code=408, detail=error_msg)
        
    except FileNotFoundError:
        error_msg = "docker-compose command not found. Ensure Docker Compose is installed and in PATH."
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error restarting service '{service_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/allowed-services")
async def get_allowed_services() -> Dict[str, Any]:
    """
    Get list of services that are allowed to be restarted.
    
    Returns:
        Dict containing allowed services and their count
    """
    return {
        "allowed_services": sorted(ALLOWED_SERVICES),
        "total_count": len(ALLOWED_SERVICES),
        "note": "These are the services that can be restarted via the system API"
    }


@router.get("/health")
async def system_health() -> Dict[str, str]:
    """
    Simple health check for the system endpoints.
    
    Returns:
        Dict with health status information
    """
    return {
        "status": "healthy",
        "service": "system-api",
        "version": "1.0.0"
    }


