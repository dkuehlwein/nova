"""
MCP Server Management API Endpoints

Per ADR-015, LiteLLM is the single source of truth for MCP servers.
This endpoint provides read-only access to MCP server status via LiteLLM's MCP Gateway.

Server configuration is managed in configs/litellm_config.yaml, not via this API.
"""

from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcp_client import mcp_manager
from utils.logging import get_logger

logger = get_logger("mcp-api")
router = APIRouter(prefix="/api/mcp", tags=["MCP Servers"])


class MCPServerStatus(BaseModel):
    """MCP Server status from LiteLLM."""
    name: str = Field(..., description="Server name")
    description: str = Field(..., description="Server description")
    healthy: bool = Field(..., description="Whether server is healthy")
    tools_count: int = Field(..., description="Number of available tools")
    tool_names: List[str] = Field(default_factory=list, description="List of tool names")


class MCPServersResponse(BaseModel):
    """Response for GET /api/mcp endpoint."""
    servers: List[MCPServerStatus] = Field(..., description="List of MCP servers from LiteLLM")
    total_servers: int = Field(..., description="Total number of servers")
    total_tools: int = Field(..., description="Total number of tools across all servers")
    source: str = Field(default="litellm", description="Source of MCP server registry")


@router.get("/", response_model=MCPServersResponse)
async def get_mcp_servers():
    """
    Get all MCP servers with their status from LiteLLM's MCP Gateway.

    Per ADR-015, LiteLLM is the single registry for MCP servers.
    This endpoint queries LiteLLM's /mcp-rest/tools/list and aggregates
    server information from the tool metadata.

    Returns:
        MCPServersResponse with list of servers and their tools
    """
    try:
        servers = await mcp_manager.get_mcp_servers_status()

        if not servers:
            logger.info("No MCP servers available from LiteLLM")
            return MCPServersResponse(
                servers=[],
                total_servers=0,
                total_tools=0,
                source="litellm"
            )

        response_servers = []
        total_tools = 0

        for server in servers:
            tools_count = server.get("tools_count", 0)
            total_tools += tools_count

            response_servers.append(MCPServerStatus(
                name=server["name"],
                description=server.get("description", ""),
                healthy=server.get("healthy", False),
                tools_count=tools_count,
                tool_names=server.get("tool_names", [])
            ))

        logger.info("MCP status retrieved", extra={"data": {"servers_count": len(servers), "total_tools": total_tools}})

        return MCPServersResponse(
            servers=response_servers,
            total_servers=len(servers),
            total_tools=total_tools,
            source="litellm"
        )

    except Exception as e:
        logger.error("Failed to get MCP servers status", exc_info=True, extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail=f"Failed to retrieve MCP servers: {str(e)}")


@router.get("/tools", response_model=Dict[str, Any])
async def get_mcp_tools():
    """
    Get all available MCP tools from LiteLLM's MCP Gateway.

    Returns the raw tool list from LiteLLM, useful for debugging
    and understanding what tools are available.
    """
    try:
        result = await mcp_manager.list_tools_from_litellm()
        tools = result.get("tools", [])

        return {
            "tools": tools,
            "total_tools": len(tools),
            "source": "litellm"
        }

    except Exception as e:
        logger.error("Failed to get MCP tools", exc_info=True, extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail=f"Failed to retrieve MCP tools: {str(e)}")
