"""
Tool Permissions Manager

Handles loading, caching, and managing tool permissions configuration
using Nova's ConfigRegistry system for proper path resolution and hot-reload.
"""

import logging
from typing import Dict, List, Any

from utils.config_registry import get_config, save_config
from models.tool_permissions_config import ToolPermissionsConfig

logger = logging.getLogger(__name__)


class ToolPermissionConfig:
    """Tool permission configuration manager using Nova's ConfigRegistry."""
    
    def __init__(self):
        # No path handling needed - ConfigRegistry handles environment detection
        pass
        
    async def get_permissions(self, use_cache: bool = True) -> Dict[str, Any]:
        """Get permissions using Nova's ConfigRegistry."""
        try:
            config: ToolPermissionsConfig = get_config("tool_permissions")
            # Convert Pydantic model to dict for backward compatibility
            return {
                "permissions": {
                    "allow": config.permissions.allow,
                    "deny": config.permissions.deny
                },
                "settings": {
                    "require_justification": config.settings.require_justification,
                    "audit_enabled": config.settings.audit_enabled,
                    "default_secure": config.settings.default_secure
                }
            }
        except Exception as e:
            logger.error(f"Error loading tool permissions config: {e}, using defaults")
            # Return default config if ConfigRegistry fails
            default_config = ToolPermissionsConfig.get_default_config()
            return {
                "permissions": {
                    "allow": default_config.permissions.allow,
                    "deny": default_config.permissions.deny
                },
                "settings": {
                    "require_justification": default_config.settings.require_justification,
                    "audit_enabled": default_config.settings.audit_enabled,
                    "default_secure": default_config.settings.default_secure
                }
            }
    
    async def add_permission(self, tool_name: str, tool_args: Dict[str, Any] = None):
        """Add new permission to allow list using Nova's ConfigRegistry."""
        pattern = self._format_permission_pattern(tool_name, tool_args)
        
        try:
            config: ToolPermissionsConfig = get_config("tool_permissions")
            
            if pattern not in config.permissions.allow:
                config.permissions.allow.append(pattern)
                save_config("tool_permissions", config)
                logger.info(f"Added tool permission: {pattern}")
        except Exception as e:
            logger.error(f"Failed to add tool permission {pattern}: {e}")
            raise
    
    async def remove_permission(self, pattern: str):
        """Remove permission from allow or deny list using Nova's ConfigRegistry."""
        try:
            config: ToolPermissionsConfig = get_config("tool_permissions")
            
            if pattern in config.permissions.allow:
                config.permissions.allow.remove(pattern)
                save_config("tool_permissions", config)
                logger.info(f"Removed allowed tool permission: {pattern}")
            elif pattern in config.permissions.deny:
                config.permissions.deny.remove(pattern)
                save_config("tool_permissions", config)
                logger.info(f"Removed denied tool permission: {pattern}")
        except Exception as e:
            logger.error(f"Failed to remove tool permission {pattern}: {e}")
            raise
    
    def _format_permission_pattern(self, tool_name: str, tool_args: Dict[str, Any] = None) -> str:
        """Format tool call into permission pattern string."""
        if not tool_args:
            return tool_name
        
        # Sort for consistent pattern matching
        sorted_args = sorted(tool_args.items())
        args_str = ",".join(f"{k}={v}" for k, v in sorted_args)
        return f"{tool_name}({args_str})"
    
    def get_permissions_sync(self) -> Dict[str, Any]:
        """Get permissions synchronously for use in tool initialization."""
        try:
            config: ToolPermissionsConfig = get_config("tool_permissions")
            return {
                "permissions": {
                    "allow": config.permissions.allow,
                    "deny": config.permissions.deny
                },
                "settings": {
                    "require_justification": config.settings.require_justification,
                    "audit_enabled": config.settings.audit_enabled,
                    "default_secure": config.settings.default_secure
                }
            }
        except Exception as e:
            logger.error(f"Error loading tool permissions config: {e}, using defaults")
            default_config = ToolPermissionsConfig.get_default_config()
            return {
                "permissions": {
                    "allow": default_config.permissions.allow,
                    "deny": default_config.permissions.deny
                },
                "settings": {
                    "require_justification": default_config.settings.require_justification,
                    "audit_enabled": default_config.settings.audit_enabled,
                    "default_secure": default_config.settings.default_secure
                }
            }
    
    def get_restricted_tools(self) -> List[str]:
        """Get list of tools that require approval (not in allow list)."""
        try:
            permissions = self.get_permissions_sync()
            allowed_tools = set(permissions["permissions"].get("allow", []))
            
            # For simplicity, we'll define the known tool names here
            # In a real implementation, this could be dynamic based on loaded tools
            all_known_tools = {
                "create_task", "update_task", "get_tasks", "get_task_by_id",
                "search_memory", "add_memory", "ask_user"
            }
            
            # Tools not in allow list require approval
            restricted_tools = [tool for tool in all_known_tools if tool not in allowed_tools]
            logger.debug(f"Restricted tools requiring approval: {restricted_tools}")
            return restricted_tools
            
        except Exception as e:
            logger.error(f"Error getting restricted tools: {e}")
            # Default to requiring approval for memory modification tools
            return ["add_memory", "update_task"]
    
    def clear_permissions_cache(self):
        """Clear permissions cache - delegated to ConfigRegistry hot-reload."""
        # ConfigRegistry handles hot-reload automatically via file watching
        # This method is kept for compatibility with existing cache clearing
        from utils.config_registry import reload_config
        try:
            reload_config("tool_permissions")
            logger.info("Tool permissions reloaded via ConfigRegistry")
        except Exception as e:
            logger.warning(f"Failed to reload tool permissions: {e}")


class ToolApprovalInterceptor:
    """Tool approval interceptor for checking permissions."""
    
    def __init__(self, config: ToolPermissionConfig):
        self.config = config
        
    async def check_permission(self, tool_name: str, tool_args: Dict[str, Any] = None) -> bool:
        """Check if tool call is pre-approved in config."""
        permission_string = self.config._format_permission_pattern(tool_name, tool_args)
        permissions = await self.config.get_permissions()
        
        # Check deny rules first (they override allow rules)
        deny_patterns = permissions["permissions"].get("deny", [])
        if self._matches_any_pattern(permission_string, deny_patterns):
            logger.debug(f"Tool call denied by deny rule: {permission_string}")
            return False
            
        # Check allow rules
        allow_patterns = permissions["permissions"].get("allow", [])
        allowed = self._matches_any_pattern(permission_string, allow_patterns)
        
        if allowed:
            logger.debug(f"Tool call pre-approved: {permission_string}")
        else:
            logger.debug(f"Tool call requires approval: {permission_string}")
            
        return allowed
    
    def _matches_any_pattern(self, permission_string: str, patterns: List[str]) -> bool:
        """Check if permission string matches any of the given patterns."""
        for pattern in patterns:
            if self._matches_pattern(permission_string, pattern):
                return True
        return False
    
    def _matches_pattern(self, permission_string: str, pattern: str) -> bool:
        """Check if permission string matches a specific pattern."""
        # Handle exact match
        if pattern == permission_string:
            return True
            
        # Handle wildcard patterns like "mcp_tool(*)"
        if pattern.endswith("(*)"):
            tool_name = pattern[:-3]
            return permission_string.startswith(f"{tool_name}(")
        
        # Handle tool-only patterns (no parentheses)
        if "(" not in pattern and "(" not in permission_string:
            return pattern == permission_string
        
        # Handle patterns with specific args like "update_task(status=done)"
        if pattern in permission_string:
            return True
            
        return False


# Global instance
permission_config = ToolPermissionConfig()