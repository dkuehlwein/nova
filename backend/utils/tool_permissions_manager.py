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
    
    # Field names that are always dynamic/user-specific (filter by name)
    IGNORED_FIELD_NAMES = {
        "id", "task_id", "uuid", "execution_id", "thread_id", "run_id",
        "email", "username", "user_id", "user_identifier", "display_name",
        "name", "title", "description", "content", "body", "message",
        "password", "token", "secret", "key", "api_key",
    }

    # Enum-like values that represent operation types (keep these)
    SEMANTIC_ARG_PATTERNS = {
        "status", "type", "action", "mode", "state", "priority", "level",
        "category", "kind", "role", "permission", "access", "visibility",
    }

    def _is_semantic_value(self, key: str, value: Any) -> bool:
        """Determine if an argument represents a semantic operation type vs user data.

        Returns True for values that define the "type" of operation:
        - Boolean flags
        - Short enum-like strings (e.g., "done", "in_progress", "high")
        - Arguments with semantic field names (status, type, mode, etc.)

        Returns False for user-specific data:
        - Emails, URLs, long text
        - Arguments with user-data field names (email, name, etc.)
        """
        key_lower = key.lower()

        # Always filter out known user-data fields
        if key_lower in self.IGNORED_FIELD_NAMES:
            return False

        # Always keep known semantic fields
        if key_lower in self.SEMANTIC_ARG_PATTERNS:
            return True

        # Analyze the value itself
        if isinstance(value, bool):
            return True  # Booleans are semantic flags

        if isinstance(value, (int, float)):
            return True  # Numbers are usually semantic (limits, counts, etc.)

        if isinstance(value, str):
            # Filter out empty or whitespace-only strings
            if not value or not value.strip():
                return False
            # Filter out obvious user data patterns
            if "@" in value:  # Email
                return False
            if value.startswith(("http://", "https://")):  # URLs
                return False
            if len(value) > 30:  # Long text is likely user content
                return False
            if " " in value and len(value) > 15:  # Multi-word long strings
                return False
            # Short strings without spaces are likely enum values
            return True

        # Filter out complex types (lists, dicts)
        if isinstance(value, (list, dict)):
            return False

        return False

    async def add_permission(self, tool_name: str, tool_args: Dict[str, Any] = None):
        """Add new permission to allow list using Nova's ConfigRegistry.

        Filters tool_args to keep only semantic arguments (status, type, mode, etc.)
        while removing user-specific data (emails, names, long text).
        This creates permissions like "update_task(status=done)" instead of
        overly specific ones with user data.
        """
        # Filter to keep only semantic arguments
        semantic_args = None
        if tool_args:
            semantic_args = {
                k: v for k, v in tool_args.items()
                if self._is_semantic_value(k, v)
            }
            # If no semantic args remain, use None (just tool name)
            if not semantic_args:
                semantic_args = None

        pattern = self._format_permission_pattern(tool_name, semantic_args)

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
    
    def _format_permission_pattern(self, tool_name: str, tool_args: Dict[str, Any] | None = None) -> str:
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
    
    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is explicitly allowed (doesn't require approval).

        With default_secure=true, tools NOT in the allow list require approval.
        Tools in the deny list are always blocked (require approval that will be denied).
        """
        try:
            permissions = self.get_permissions_sync()
            allow_patterns = permissions["permissions"].get("allow", [])
            deny_patterns = permissions["permissions"].get("deny", [])
            default_secure = permissions["settings"].get("default_secure", True)

            # Check deny list first - denied tools always require approval
            for pattern in deny_patterns:
                if self._matches_tool_pattern(tool_name, pattern):
                    logger.debug(f"Tool {tool_name} is in deny list")
                    return False

            # Check allow list
            for pattern in allow_patterns:
                if self._matches_tool_pattern(tool_name, pattern):
                    logger.debug(f"Tool {tool_name} is explicitly allowed")
                    return True

            # If default_secure is True, tools not in allow list require approval
            if default_secure:
                logger.debug(f"Tool {tool_name} not in allow list, default_secure=True, requires approval")
                return False

            # default_secure is False - allow by default
            return True

        except Exception as e:
            logger.error(f"Error checking tool permission for {tool_name}: {e}")
            # Fail secure - require approval on error
            return False

    def _matches_tool_pattern(self, tool_name: str, pattern: str) -> bool:
        """Check if a tool name matches a permission pattern.

        Supports:
        - Exact match: "send_email"
        - Wildcard suffix: "mcp_tool(*)" matches any mcp_tool call
        - Prefix wildcard: "_example_skill__*" matches _example_skill__foo, _example_skill__bar
        """
        # Exact match
        if pattern == tool_name:
            return True

        # Wildcard suffix pattern like "tool_name(*)"
        if pattern.endswith("(*)") and tool_name == pattern[:-3]:
            return True

        # Prefix wildcard pattern like "prefix_*"
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            if tool_name.startswith(prefix):
                return True

        return False

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
        if self._matches_any_pattern(tool_name, tool_args, deny_patterns):
            logger.debug(f"Tool call denied by deny rule: {permission_string}")
            return False
            
        # Check allow rules
        allow_patterns = permissions["permissions"].get("allow", [])
        allowed = self._matches_any_pattern(tool_name, tool_args, allow_patterns)
        
        if allowed:
            logger.debug(f"Tool call pre-approved: {permission_string}")
        else:
            logger.debug(f"Tool call requires approval: {permission_string}")
            
        return allowed
    
    def _matches_any_pattern(self, tool_name: str, tool_args: Dict[str, Any], patterns: List[str]) -> bool:
        """Check if permission string matches any of the given patterns."""
        for pattern in patterns:
            if self._matches_pattern(tool_name, tool_args, pattern):
                return True
        return False
    
    def _matches_pattern(self, tool_name: str, tool_args: Dict[str, Any], pattern: str) -> bool:
        """Check if tool call matches a specific pattern."""
        # 1. Exact match with formatted string
        permission_string = self.config._format_permission_pattern(tool_name, tool_args)
        if pattern == permission_string:
            return True
            
        # 2. Wildcard pattern "ToolName(*)"
        if pattern == f"{tool_name}(*)":
            return True
            
        # 3. Tool name only "ToolName"
        if pattern == tool_name:
            return True
        
        # 4. Subset argument matching
        # If the pattern is for this tool, check if required args are present and match
        if pattern.startswith(f"{tool_name}("):
            try:
                # Extract args string: "key1=val1,key2=val2"
                args_content = pattern[len(tool_name)+1:-1]
                if not args_content:
                    return True # Empty args pattern matches
                
                # Split pairs
                # Note: This simple split fails for values containing commas. 
                # But it improves upon the previous substring matching significantly.
                pairs = args_content.split(',')
                
                tool_args_str = {k: str(v) for k, v in (tool_args or {}).items()}
                
                for pair in pairs:
                    if '=' not in pair:
                        continue
                    k, v = pair.split('=', 1)
                    k = k.strip()
                    v = v.strip()
                    
                    # If pattern requires a key that is missing or different
                    if k not in tool_args_str or tool_args_str[k] != v:
                        return False
                
                # If all required pairs matched
                return True
            except Exception:
                pass

        # 5. Legacy/Fallback: Substring match for backward compatibility and complex cases
        if pattern in permission_string:
            return True
            
        return False


# Global instance
permission_config = ToolPermissionConfig()