"""
System Management API Endpoints

Provides system-level functionality including health monitoring, 
service management, and development utilities.
"""

import subprocess
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException

from utils.logging import get_logger
from services.health_monitor import health_monitor

# Import domain-specific models
from models.system import ServiceRestartRequest, ServiceRestartResponse

logger = get_logger("system-api")
router = APIRouter(prefix="/api/system", tags=["System Management"])

# Allowed services for restart operations (security measure)
ALLOWED_SERVICES = {
    "mcp_gmail",
    "redis", 
    "postgres",
    "chat-agent",
    "core-agent",
    "llamacpp"
}




@router.post("/restart/{service_name}", response_model=ServiceRestartResponse)
async def restart_service(service_name: str):
    """
    Restart a specific service using docker-compose.
    
    This is a development-only endpoint for convenience during development.
    In production, service restarts should be handled by proper deployment tools.
    
    Args:
        service_name: Name of the service to restart (must be in ALLOWED_SERVICES)
    
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


@router.get("/system-health")
async def get_unified_system_status(
    force_refresh: bool = False,
    include_history: bool = False
):
    """
    Get comprehensive system status with caching from unified health monitor.
    
    This is the primary endpoint for unified system health monitoring following ADR 010.
    
    Args:
        force_refresh: Force real-time checks (bypass cache)
        include_history: Include health history for trends
    
    Returns:
        Comprehensive system status with cached data
    """
    try:
        # If force refresh requested, trigger immediate health check
        if force_refresh:
            await health_monitor.monitor_all_services()
        
        # Get overall status calculation
        overall_status = await health_monitor.calculate_overall_status()
        
        # Build service categories for response
        core_services = []
        infrastructure_services = []
        
        for service_name, config in health_monitor.SERVICES.items():
            cached_status = overall_status["all_statuses"].get(service_name)
            
            # If no cached status, create a default "unknown" status entry
            if not cached_status:
                cached_status = {
                    "status": "unknown",
                    "response_time_ms": None,
                    "checked_at": None,
                    "error_message": "No status data available",
                    "metadata": {"reason": "no_cached_data"}
                }
                
            service_data = {
                "name": service_name,
                "type": config["type"],
                "status": cached_status.get("status", "unknown"),
                "response_time_ms": cached_status.get("response_time_ms"),
                "last_check": cached_status.get("checked_at"),
                "error_message": cached_status.get("error_message"),
                "metadata": cached_status.get("metadata", {}),
                "essential": config.get("essential", False)
            }
            
            if config["type"] == "core":
                core_services.append(service_data)
            elif config["type"] == "infrastructure":
                infrastructure_services.append(service_data)
        
        # Build unified response
        response = {
            "overall_status": overall_status["overall_status"],
            "overall_health_percentage": overall_status["overall_health_percentage"],
            "last_updated": overall_status["last_updated"],
            "cached": not force_refresh,
            
            # Service Categories
            "core_services": core_services,
            "infrastructure_services": infrastructure_services,
            
            # Quick Summary for Navbar
            "summary": overall_status["summary"]
        }
        
        # Add history if requested
        if include_history:
            response["history"] = await _get_health_history()
        
        logger.debug(f"Unified system status: {overall_status['overall_status']} "
                    f"({overall_status['summary']['healthy_services']}/{overall_status['summary']['total_services']} healthy)")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get unified system status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve system status: {str(e)}")


@router.get("/system-health/{service_name}")
async def get_service_status(
    service_name: str,
    force_refresh: bool = False
):
    """
    Get detailed status for specific service.
    
    Args:
        service_name: Name of the service to check
        force_refresh: Force real-time check (bypass cache)
    
    Returns:
        Detailed service status information
    """
    try:
        # Validate service exists
        if service_name not in health_monitor.SERVICES:
            raise HTTPException(
                status_code=404, 
                detail=f"Service '{service_name}' not found in monitoring configuration"
            )
        
        # If force refresh, trigger check for this specific service
        if force_refresh:
            config = health_monitor.SERVICES[service_name]
            if config["endpoint"] == "cached":
                # For cached services, we can't force refresh here
                pass
            elif config["endpoint"] == "model_availability":
                # AI model availability - trigger individual check
                await health_monitor._check_ai_model_availability(service_name, config)
            elif config["endpoint"] != "dynamic" and config["endpoint"] != "internal":
                # HTTP service - trigger individual check
                await health_monitor._check_http_service(service_name, config)
            elif config["endpoint"] == "internal":
                # Internal service - trigger individual check
                await health_monitor._check_internal_service(service_name, config)
        
        # Get cached status
        cached_status = await health_monitor.get_cached_status(service_name)
        
        if not cached_status:
            raise HTTPException(
                status_code=404,
                detail=f"No status data available for service '{service_name}'"
            )
        
        # Add service configuration info
        config = health_monitor.SERVICES[service_name]
        response = {
            **cached_status,
            "service_type": config["type"],
            "essential": config.get("essential", False),
            "endpoint": config["endpoint"],
            "functional_tests": config.get("functional_tests", [])
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status for service {service_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get service status: {str(e)}")


@router.post("/system-health/refresh")
async def refresh_all_services():
    """
    Trigger immediate refresh of all service health checks.
    
    This bypasses the cache and performs real-time health checks for all services.
    
    Returns:
        Summary of refresh operation
    """
    try:
        logger.info("Manual refresh of all services triggered")
        
        # Trigger immediate health check for all services
        await health_monitor.monitor_all_services()
        
        # Get updated overall status
        overall_status = await health_monitor.calculate_overall_status()
        
        return {
            "message": "All services refreshed successfully",
            "overall_status": overall_status["overall_status"],
            "refreshed_at": overall_status["last_updated"],
            "summary": overall_status["summary"]
        }
        
    except Exception as e:
        logger.error(f"Failed to refresh all services: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to refresh services: {str(e)}")


async def _get_health_history() -> List[Dict[str, Any]]:
    """Get recent health history for trends (placeholder for future implementation)."""
    # TODO: Implement health history retrieval from SystemHealthStatus table
    # This would query the last 24 hours of health data and provide trend information
    return []


