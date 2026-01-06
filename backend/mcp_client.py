"""
MCP Client Manager - Interfaces with LiteLLM's MCP Gateway.

Per ADR-015, LiteLLM is the single source of truth for MCP servers and tools.
Nova queries LiteLLM's /mcp-rest/tools/list endpoint for tool discovery.
"""

import asyncio
import httpx
from typing import List, Dict, Any, Optional
from langchain_core.tools import StructuredTool
from pydantic import create_model
from config import settings
from utils.logging import get_logger

logger = get_logger("mcp-client")


class MCPClientManager:
    """Manages MCP tool discovery via LiteLLM's MCP Gateway.

    LiteLLM is the single registry for all MCP servers (ADR-015).
    This manager queries LiteLLM to discover available tools and
    converts them to LangChain tools for agent use.
    """

    def __init__(self):
        self._litellm_base_url = settings.LITELLM_BASE_URL
        self._litellm_api_key = settings.LITELLM_MASTER_KEY

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
            logger.warning(f"Timeout fetching tools from LiteLLM MCP Gateway")
            return {"tools": []}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from LiteLLM MCP Gateway: {e.response.status_code}")
            return {"tools": []}
        except Exception as e:
            logger.error(f"Error fetching tools from LiteLLM: {e}")
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
        logger.debug(f"Server {server_name} not found in LiteLLM MCP Gateway")
        return False, None

    async def discover_working_servers(self) -> List[Dict[str, Any]]:
        """Discover working MCP servers from LiteLLM."""
        servers = await self.get_mcp_servers_status()

        if not servers:
            logger.warning("No MCP servers available from LiteLLM")
            return []

        logger.info(f"Found {len(servers)} MCP servers via LiteLLM")
        return servers

    def _convert_json_schema_to_pydantic_fields(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert JSON Schema properties to Pydantic field definitions."""
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        fields = {}

        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict
        }

        for prop_name, prop_schema in properties.items():
            prop_type = prop_schema.get("type", "string")
            python_type = type_mapping.get(prop_type, str)

            default = prop_schema.get("default", ...)
            if prop_name not in required and default == ...:
                default = None
                python_type = Optional[python_type]

            fields[prop_name] = (python_type, default)

        return fields

    async def call_mcp_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Execute an MCP tool via LiteLLM's MCP Gateway.

        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        url = f"{self._litellm_base_url}/mcp-rest/tools/call"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._litellm_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "name": tool_name,
                        "arguments": arguments,
                        "mcp_server": server_name
                    },
                    timeout=60.0  # Tool calls may take longer
                )
                response.raise_for_status()
                result = response.json()

                # Extract content from MCP response
                content = result.get("content", [])
                if content and isinstance(content, list) and len(content) > 0:
                    # Return the text content from the first content block
                    first_content = content[0]
                    if isinstance(first_content, dict) and "text" in first_content:
                        return first_content["text"]
                    return first_content

                return result

        except httpx.TimeoutException:
            logger.error(f"Timeout calling MCP tool {tool_name} on {server_name}")
            return {"error": f"Timeout calling tool {tool_name}"}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling MCP tool: {e.response.status_code} - {e.response.text}")
            return {"error": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            return {"error": str(e)}

    async def get_tools(self) -> List[Any]:
        """
        Get LangChain-compatible tools from LiteLLM's MCP Gateway.

        Fetches all tools from LiteLLM and converts them to LangChain
        StructuredTool objects that can be bound to the agent.
        """
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

                # Create a closure to capture server_name and tool_name
                def make_tool_func(srv_name: str, tl_name: str):
                    async def tool_func(**kwargs) -> str:
                        result = await self.call_mcp_tool(srv_name, tl_name, kwargs)
                        if isinstance(result, dict):
                            import json
                            return json.dumps(result)
                        return str(result)
                    return tool_func

                tool = StructuredTool.from_function(
                    coroutine=make_tool_func(server_name, tool_name),
                    name=tool_name,
                    description=f"[{server_name}] {description}",
                    args_schema=ArgsModel,
                    return_direct=False
                )

                langchain_tools.append(tool)

            except Exception as e:
                logger.warning(f"Failed to convert MCP tool {tool_data.get('name', 'unknown')}: {e}")
                continue

        logger.info(f"Successfully loaded {len(langchain_tools)} MCP tools from LiteLLM")
        return langchain_tools


# Global instance for reuse
mcp_manager = MCPClientManager()
