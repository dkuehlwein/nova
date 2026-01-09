"""
Nova System Domain Models

Modern Pydantic V2 models for system-related API endpoints.
All models follow latest Pydantic V2 patterns with proper validation and serialization.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ServiceRestartResponse(BaseModel):
    """Response for service restart operations."""
    service_name: str = Field(..., description="Name of the restarted service")
    status: str = Field(..., description="Restart status (success or error)")
    message: str = Field(..., description="Human-readable status message")
    stdout: str = Field(..., description="Standard output from restart command")
    stderr: str = Field(..., description="Standard error from restart command")
    exit_code: int = Field(..., description="Exit code from restart command")


class SystemHealthSummary(BaseModel):
    """System health summary for navbar display."""
    overall_status: str = Field(..., description="Overall system status (operational, degraded, critical)")
    chat_agent_status: str = Field(..., description="Chat agent health status")
    core_agent_status: str = Field(..., description="Core agent health status") 
    mcp_servers_healthy: int = Field(..., description="Number of healthy MCP servers")
    mcp_servers_total: int = Field(..., description="Total number of enabled MCP servers")
    database_status: str = Field(..., description="Database health status") 