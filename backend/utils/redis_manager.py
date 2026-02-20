"""
Redis manager for Nova's real-time event system.
Handles pub/sub for broadcasting events to WebSocket clients.
"""

import asyncio
import json
from typing import AsyncIterator, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from models.events import NovaEvent, WebSocketMessage
from utils.logging import get_logger

logger = get_logger("redis_manager")

# Global Redis client instance
_redis_client: Optional[Redis] = None


async def get_redis() -> Redis:
    """Get the global Redis client instance."""
    global _redis_client
    
    if _redis_client is None:
        try:
            # Get Redis URL from configuration
            from config import settings
            redis_url = settings.REDIS_URL
            
            # Connect to Redis instance using URL
            _redis_client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                health_check_interval=30,
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True,
                retry_on_error=[redis.ConnectionError, redis.TimeoutError]
            )
            
            # Test the connection
            await _redis_client.ping()
            
            logger.info(
                "Connected to Redis successfully",
                extra={
                    "data": {
                        "redis_url": redis_url
                    }
                }
            )
            
        except redis.ConnectionError as e:
            logger.warning(
                "Failed to connect to Redis, events will be logged but not broadcast",
                extra={
                    "data": {
                        "error": str(e),
                        "redis_url": redis_url
                    }
                }
            )
            # Return None to indicate Redis is not available
            return None
        except Exception as e:
            logger.error(
                "Unexpected error connecting to Redis",
                exc_info=True,
                extra={
                    "data": {
                        "error": str(e)
                    }
                }
            )
            return None
    
    return _redis_client


def get_sync_redis():
    """Get a synchronous Redis client for use in Celery workers."""
    try:
        from config import settings
        redis_url = settings.REDIS_URL
        
        # Import the synchronous Redis client
        import redis as sync_redis
        
        # Create synchronous Redis client
        return sync_redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            health_check_interval=30,
            socket_keepalive=True,
            socket_keepalive_options={},
            retry_on_timeout=True,
            retry_on_error=[sync_redis.ConnectionError, sync_redis.TimeoutError]
        )
    except Exception as e:
        logger.error(
            "Failed to create sync Redis client",
            extra={"data": {"error": str(e)}}
        )
        return None


async def publish(event: NovaEvent, channel: str = "nova_events") -> bool:
    """
    Publish an event to Redis channel.
    
    Args:
        event: The NovaEvent to publish
        channel: Redis channel name (default: "nova_events")
    
    Returns:
        bool: True if published successfully, False otherwise
    """
    try:
        redis_client = await get_redis()
        if redis_client is None:
            logger.debug(
                "Redis not available, skipping event publish",
                extra={
                    "data": {
                        "event_id": event.id,
                        "event_type": event.type,
                        "channel": channel
                    }
                }
            )
            return False
        
        # Serialize the event to JSON
        event_json = event.model_dump_json()
        
        # Publish to Redis channel
        subscribers = await redis_client.publish(channel, event_json)
        
        logger.info(
            "Published event to Redis channel",
            extra={
                "data": {
                    "event_id": event.id,
                    "event_type": event.type,
                    "channel": channel,
                    "subscribers": subscribers,
                    "source": event.source
                }
            }
        )

        return True

    except redis.ConnectionError:
        logger.warning(
            "Redis connection lost, failed to publish event",
            extra={
                "data": {
                    "event_id": event.id,
                    "event_type": event.type,
                    "channel": channel
                }
            }
        )
        return False
    except Exception as e:
        logger.error(
            "Failed to publish event to Redis",
            exc_info=True,
            extra={
                "data": {
                    "event_id": event.id,
                    "event_type": event.type,
                    "channel": channel,
                    "error": str(e)
                }
            }
        )
        return False


