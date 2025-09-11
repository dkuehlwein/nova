"""
Tool Permissions API Endpoints

FastAPI endpoints for managing tool permissions configuration.
"""

import logging
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.chat_agent import clear_chat_agent_cache
from utils.tool_permissions_manager import permission_config, ToolApprovalInterceptor
from utils.config_registry import get_config, save_config
from models.tool_permissions_config import ToolPermissionsConfig
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tool-permissions", tags=["tool-permissions"])


class ToolPermissionResponse(BaseModel):
    permissions: Dict[str, Any]
    settings: Dict[str, Any]


class AddPermissionRequest(BaseModel):
    tool_name: str
    tool_args: Dict[str, Any] = None


class RemovePermissionRequest(BaseModel):
    pattern: str


@router.get("", response_model=ToolPermissionResponse)
async def get_tool_permissions():
    """Get the current tool permissions configuration."""
    try:
        # Use ConfigRegistry directly for better performance
        config: ToolPermissionsConfig = get_config("tool_permissions")
        return ToolPermissionResponse(
            permissions={
                "allow": config.permissions.allow,
                "deny": config.permissions.deny
            },
            settings={
                "require_justification": config.settings.require_justification,
                "audit_enabled": config.settings.audit_enabled,
                "default_secure": config.settings.default_secure
            }
        )
    except Exception as e:
        logger.error("Failed to get tool permissions", extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail=f"Failed to get tool permissions: {str(e)}")


@router.post("/add")
async def add_permission(request: AddPermissionRequest):
    """Add a tool permission to the allow list."""
    try:
        # Use ConfigRegistry directly
        config: ToolPermissionsConfig = get_config("tool_permissions")
        
        # Format pattern
        if request.tool_args:
            sorted_args = sorted(request.tool_args.items())
            args_str = ",".join(f"{k}={v}" for k, v in sorted_args)
            pattern = f"{request.tool_name}({args_str})"
        else:
            pattern = request.tool_name
        
        if pattern not in config.permissions.allow:
            config.permissions.allow.append(pattern)
            save_config("tool_permissions", config)
        
        # Clear cache to apply changes immediately
        clear_chat_agent_cache()
        
        return {"message": f"Permission added for {request.tool_name}"}
    except Exception as e:
        logger.error("Failed to add tool permission", extra={"data": {
            "tool_name": request.tool_name,
            "error": str(e)
        }})
        raise HTTPException(status_code=500, detail=f"Failed to add permission: {str(e)}")


@router.post("/remove")
async def remove_permission(request: RemovePermissionRequest):
    """Remove a tool permission pattern."""
    try:
        # Use ConfigRegistry directly
        config: ToolPermissionsConfig = get_config("tool_permissions")
        
        removed = False
        if request.pattern in config.permissions.allow:
            config.permissions.allow.remove(request.pattern)
            removed = True
        elif request.pattern in config.permissions.deny:
            config.permissions.deny.remove(request.pattern)
            removed = True
        
        if removed:
            save_config("tool_permissions", config)
            # Clear cache to apply changes immediately
            clear_chat_agent_cache()
        
        return {"message": f"Permission removed: {request.pattern}"}
    except Exception as e:
        logger.error("Failed to remove tool permission", extra={"data": {
            "pattern": request.pattern,
            "error": str(e)
        }})
        raise HTTPException(status_code=500, detail=f"Failed to remove permission: {str(e)}")


@router.post("/clear-cache")
async def clear_permissions_cache():
    """Clear the tool permissions cache to force reload."""
    try:
        clear_chat_agent_cache()
        return {"message": "Tool permissions cache cleared - will reload from config"}
    except Exception as e:
        logger.error("Failed to clear permissions cache", extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/test/{tool_name}")
async def test_permission(tool_name: str, tool_args: str = ""):
    """Test if a tool would be approved with current permissions."""
    try:
        # Parse tool_args if provided
        parsed_args = {}
        if tool_args:
            # Simple parsing for testing - in real use this would come from the tool call
            for pair in tool_args.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    parsed_args[key.strip()] = value.strip()
        
        interceptor = ToolApprovalInterceptor(permission_config)
        approved = await interceptor.check_permission(tool_name, parsed_args)
        
        return {
            "tool_name": tool_name,
            "tool_args": parsed_args,
            "approved": approved,
            "message": "Pre-approved" if approved else "Requires approval"
        }
    except Exception as e:
        logger.error("Failed to test tool permission", extra={"data": {
            "tool_name": tool_name,
            "error": str(e)
        }})
        raise HTTPException(status_code=500, detail=f"Failed to test permission: {str(e)}")