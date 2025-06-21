"""
Nova MCP Domain Models

Modern Pydantic V2 models for MCP server-related API endpoints.
All models follow latest Pydantic V2 patterns with proper validation and serialization.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class MCPServerStatus(BaseModel):
    """MCP Server with health status information."""
    name: str = Field(..., description="Server name")
    url: str = Field(..., description="Server URL")
    health_url: Optional[str] = Field(None, description="Optional health check URL (uses MCP tools/list if not provided)")
    description: str = Field(..., description="Server description")
    enabled: bool = Field(..., description="Whether server is enabled")
    healthy: bool = Field(..., description="Whether server is healthy")
    tools_count: Optional[int] = Field(None, description="Number of available tools")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class MCPServersResponse(BaseModel):
    """Response for GET /api/mcp endpoint."""
    servers: List[MCPServerStatus] = Field(..., description="List of MCP servers")
    total_servers: int = Field(..., description="Total number of servers")
    healthy_servers: int = Field(..., description="Number of healthy servers")
    enabled_servers: int = Field(..., description="Number of enabled servers")


class MCPToggleRequest(BaseModel):
    """Request body for toggling MCP server status."""
    enabled: bool = Field(..., description="Whether to enable or disable the server")


class MCPToggleResponse(BaseModel):
    """Response for MCP server toggle operations."""
    server_name: str = Field(..., description="Name of the toggled server")
    enabled: bool = Field(..., description="New enabled status")
    message: str = Field(..., description="Human-readable status message") 