def publish_sync(event: NovaEvent, channel: str = "nova_events") -> bool:
    """
    Synchronously publish an event to Redis channel (for use in Celery workers).

    Args:
        event: The NovaEvent to publish
        channel: Redis channel name (default: "nova_events")

    Returns:
        bool: True if published successfully, False otherwise
    """
    try:
        redis_client = get_sync_redis()
        if redis_client is None:
            logger.debug(
                "Redis not available, skipping event publish",
                extra={
                    "data": {
                        "event_id": event.id,
                        "event_type": event.type,
                        "channel": channel
                    }
                }
            )
            return False

        # Serialize the event to JSON
        event_json = event.model_dump_json()

        # Publish to Redis channel
        subscribers = redis_client.publish(channel, event_json)

        logger.info(
            "Published event to Redis channel",
            extra={
                "data": {
                    "event_id": event.id,
                    "event_type": event.type,
                    "channel": channel,
                    "subscribers": subscribers,
                    "source": event.source
                }
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(
            "Failed to publish event to Redis",
            exc_info=True,
            extra={
                "data": {
                    "event_id": event.id,
                    "event_type": event.type,
                    "channel": channel,
                    "error": str(e)
                }
            }
        )
        return False


async def subscribe(channel: str = "nova_events") -> AsyncIterator[NovaEvent]:
    """
    Subscribe to Redis channel and yield NovaEvents.
    
    Args:
        channel: Redis channel name to subscribe to
        
    Yields:
        NovaEvent: Events received from the channel
    """
    redis_client = await get_redis()
    if redis_client is None:
        logger.warning(
            "Redis not available, cannot subscribe to channel",
            extra={"data": {"channel": channel}}
        )
        return
    
    pubsub = redis_client.pubsub()
    
    try:
        await pubsub.subscribe(channel)
        
        logger.info(
            "Subscribed to Redis channel",
            extra={"data": {"channel": channel}}
        )
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    # Parse JSON message back to NovaEvent
                    event_data = json.loads(message['data'])
                    event = NovaEvent(**event_data)
                    
                    logger.debug(
                        "Received event from Redis channel",
                        extra={
                            "data": {
                                "event_id": event.id,
                                "event_type": event.type,
                                "channel": channel,
                                "source": event.source
                            }
                        }
                    )
                    
                    yield event
                    
                except json.JSONDecodeError as e:
                    logger.error(
                        "Failed to parse event JSON from Redis",
                        extra={
                            "data": {
                                "channel": channel,
                                "message": message['data'][:100],  # First 100 chars
                                "error": str(e)
                            }
                        }
                    )
                except Exception as e:
                    logger.error(
                        "Error processing Redis message",
                        exc_info=True,
                        extra={
                            "data": {
                                "channel": channel,
                                "error": str(e)
                            }
                        }
                    )
    
    except redis.ConnectionError:
        logger.warning(
            "Redis connection lost during subscription",
            extra={"data": {"channel": channel}}
        )
    except Exception as e:
        logger.error(
            "Error in Redis subscription",
            exc_info=True,
            extra={
                "data": {
                    "channel": channel,
                    "error": str(e)
                }
            }
        )
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            logger.info(
                "Unsubscribed from Redis channel",
                extra={"data": {"channel": channel}}
            )
        except Exception as e:
            logger.debug("Error during Redis cleanup", extra={"data": {"error": str(e)}})


async def test_redis_connection() -> bool:
    """
    Test Redis connection health.
    
    Returns:
        bool: True if Redis is healthy, False otherwise
    """
    try:
        redis_client = await get_redis()
        if redis_client is None:
            return False
        
        await redis_client.ping()
        return True
        
    except Exception as e:
        logger.error(
            "Redis health check failed",
            exc_info=True,
            extra={"data": {"error": str(e)}}
        )
        return False


async def close_redis():
    """Close the Redis connection."""
    global _redis_client
    
    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error("Error closing Redis connection", extra={"data": {"error": str(e)}})
        finally:
            _redis_client = None


# Convenience function for WebSocket message broadcasting
async def publish_websocket_message(event: NovaEvent, channel: str = "nova_events") -> bool:
    """
    Publish a NovaEvent that will be converted to WebSocket message format.
    
    Args:
        event: The NovaEvent to publish
        channel: Redis channel name
        
    Returns:
        bool: True if published successfully, False otherwise
    """
    return await publish(event, channel) 