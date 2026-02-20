"""
Unified Event Handlers for Nova Services

Provides DRY event handling functions for chat agent and core agent services.
"""

from typing import Callable, Optional
from utils.logging import get_logger

logger = get_logger("event-handlers")


def create_unified_event_handler(
    service_name: str,
    reload_agent_func: Optional[Callable] = None,
    clear_cache_func: Optional[Callable] = None,
    websocket_broadcast_func: Optional[Callable] = None
):
    """Create a unified event handler for Nova services.
    
    Args:
        service_name: Name of the service (for logging)
        reload_agent_func: Optional function to reload the agent
        clear_cache_func: Optional function to clear caches (chat agent only)
        websocket_broadcast_func: Optional function to broadcast events via WebSocket
        
    Returns:
        Async event handler function
    """
    
    async def unified_event_handler(event):
        """Unified event handler for prompt and LLM settings updates."""
        try:
            # Always broadcast to WebSocket clients if function is provided
            if websocket_broadcast_func:
                await websocket_broadcast_func(event)
            
            if event.type == "prompt_updated":
                logger.info(
                    "Prompt updated, reloading agent",
                    extra={
                        "data": {
                            "event_id": event.id,
                            "service": service_name,
                            "prompt_file": event.data.get('prompt_file'),
                            "source": getattr(event, 'source', 'unknown')
                        }
                    }
                )
                
                # Clear cache if provided (for chat agent)
                if clear_cache_func:
                    clear_cache_func()
                    logger.info("Cache cleared, using updated prompt", extra={"data": {"service": service_name}})
                elif reload_agent_func:
                    # For core agent, reload directly
                    await reload_agent_func()
                    logger.info("Agent reloaded with updated prompt", extra={"data": {"service": service_name}})
                
            elif event.type == "llm_settings_updated":
                logger.info(
                    "LLM settings updated, reloading agent",
                    extra={
                        "data": {
                            "event_id": event.id,
                            "service": service_name,
                            "model": event.data.get('model'),
                            "provider": event.data.get('provider'),
                            "temperature": event.data.get('temperature'),
                            "max_tokens": event.data.get('max_tokens'),
                            "source": getattr(event, 'source', 'unknown')
                        }
                    }
                )
                
                # Clear cache if provided (for chat agent)
                if clear_cache_func:
                    clear_cache_func()
                    logger.info("Cache cleared, using updated LLM settings", extra={"data": {"service": service_name}})
                elif reload_agent_func:
                    # For core agent, reload directly
                    await reload_agent_func()
                    logger.info("Agent reloaded with updated LLM settings", extra={"data": {"service": service_name}})
                    
            elif event.type == "mcp_toggled":
                if service_name == "chat-agent":  # Only chat agent handles MCP toggles
                    logger.info(
                        "MCP server toggled, reloading agent",
                        extra={
                            "data": {
                                "event_id": event.id,
                                "service": service_name,
                                "server_name": event.data.get('server_name'),
                                "enabled": event.data.get('enabled'),
                                "source": getattr(event, 'source', 'unknown')
                            }
                        }
                    )
                    if clear_cache_func:
                        clear_cache_func()
                        logger.info("Cache cleared, using updated MCP tools", extra={"data": {"service": service_name}})
                        
            # Ignore other event types
            
        except Exception as e:
            logger.error("Failed to handle event", extra={"data": {"type": event.type, "service": service_name, "error": str(e)}})
    
    return unified_event_handler


async def create_prompt_updated_handler(reload_func: Callable):
    """Legacy function for backward compatibility with prompt-only handlers."""
    return create_unified_event_handler("legacy-service", reload_func)