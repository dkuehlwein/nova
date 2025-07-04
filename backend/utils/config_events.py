"""
Unified configuration event system.
Provides standardized events for all configuration changes.
"""

from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel

from utils.logging import get_logger

logger = get_logger("config_events")


class ConfigUpdatedEvent(BaseModel):
    """Unified event for configuration updates."""
    id: str
    type: str = "config_updated"
    config_type: str  # "mcp_servers", "user_profile", "system_prompt"
    operation: str    # "updated", "validated", "backed_up", "restored", "reloaded"
    source: str       # "config-api", "file-watcher", "user-action", "manual"
    details: Dict[str, Any]
    timestamp: datetime


def create_config_event(
    config_type: str,
    operation: str,
    source: str,
    details: Dict[str, Any]
) -> ConfigUpdatedEvent:
    """Create a standardized configuration event."""
    timestamp = datetime.now()
    event_id = f"config_{config_type}_{operation}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
    
    return ConfigUpdatedEvent(
        id=event_id,
        config_type=config_type,
        operation=operation,
        source=source,
        details=details,
        timestamp=timestamp
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
            f"Configuration event published: {config_type}/{operation}",
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
            f"Failed to publish config event: {config_type}/{operation}",
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