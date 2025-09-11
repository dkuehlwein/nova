"""
Tool Permissions Configuration Models

Pydantic models for tool permissions configuration following Nova's patterns.
"""

from typing import List
from pydantic import BaseModel, Field


class ToolPermissionSettings(BaseModel):
    """Settings for tool permission system."""
    require_justification: bool = Field(default=True, description="Require justification for tool approvals")
    audit_enabled: bool = Field(default=True, description="Enable audit logging for tool approvals")
    default_secure: bool = Field(default=True, description="New tools require approval by default")


class ToolPermissions(BaseModel):
    """Tool permission rules."""
    allow: List[str] = Field(default_factory=list, description="Tools/patterns that are pre-approved")
    deny: List[str] = Field(default_factory=list, description="Tools/patterns that are always denied")


class ToolPermissionsConfig(BaseModel):
    """Complete tool permissions configuration."""
    permissions: ToolPermissions = Field(default_factory=ToolPermissions)
    settings: ToolPermissionSettings = Field(default_factory=ToolPermissionSettings)
    
    @staticmethod
    def get_default_config() -> 'ToolPermissionsConfig':
        """Get default secure configuration."""
        return ToolPermissionsConfig(
            permissions=ToolPermissions(
                allow=[
                    "get_tasks",
                    "search_memory", 
                    "get_task_by_id",
                    "get_memories",
                    "search_memories"
                ],
                deny=[
                    "mcp_tool(*)",
                    "update_task(status=done)",
                    "update_task(status=cancelled)"
                ]
            ),
            settings=ToolPermissionSettings(
                require_justification=True,
                audit_enabled=True,
                default_secure=True
            )
        )