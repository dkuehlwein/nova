"""
Admin API Endpoints

Provides administrative functionality for development and maintenance.
Implements work package B6 from the settings realization roadmap.
"""

import subprocess
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from utils.logging import get_logger

logger = get_logger("admin-api")
router = APIRouter(prefix="/api/admin", tags=["Administration"])

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
        "note": "These are the services that can be restarted via the admin API"
    }


@router.get("/health")
async def admin_health() -> Dict[str, str]:
    """
    Simple health check for the admin endpoints.
    
    Returns:
        Dict with health status information
    """
    return {
        "status": "healthy",
        "service": "admin-api",
        "version": "1.0.0"
    } 