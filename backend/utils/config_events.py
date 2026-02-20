"""
Unified configuration event system.
Provides standardized events for all configuration changes.

Uses the NovaEvent model from models/events.py with type="config_changed"
to ensure compatibility with the Redis pub/sub system.
"""

from datetime import datetime
from typing import Dict, Any

from models.events import NovaEvent
from utils.logging import get_logger

logger = get_logger("config_events")


def create_config_event(
    config_type: str,
    operation: str,
    source: str,
    details: Dict[str, Any]
) -> NovaEvent:
    """Create a standardized configuration event using NovaEvent.

    Args:
        config_type: Type of config ("mcp_servers", "user_profile", "system_prompt", "tool_permissions")
        operation: Operation performed ("updated", "validated", "backed_up", "restored", "reloaded")
        source: Source of the change ("config-api", "file-watcher", "user-action", "manual")
        details: Additional details about the change

    Returns:
        NovaEvent with type="config_changed"
    """
    return NovaEvent(
        type="config_changed",
        data={
            "config_type": config_type,
            "operation": operation,
            "details": details
        },
        source=source
    )


async def publish_config_event(
    config_type: str,
    operation: str,
    source: str,
    details: Dict[str, Any]
) -> None:
    """Publish a standardized configuration event."""
    try:
        from utils.redis_manager import publish
        
        event = create_config_event(config_type, operation, source, details)
        await publish(event)
        
        logger.info(
            "Configuration event published",
            extra={
                "data": {
                    "event_id": event.id,
                    "config_type": config_type,
                    "operation": operation,
                    "source": source
                }
            }
        )
        
    except Exception as e:
        logger.error(
            "Failed to publish config event",
            exc_info=True,
            extra={
                "data": {
                    "config_type": config_type,
                    "operation": operation,
                    "source": source,
                    "error": str(e)
                }
            }
        ) 