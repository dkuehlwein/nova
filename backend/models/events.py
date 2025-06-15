"""
Event schema definitions for Nova real-time system.
Defines consistent event types and WebSocket message formats.
"""

from datetime import datetime
from typing import Any, Dict, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class NovaEvent(BaseModel):
    """
    Standard event format for Nova's real-time system.
    All events published through Redis should use this format.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal[
        "mcp_toggled",
        "prompt_updated", 
        "task_updated",
        "system_health",
        "config_validated",
        "config_changed"
    ]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]
    source: str  # service name that generated the event


class WebSocketMessage(BaseModel):
    """
    WebSocket message format sent to frontend clients.
    Converts NovaEvent to wire format with ISO timestamp.
    """
    id: str
    type: str
    timestamp: str  # ISO format string
    data: Dict[str, Any]
    source: str
    
    @classmethod
    def from_nova_event(cls, event: NovaEvent) -> "WebSocketMessage":
        """Convert a NovaEvent to WebSocket message format."""
        return cls(
            id=event.id,
            type=event.type,
            timestamp=event.timestamp.isoformat(),
            data=event.data,
            source=event.source
        )


# Specific event data models for type safety
class MCPToggledEventData(BaseModel):
    """Data structure for MCP server toggle events."""
    server_name: str
    enabled: bool
    user_action: bool = True


class PromptUpdatedEventData(BaseModel):
    """Data structure for prompt update events."""
    prompt_file: str
    change_type: Literal["modified", "created", "deleted"]


class TaskUpdatedEventData(BaseModel):
    """Data structure for task update events."""
    task_id: str
    previous_lane: str
    new_lane: str
    agent_action: bool = True


class SystemHealthEventData(BaseModel):
    """Data structure for system health events."""
    component: str
    status: Literal["healthy", "degraded", "unhealthy"]
    details: Dict[str, Any]


class ConfigValidatedEventData(BaseModel):
    """Data structure for configuration validation events."""
    config_type: str
    valid: bool
    errors: list[str] = []


# Helper functions for creating typed events
def create_mcp_toggled_event(
    server_name: str, 
    enabled: bool, 
    source: str = "settings-service"
) -> NovaEvent:
    """Create a typed MCP toggle event."""
    return NovaEvent(
        type="mcp_toggled",
        data=MCPToggledEventData(
            server_name=server_name,
            enabled=enabled
        ).model_dump(),
        source=source
    )


def create_prompt_updated_event(
    prompt_file: str,
    change_type: Literal["modified", "created", "deleted"],
    source: str = "settings-service"
) -> NovaEvent:
    """Create a typed prompt update event."""
    return NovaEvent(
        type="prompt_updated",
        data=PromptUpdatedEventData(
            prompt_file=prompt_file,
            change_type=change_type
        ).model_dump(),
        source=source
    )


def create_task_updated_event(
    task_id: str,
    previous_lane: str,
    new_lane: str,
    source: str = "core-agent"
) -> NovaEvent:
    """Create a typed task update event."""
    return NovaEvent(
        type="task_updated",
        data=TaskUpdatedEventData(
            task_id=task_id,
            previous_lane=previous_lane,
            new_lane=new_lane
        ).model_dump(),
        source=source
    )


def create_system_health_event(
    component: str,
    status: Literal["healthy", "degraded", "unhealthy"],
    details: Dict[str, Any],
    source: str = "health-monitor"
) -> NovaEvent:
    """Create a typed system health event."""
    return NovaEvent(
        type="system_health",
        data=SystemHealthEventData(
            component=component,
            status=status,
            details=details
        ).model_dump(),
        source=source
    )


def create_config_validated_event(
    config_type: str,
    valid: bool,
    errors: list[str] = None,
    source: str = "settings-service"
) -> NovaEvent:
    """Create a typed configuration validation event."""
    return NovaEvent(
        type="config_validated",
        data=ConfigValidatedEventData(
            config_type=config_type,
            valid=valid,
            errors=errors or []
        ).model_dump(),
        source=source
    ) 