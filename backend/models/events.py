"""
Event schema definitions for Nova real-time system.
Defines consistent event types and WebSocket message formats.
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


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
        "config_changed",
        "user_profile_updated",
        "email_processing_started",
        "email_processing_completed",
        "email_settings_updated",
        "llm_settings_updated"
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
    status: str
    action: str  # "created", "updated", "status_changed", etc.
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


class UserProfileUpdatedEventData(BaseModel):
    """Data structure for user profile update events."""
    full_name: str
    email: str
    timezone: str
    notes: Optional[str] = None


class EmailSettingsUpdatedEventData(BaseModel):
    """Data structure for email settings update events."""
    enabled: bool
    polling_interval_minutes: int
    email_label_filter: str
    max_emails_per_fetch: int
    create_tasks_from_emails: bool


class LLMSettingsUpdatedEventData(BaseModel):
    """Data structure for LLM settings update events."""
    model: str
    temperature: float
    max_tokens: int


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
    status: str,
    action: str,
    source: str = "core-agent"
) -> NovaEvent:
    """Create a typed task update event."""
    return NovaEvent(
        type="task_updated",
        data=TaskUpdatedEventData(
            task_id=task_id,
            status=status,
            action=action
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


def create_user_profile_updated_event(
    full_name: str,
    email: str,
    timezone: str,
    notes: Optional[str] = None,
    source: str = "settings-service"
) -> NovaEvent:
    """Create a typed user profile update event."""
    return NovaEvent(
        type="user_profile_updated",
        data=UserProfileUpdatedEventData(
            full_name=full_name,
            email=email,
            timezone=timezone,
            notes=notes
        ).model_dump(),
        source=source
    )


def create_email_settings_updated_event(
    enabled: bool,
    polling_interval_minutes: int,
    email_label_filter: str,
    max_emails_per_fetch: int,
    create_tasks_from_emails: bool,
    source: str = "settings-service"
) -> NovaEvent:
    """Create a typed email settings update event."""
    return NovaEvent(
        type="email_settings_updated",
        data=EmailSettingsUpdatedEventData(
            enabled=enabled,
            polling_interval_minutes=polling_interval_minutes,
            email_label_filter=email_label_filter,
            max_emails_per_fetch=max_emails_per_fetch,
            create_tasks_from_emails=create_tasks_from_emails
        ).model_dump(),
        source=source
    )


def create_llm_settings_updated_event(
    model: str,
    temperature: float,
    max_tokens: int,
    source: str = "settings-service"
) -> NovaEvent:
    """Create a typed LLM settings update event."""
    return NovaEvent(
        type="llm_settings_updated",
        data=LLMSettingsUpdatedEventData(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        ).model_dump(),
        source=source
    )


 