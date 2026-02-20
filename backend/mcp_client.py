"""
MCP Client Manager - Interfaces with LiteLLM's MCP Gateway.

Per ADR-015, LiteLLM is the single source of truth for MCP servers and tools.
Nova queries LiteLLM's /mcp-rest/tools/list endpoint for tool discovery.
"""

import json
import time

import httpx
from typing import List, Dict, Any, Optional
from langchain_core.tools import StructuredTool
from pydantic import create_model
from config import settings
from utils.logging import get_logger

logger = get_logger("mcp-client")

# Cache settings for MCP tools
_TOOLS_CACHE_TTL_SECONDS = 60  # Cache tools for 60 seconds to reduce MCP server load


def get_prefixed_tool_name(server_name: str, tool_name: str) -> str:
    """Return 'server_name-tool_name' for unique tool names across MCP servers (ADR-015)."""
    return f"{server_name}-{tool_name}"


class MCPClientManager:
    """Manages MCP tool discovery via LiteLLM's MCP Gateway.

    LiteLLM is the single registry for all MCP servers (ADR-015).
    This manager queries LiteLLM to discover available tools and
    converts them to LangChain tools for agent use.
    """

    def __init__(self):
        self._litellm_base_url = settings.LITELLM_BASE_URL
        self._litellm_api_key = settings.LITELLM_MASTER_KEY
        # Cache for LangChain tools to reduce MCP server load
        self._tools_cache: Optional[List[Any]] = None
        self._tools_cache_timestamp: float = 0
        # Cache for server_name -> server_id mapping
        self._server_id_cache: Dict[str, str] = {}

    async def list_tools_from_litellm(self, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Query LiteLLM's MCP Gateway for all available tools.

        Returns:
            Dict with 'tools' list from LiteLLM or empty on failure
        """
        url = f"{self._litellm_base_url}/mcp-rest/tools/list"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self._litellm_api_key}"},
                    timeout=timeout
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException:
            logger.warning("Timeout fetching tools from LiteLLM MCP Gateway")
            return {"tools": []}
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error from LiteLLM MCP Gateway", extra={"data": {"status_code": e.response.status_code}})
            return {"tools": []}
        except Exception as e:
            logger.error("Error fetching tools from LiteLLM", extra={"data": {"error": str(e)}})
            return {"tools": []}

    async def get_mcp_servers_status(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """
        Get MCP server status by aggregating info from LiteLLM's tool list.

        Groups tools by server (via mcp_info) and returns server-level status.
        """
        result = await self.list_tools_from_litellm(timeout)
        tools = result.get("tools", [])

        if not tools:
            return []

        # Group tools by server
        servers: Dict[str, Dict[str, Any]] = {}

        for tool in tools:
            mcp_info = tool.get("mcp_info", {})
            server_name = mcp_info.get("server_name", "unknown")

            if server_name not in servers:
                servers[server_name] = {
                    "name": server_name,
                    "description": mcp_info.get("description", ""),
                    "tools_count": 0,
                    "healthy": True,  # If we got tools, server is healthy
                    "enabled": True,  # LiteLLM only returns enabled servers
                    "tool_names": []
                }

            servers[server_name]["tools_count"] += 1
            servers[server_name]["tool_names"].append(tool.get("name", "unknown"))

        return list(servers.values())

    async def check_server_health_and_get_tools_count(
        self,
        server_info: Dict[str, Any],
        timeout: float = 5.0
    ) -> tuple[bool, Optional[int]]:
        """
        Check if a specific MCP server is healthy via LiteLLM.

        Since LiteLLM manages server connections, we check if the server
        appears in the tools list with tools.
        """
        server_name = server_info.get("name", "unknown")

        servers_status = await self.get_mcp_servers_status(timeout)

        for server in servers_status:
            if server["name"] == server_name:
                return True, server["tools_count"]

        # Server not found in LiteLLM - either unhealthy or not configured
        logger.debug("Server not found in LiteLLM MCP Gateway", extra={"data": {"server_name": server_name}})
        return False, None

    async def discover_working_servers(self) -> List[Dict[str, Any]]:
        """Discover working MCP servers from LiteLLM."""
        servers = await self.get_mcp_servers_status()

        if not servers:
            logger.warning("No MCP servers available from LiteLLM")
            return []

        logger.info("Found MCP servers via LiteLLM", extra={"data": {"servers_count": len(servers)}})
        return servers

    def _resolve_json_schema_type(self, prop_schema: Dict[str, Any]) -> tuple:
        """Resolve a JSON Schema property to a Python type, handling anyOf/oneOf.

        Returns (python_type, nullable) tuple.
        """
        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        # Direct type
        if "type" in prop_schema:
            return type_mapping.get(prop_schema["type"], str), False

        # anyOf / oneOf: pick the first non-null type, track if null is allowed
        for key in ("anyOf", "oneOf"):
            variants = prop_schema.get(key, [])
            if not variants:
                continue
            resolved_type = str
            nullable = False
            for variant in variants:
                vtype = variant.get("type")
                if vtype == "null":
                    nullable = True
                elif vtype:
                    resolved_type = type_mapping.get(vtype, str)
            return resolved_type, nullable

        return str, False

    def _convert_json_schema_to_pydantic_fields(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert JSON Schema properties to Pydantic field definitions."""
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        fields = {}

        for prop_name, prop_schema in properties.items():
            python_type, nullable = self._resolve_json_schema_type(prop_schema)

            if nullable:
                python_type = Optional[python_type]

            default = prop_schema.get("default", ...)
            if prop_name not in required and default == ...:
                default = None
                if not nullable:
                    python_type = Optional[python_type]

            fields[prop_name] = (python_type, default)

        return fields

    async def get_server_id_by_name(self, server_name: str) -> Optional[str]:
        """
        Look up the server UUID by server name.

        LiteLLM requires server_id (UUID) for API calls, not server_name.
        This fetches the server list and finds the matching server.
        Results are cached to avoid repeated API calls.

        Args:
            server_name: The server name (e.g., "ms_graph")

        Returns:
            The server UUID or None if not found
        """
        # Check cache first
        if server_name in self._server_id_cache:
            return self._server_id_cache[server_name]

        url = f"{self._litellm_base_url}/v1/mcp/server"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self._litellm_api_key}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    servers = response.json()
                    # Update cache with all servers
                    for server in servers:
                        name = server.get("server_name")
                        alias = server.get("alias")
                        sid = server.get("server_id")
                        if name and sid:
                            self._server_id_cache[name] = sid
                        if alias and sid:
                            self._server_id_cache[alias] = sid
                    # Return the requested server
                    return self._server_id_cache.get(server_name)
                return None
        except Exception as e:
            logger.warning("Failed to look up server_id", extra={"data": {"server_name": server_name, "error": str(e)}})
            return None

    def _parse_auth_error(self, tool_result: Any) -> Optional[str]:
        """Return the auth_url if tool_result indicates MS Graph auth is required, else None."""
        if isinstance(tool_result, str):
            try:
                tool_result = json.loads(tool_result)
            except (json.JSONDecodeError, ValueError):
                return None

        if isinstance(tool_result, dict) and tool_result.get("auth_required"):
            return tool_result.get("auth_url")
        return None

    async def _execute_mcp_call(
        self,
        url: str,
        prefixed_tool_name: str,
        arguments: Dict[str, Any],
        server_id: str,
    ) -> Any:
        """Execute a single MCP tool call and return the parsed result."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._litellm_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "name": prefixed_tool_name,
                    "arguments": arguments,
                    "server_id": server_id
                },
                timeout=60.0  # Tool calls may take longer
            )
            response.raise_for_status()
            result = response.json()

            # Extract text from the first content block of the MCP response
            content = result.get("content")
            if content and isinstance(content, list):
                first = content[0]
                if isinstance(first, dict) and "text" in first:
                    return first["text"]
                return first

            return result

    async def call_mcp_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Execute an MCP tool via LiteLLM's MCP Gateway.

        If the tool returns an auth_required error (NOV-122), automatically
        launches a browser to complete the OAuth flow and retries the call.

        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        url = f"{self._litellm_base_url}/mcp-rest/tools/call"

        # LiteLLM requires server_id (UUID), not server_name
        # Try to look up the UUID, fall back to using name directly
        server_id = await self.get_server_id_by_name(server_name)
        if not server_id:
            logger.warning("Could not find server_id for , using name directly", extra={"data": {"server_name": server_name}})
            server_id = server_name

        # LiteLLM routes tool calls by tool name (not server_id).
        # Must use prefixed name (server_name-tool_name) so LiteLLM routes
        # to the correct MCP server when multiple servers share tool names.
        prefixed_tool_name = get_prefixed_tool_name(server_name, tool_name)

        try:
            result = await self._execute_mcp_call(
                url, prefixed_tool_name, arguments, server_id
            )

            # Auto-authenticate on MS Graph auth errors (NOV-123)
            auth_url = self._parse_auth_error(result)
            if auth_url:
                logger.info("MS Graph auth required for , launching browser auth", extra={"data": {"tool_name": tool_name}})
                from utils.ms_graph_auth_browser import authenticate_ms_graph

                auth_result = await authenticate_ms_graph(auth_url)
                if auth_result.get("success"):
                    logger.info("MS Graph auth succeeded, retrying", extra={"data": {"tool_name": tool_name}})
                    return await self._execute_mcp_call(
                        url, prefixed_tool_name, arguments, server_id
                    )
                logger.warning("MS Graph auto-auth failed", extra={"data": {"auth_result": auth_result.get('error')}})

            return result

        except httpx.TimeoutException:
            logger.error("Timeout calling MCP tool", extra={"data": {"tool_name": tool_name, "server_name": server_name}})
            return {"error": f"Timeout calling tool {tool_name}"}
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling MCP tool", extra={"data": {"status_code": e.response.status_code, "text": e.response.text}})
            return {"error": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            logger.error("Error calling MCP tool", extra={"data": {"tool_name": tool_name, "error": str(e)}})
            return {"error": str(e)}

    async def get_tools(self, force_refresh: bool = False) -> List[Any]:
        """
        Get LangChain-compatible tools from LiteLLM's MCP Gateway.

        Fetches all tools from LiteLLM and converts them to LangChain
        StructuredTool objects that can be bound to the agent.

        Uses a cache with TTL to reduce load on MCP servers - each call to
        list_tools causes LiteLLM to connect to all MCP servers.

        Args:
            force_refresh: If True, bypass cache and fetch fresh tools
        """
        # Check cache first (unless force refresh requested)
        current_time = time.time()
        cache_age = current_time - self._tools_cache_timestamp

        if not force_refresh and self._tools_cache is not None and cache_age < _TOOLS_CACHE_TTL_SECONDS:
            logger.debug(
                f"Using cached MCP tools (age: {cache_age:.1f}s, TTL: {_TOOLS_CACHE_TTL_SECONDS}s)"
            )
            return self._tools_cache

        logger.info("Fetching MCP tools from LiteLLM")

        result = await self.list_tools_from_litellm()
        tools_data = result.get("tools", [])

        if not tools_data:
            logger.info("No MCP tools available from LiteLLM")
            return []

        langchain_tools = []

        for tool_data in tools_data:
            try:
                tool_name = tool_data.get("name")
                description = tool_data.get("description", "No description")
                input_schema = tool_data.get("inputSchema", {})
                mcp_info = tool_data.get("mcp_info", {})
                server_name = mcp_info.get("server_name", "unknown")

                # Create Pydantic model for the tool's input schema
                fields = self._convert_json_schema_to_pydantic_fields(input_schema)

                if fields:
                    ArgsModel = create_model(f"{tool_name}Args", **fields)
                else:
                    ArgsModel = create_model(f"{tool_name}Args")

                # Create prefixed tool name for uniqueness across MCP servers
                prefixed_name = get_prefixed_tool_name(server_name, tool_name)

                # Create a closure to capture server_name and original tool_name
                # call_mcp_tool handles prefixing internally for LiteLLM routing
                def make_tool_func(srv_name: str, original_tool_name: str):
                    async def tool_func(**kwargs) -> str:
                        result = await self.call_mcp_tool(srv_name, original_tool_name, kwargs)
                        if isinstance(result, dict):
                            import json
                            return json.dumps(result)
                        return str(result)
                    return tool_func

                tool = StructuredTool.from_function(
                    coroutine=make_tool_func(server_name, tool_name),
                    name=prefixed_name,  # Use prefixed name for LangChain
                    description=description,  # Server name is now in the tool name
                    args_schema=ArgsModel,
                    return_direct=False
                )

                langchain_tools.append(tool)

            except Exception as e:
                logger.warning("Failed to convert MCP tool", extra={"data": {"tool_data": tool_data.get('name', 'unknown'), "error": str(e)}})
                continue

        # Update cache
        self._tools_cache = langchain_tools
        self._tools_cache_timestamp = current_time

        logger.info("Successfully loaded MCP tools from LiteLLM (cached for s", extra={"data": {"langchain_tools_count": len(langchain_tools), "_TOOLS_CACHE_TTL_SECONDS": _TOOLS_CACHE_TTL_SECONDS}})
        return langchain_tools

    def clear_tools_cache(self):
        """Clear the tools cache to force a refresh on next get_tools() call."""
        self._tools_cache = None
        self._tools_cache_timestamp = 0
        logger.info("MCP tools cache cleared")


# Global instance for reuse
mcp_manager = MCPClientManager()
