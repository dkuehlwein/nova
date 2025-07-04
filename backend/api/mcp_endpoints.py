"""
MCP Server Management API Endpoints

Provides REST API for managing MCP servers configuration and monitoring health status.
Implements work package B5 from the settings realization roadmap.
"""

import asyncio
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from mcp_client import mcp_manager
from utils.config_registry import get_config, save_config
from utils.logging import get_logger, log_config_change
from utils.redis_manager import publish
from models.events import create_mcp_toggled_event

logger = get_logger("mcp-api")
router = APIRouter(prefix="/api/mcp", tags=["MCP Servers"])

# Import domain-specific models
from models.mcp import MCPServerStatus, MCPServersResponse, MCPToggleRequest, MCPToggleResponse


@router.get("/", response_model=MCPServersResponse)
async def get_mcp_servers():
    """
    Get all MCP servers with their configuration and health status.
    
    Returns both enabled and disabled servers from YAML configuration,
    with real-time health status for enabled servers.
    """
    try:
        # Load all servers from YAML (enabled and disabled)
        mcp_config = get_config("mcp_servers")
        
        if not mcp_config:
            return MCPServersResponse(
                servers=[],
                total_servers=0,
                healthy_servers=0,
                enabled_servers=0
            )
        
        servers = []
        health_check_tasks = []
        
        # Prepare server info and health check tasks
        for server_name, server_config in mcp_config.items():
            server_info = {
                "name": server_name,
                "url": server_config["url"],
                "description": server_config.get("description", f"{server_name} MCP Server"),
                "enabled": server_config.get("enabled", True)
            }
            
            servers.append(server_info)
            
            # Only check health for enabled servers using standard MCP protocol
            if server_info["enabled"]:
                health_check_tasks.append(
                    mcp_manager.check_server_health_and_get_tools_count(server_info, timeout=3.0)
                )
            else:
                health_check_tasks.append(None)
        
        # Run health checks concurrently for enabled servers
        health_results = []
        for i, task in enumerate(health_check_tasks):
            if task is not None:
                try:
                    # Use asyncio.wait_for to add timeout safety
                    result = await asyncio.wait_for(task, timeout=3.5)
                    health_results.append(result)
                except asyncio.TimeoutError:
                    health_results.append((False, None))
                except Exception:
                    health_results.append((False, None))
            else:
                health_results.append((False, None))  # Disabled servers are marked as unhealthy
        
        # Build response with health status and tools count
        response_servers = []
        healthy_count = 0
        enabled_count = 0
        
        for server_info, (is_healthy, tools_count) in zip(servers, health_results):
            if server_info["enabled"]:
                enabled_count += 1
                if is_healthy:
                    healthy_count += 1
            
            response_servers.append(MCPServerStatus(
                name=server_info["name"],
                url=server_info["url"],
                health_url=server_info.get("health_url"),  # Optional health URL
                description=server_info["description"],
                enabled=server_info["enabled"],
                healthy=is_healthy,
                tools_count=tools_count,  # Now includes actual tools count from standard MCP protocol
                error=None if is_healthy else "Server unavailable" if server_info["enabled"] else "Server disabled"
            ))
        
        logger.info(f"MCP servers status retrieved: {len(servers)} total, {enabled_count} enabled, {healthy_count} healthy")
        
        return MCPServersResponse(
            servers=response_servers,
            total_servers=len(servers),
            healthy_servers=healthy_count,
            enabled_servers=enabled_count
        )
        
    except Exception as e:
        logger.error(f"Failed to get MCP servers status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve MCP servers: {str(e)}")


@router.put("/{server_name}/toggle", response_model=MCPToggleResponse)
async def toggle_mcp_server(server_name: str, request: MCPToggleRequest):
    """
    Toggle MCP server enabled/disabled status.
    
    Updates the YAML configuration and publishes a real-time event
    to notify connected clients of the status change.
    """
    try:
        # Load current configuration
        mcp_config = get_config("mcp_servers")
        
        if server_name not in mcp_config:
            raise HTTPException(
                status_code=404, 
                detail=f"MCP server '{server_name}' not found in configuration"
            )
        
        # Check if status is actually changing
        current_status = mcp_config[server_name].get("enabled", True)
        if current_status == request.enabled:
            return MCPToggleResponse(
                server_name=server_name,
                enabled=request.enabled,
                message=f"Server '{server_name}' is already {'enabled' if request.enabled else 'disabled'}"
            )
        
        # Update configuration
        mcp_config[server_name]["enabled"] = request.enabled
        
        # Save configuration with validation
        save_config("mcp_servers", mcp_config)
        
        # Log the configuration change
        log_config_change(
            operation="mcp_server_toggled",
            config_type="mcp_servers",
            details={
                "server_name": server_name,
                "enabled": request.enabled,
                "previous_enabled": current_status,
                "user_action": True
            },
            logger=logger
        )
        
        # Publish real-time event
        event = create_mcp_toggled_event(
            server_name=server_name,
            enabled=request.enabled,
            source="mcp-api"
        )
        
        # Publish event (non-blocking, graceful failure)
        try:
            await publish(event)
            logger.info(f"Published MCP toggle event for {server_name}")
        except Exception as e:
            logger.warning(f"Failed to publish MCP toggle event: {e}")
        
        action = "enabled" if request.enabled else "disabled"
        message = f"MCP server '{server_name}' has been {action}"
        
        logger.info(f"MCP server {server_name} {action} successfully")
        
        return MCPToggleResponse(
            server_name=server_name,
            enabled=request.enabled,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle MCP server {server_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to toggle MCP server '{server_name}': {str(e)}"
        ) 