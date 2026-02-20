"""
Email fetching and MCP communication for Nova.

Handles all MCP tool interactions for email retrieval.
"""
from typing import List, Dict, Any, Optional
from config import settings
from mcp_client import mcp_manager
from utils.logging import get_logger
from utils.phoenix_integration import disable_phoenix_tracing

logger = get_logger(__name__)


class EmailFetcher:
    """Handles email fetching via MCP tools."""
    
    def __init__(self):
        self.mcp_tools = None
    
    async def fetch_new_emails(self, hook_config) -> List[Dict[str, Any]]:
        """
        Fetch new emails from email provider using hook configuration.
        
        Args:
            hook_config: EmailHookConfig containing email processing settings
        
        Returns:
            List of email dictionaries
        """
        try:
            # Check if email processing is enabled in hook config
            if not hook_config.enabled:
                logger.info("Email hook is disabled")
                return []

            # Test MCP connection health - return empty if tools unavailable
            if not await self._health_check():
                logger.info(
                    "Email hook skipped - MCP tools not available",
                    extra={"data": {"hook_name": hook_config.name}}
                )
                return []
            
            # Fetch emails using MCP client
            logger.info(
                "Fetching emails from email provider via hook system",
                extra={"data": {
                    "hook_name": hook_config.name,
                    "max_results": hook_config.hook_settings.max_per_fetch,
                    "label_filter": hook_config.hook_settings.label_filter,
                    "enabled": hook_config.enabled,
                    "polling_interval": hook_config.polling_interval,
                    "create_tasks": hook_config.create_tasks
                }}
            )
            
            # Call email list_emails interface via MCP
            result = await self._call_email_tool("list_emails")
            
            if not result:
                logger.info("No messages found or invalid response from email API")
                return []
            
            # Handle different response formats from MCP tools
            messages = self._parse_message_list(result)
            
            logger.info(
                "Fetched message list from email provider via hook system",
                extra={"data": {"message_count": len(messages)}}
            )
            
            # Get full message details for new messages
            emails = []
            for message_info in messages:
                try:
                    message_id = message_info.get("id")
                    if not message_id:
                        continue
                    
                    message_result = await self._call_email_tool(
                        "get_email",
                        message_id=message_id
                    )
                    
                    if message_result:
                        emails.append(message_result)
                        
                except Exception as e:
                    logger.error(
                        "Failed to fetch individual email details via hook system",
                        extra={"data": {
                            "message_id": message_info.get("id"),
                            "hook_name": hook_config.name,
                            "error": str(e)
                        }}
                    )
                    continue
            
            # Limit results based on hook configuration
            max_emails = hook_config.hook_settings.max_per_fetch
            if len(emails) > max_emails:
                logger.info(
                    f"Limiting emails to {max_emails} (found {len(emails)})",
                    extra={"data": {"hook_name": hook_config.name, "limit": max_emails}}
                )
                emails = emails[:max_emails]
            
            logger.info(
                f"Successfully fetched {len(emails)} emails via hook system",
                extra={"data": {"hook_name": hook_config.name, "email_count": len(emails)}}
            )
            
            return emails
            
        except Exception as e:
            logger.error(
                "Failed to fetch emails via hook system",
                exc_info=True,
                extra={"data": {"hook_name": hook_config.name, "error": str(e)}}
            )
            raise
    
    
    async def _health_check(self) -> bool:
        """
        Test MCP connection health by checking available tools.

        Returns:
            True if healthy and tools available, False otherwise
        """
        try:
            tools = await self._get_email_tools()
            if not tools:
                logger.warning(
                    "No email tools available from MCP servers - email hook will be skipped",
                    extra={"data": {"available_tools": []}}
                )
                return False

            # Check for required tools
            required_tools = ["list_emails"]
            missing_tools = [t for t in required_tools if t not in tools]
            if missing_tools:
                logger.warning(
                    "Required email tools not available - email hook will be skipped",
                    extra={"data": {
                        "missing_tools": missing_tools,
                        "available_tools": list(tools.keys())
                    }}
                )
                return False

            # Quick health check by calling list_labels interface (if available)
            if "list_labels" in tools:
                await self._call_email_tool("list_labels")
                logger.debug("Email API health check passed")
            else:
                logger.debug("list_labels tool not available, skipping optional health check")

            return True

        except Exception as e:
            logger.warning(
                "Email API health check failed - email hook will be skipped",
                extra={"data": {"error": str(e)}}
            )
            return False
    
    async def _get_email_tools(self) -> Dict[str, Any]:
        """Get email-related MCP tools using configurable interface mapping.

        Uses priority-based matching: tools are matched in the order they appear
        in EMAIL_TOOL_INTERFACE, so prefixed tools (gmail_, outlook_) are preferred
        over legacy unprefixed names.
        """
        if self.mcp_tools is None:
            # Get all available MCP tools
            all_tools = await mcp_manager.get_tools()

            # Build a lookup dict of tool_name -> tool object
            tool_by_name = {getattr(tool, 'name', ''): tool for tool in all_tools}

            # Import email interface configuration
            from .interface import EMAIL_TOOL_INTERFACE

            self.mcp_tools = {}
            tool_mapping = {}

            # Map interface names to tools, respecting priority order
            # First matching tool in possible_names list wins
            for interface_name, possible_names in EMAIL_TOOL_INTERFACE.items():
                for tool_name in possible_names:
                    if tool_name in tool_by_name:
                        self.mcp_tools[interface_name] = tool_by_name[tool_name]
                        tool_mapping[interface_name] = tool_name
                        break  # Use the first matching tool (highest priority)

            logger.info(
                f"Found {len(self.mcp_tools)} email tools: {tool_mapping}",
                extra={"data": {"interface_mapping": tool_mapping}}
            )

        return self.mcp_tools
    
    async def _call_email_tool(self, tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Call an email MCP tool with the given parameters.

        Returns:
            Tool result dict, or None if tool not available
        """
        tools = await self._get_email_tools()

        if tool_name not in tools:
            logger.warning(
                f"Email tool '{tool_name}' not available",
                extra={"data": {"tool_name": tool_name, "available_tools": list(tools.keys())}}
            )
            return None
        
        tool = tools[tool_name]
        concrete_tool_name = getattr(tool, 'name', tool_name)
        
        # Map parameters based on concrete tool name
        from .interface import EMAIL_TOOL_PARAMETERS
        parameter_mapping = EMAIL_TOOL_PARAMETERS.get(concrete_tool_name, {})
        
        # Apply parameter mapping
        mapped_kwargs = {}
        for param_key, param_value in kwargs.items():
            mapped_key = parameter_mapping.get(param_key, param_key)
            mapped_kwargs[mapped_key] = param_value
        
        try:
            # Call the tool with the mapped arguments (disable tracing to prevent trace pollution)
            with disable_phoenix_tracing():
                result = await tool.arun(mapped_kwargs)
            
            # Parse the result if it's a string (some MCP tools return JSON strings)
            if isinstance(result, str):
                import json
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    # If it's not JSON, wrap it in a simple structure
                    result = {"data": result}
            
            return result
            
        except Exception as e:
            logger.error(
                f"Failed to call email tool {tool_name} (concrete: {concrete_tool_name})",
                extra={"data": {"interface_tool": tool_name, "concrete_tool": concrete_tool_name, "error": str(e), "kwargs": mapped_kwargs}}
            )
            raise
    
    def _parse_message_list(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse message list from different MCP response formats."""
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "messages" in result:
            return result["messages"]
        elif isinstance(result, dict) and "data" in result:
            return result["data"] if isinstance(result["data"], list) else []
        else:
            logger.warning("Unexpected email API response format", extra={"data": {"type": type(result)}})
            return []