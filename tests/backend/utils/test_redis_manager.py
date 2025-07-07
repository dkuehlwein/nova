"""
Tests for Redis manager functionality.
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
import redis.asyncio as redis

from backend.models.events import NovaEvent, create_prompt_updated_event
from backend.utils.redis_manager import (
    get_redis,
    publish,
    subscribe,
    test_redis_connection,
    close_redis,
    publish_websocket_message
)


class TestRedisManager:
    """Test Redis manager functionality."""
    
    @pytest.fixture(autouse=True)
    def reset_redis_client(self):
        """Reset the global Redis client before each test."""
        import backend.utils.redis_manager
        backend.utils.redis_manager._redis_client = None
        yield
        backend.utils.redis_manager._redis_client = None
    
    @pytest.mark.asyncio
    async def test_get_redis_successful_connection(self):
        """Test successful Redis connection."""
        with patch('redis.asyncio.Redis') as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            # Make ping return a coroutine that resolves to True
            mock_client.ping = AsyncMock(return_value=True)
            
            client = await get_redis()
            
            assert client is mock_client
            mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_redis_connection_error(self):
        """Test Redis connection failure."""
        with patch('redis.asyncio.Redis') as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            mock_client.ping.side_effect = redis.ConnectionError("Connection failed")
            
            client = await get_redis()
            
            assert client is None
    
    @pytest.mark.asyncio
    async def test_get_redis_singleton_behavior(self):
        """Test that get_redis returns the same instance."""
        with patch('redis.asyncio.Redis') as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            # Make ping return a coroutine that resolves to True
            mock_client.ping = AsyncMock(return_value=True)
            
            client1 = await get_redis()
            client2 = await get_redis()
            
            assert client1 is client2
            # Should only create one Redis instance
            mock_redis_class.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_successful(self):
        """Test successful event publishing."""
        mock_client = AsyncMock()
        mock_client.publish.return_value = 2  # 2 subscribers
        
        with patch('backend.utils.redis_manager.get_redis', return_value=mock_client):
            event = create_prompt_updated_event(
                prompt_file="test.md",
                change_type="modified"
            )
            
            result = await publish(event)
            
            assert result is True
            mock_client.publish.assert_called_once()
            
            # Verify the published message
            call_args = mock_client.publish.call_args
            assert call_args[0][0] == "nova_events"  # channel
            
            # Parse the JSON message
            message_json = call_args[0][1]
            message_data = json.loads(message_json)
            assert message_data["type"] == "prompt_updated"
            assert message_data["data"]["prompt_file"] == "test.md"
    
    @pytest.mark.asyncio
    async def test_publish_redis_unavailable(self):
        """Test publishing when Redis is unavailable."""
        with patch('backend.utils.redis_manager.get_redis', return_value=None):
            event = create_prompt_updated_event(
                prompt_file="test.md",
                change_type="modified"
            )
            
            result = await publish(event)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_connection_error(self):
        """Test publishing with Redis connection error."""
        mock_client = AsyncMock()
        mock_client.publish.side_effect = redis.ConnectionError("Connection lost")
        
        with patch('backend.utils.redis_manager.get_redis', return_value=mock_client):
            event = create_prompt_updated_event(
                prompt_file="test.md",
                change_type="modified"
            )
            
            result = await publish(event)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_subscribe_successful(self):
        """Test successful event subscription."""
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        
        # Set up mock pubsub correctly
        mock_client.pubsub = Mock(return_value=mock_pubsub)
        
        # Mock received messages
        test_event = create_prompt_updated_event(
            prompt_file="test.md",
            change_type="modified"
        )
        
        mock_messages = [
            {"type": "subscribe", "channel": "nova_events"},
            {
                "type": "message",
                "data": test_event.model_dump_json()
            }
        ]
        
        async def mock_listen():
            for msg in mock_messages:
                yield msg
        
        mock_pubsub.listen = mock_listen
        
        with patch('backend.utils.redis_manager.get_redis', return_value=mock_client):
            events = []
            async for event in subscribe():
                events.append(event)
                break  # Only collect one event for test
            
            assert len(events) == 1
            assert events[0].type == "prompt_updated"
            assert events[0].data["prompt_file"] == "test.md"
            
            mock_pubsub.subscribe.assert_called_once_with("nova_events")
    
    @pytest.mark.asyncio
    async def test_subscribe_redis_unavailable(self):
        """Test subscription when Redis is unavailable."""
        with patch('backend.utils.redis_manager.get_redis', return_value=None):
            events = []
            async for event in subscribe():
                events.append(event)
                break  # Should not reach here
            
            assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_subscribe_invalid_json(self):
        """Test subscription with invalid JSON message."""
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        
        # Set up mock pubsub correctly
        mock_client.pubsub = Mock(return_value=mock_pubsub)
        
        mock_messages = [
            {"type": "subscribe", "channel": "nova_events"},
            {
                "type": "message",
                "data": "invalid json content"
            }
        ]
        
        async def mock_listen():
            for msg in mock_messages:
                yield msg
        
        mock_pubsub.listen = mock_listen
        
        with patch('backend.utils.redis_manager.get_redis', return_value=mock_client):
            events = []
            # Should not crash on invalid JSON, just log error
            async for event in subscribe():
                events.append(event)
                break  # Should not reach here due to JSON error
            
            assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_test_redis_connection_healthy(self):
        """Test Redis health check when healthy."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        
        with patch('backend.utils.redis_manager.get_redis', return_value=mock_client):
            result = await test_redis_connection()
            
            assert result is True
            mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_test_redis_connection_unhealthy(self):
        """Test Redis health check when unhealthy."""
        with patch('backend.utils.redis_manager.get_redis', return_value=None):
            result = await test_redis_connection()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_close_redis(self):
        """Test Redis connection cleanup."""
        mock_client = AsyncMock()
        
        # Set up the global client
        import backend.utils.redis_manager
        backend.utils.redis_manager._redis_client = mock_client
        
        await close_redis()
        
        mock_client.close.assert_called_once()
        assert backend.utils.redis_manager._redis_client is None
    
    @pytest.mark.asyncio
    async def test_publish_websocket_message(self):
        """Test WebSocket message publishing convenience function."""
        mock_client = AsyncMock()
        mock_client.publish.return_value = 1
        
        with patch('backend.utils.redis_manager.get_redis', return_value=mock_client):
            event = create_prompt_updated_event(
                prompt_file="test.md",
                change_type="modified"
            )
            
            result = await publish_websocket_message(event)
            
            assert result is True
            mock_client.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_custom_channel(self):
        """Test publishing to custom channel."""
        mock_client = AsyncMock()
        mock_client.publish.return_value = 1
        
        with patch('backend.utils.redis_manager.get_redis', return_value=mock_client):
            event = create_prompt_updated_event(
                prompt_file="test.md",
                change_type="modified"
            )
            
            result = await publish(event, channel="custom_channel")
            
            assert result is True
            call_args = mock_client.publish.call_args
            assert call_args[0][0] == "custom_channel"
    
    @pytest.mark.asyncio
    async def test_subscribe_custom_channel(self):
        """Test subscribing to custom channel."""
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        
        # Set up mock pubsub correctly
        mock_client.pubsub = Mock(return_value=mock_pubsub)
        
        async def mock_listen():
            yield {"type": "subscribe", "channel": "custom_channel"}
        
        mock_pubsub.listen = mock_listen
        
        with patch('backend.utils.redis_manager.get_redis', return_value=mock_client):
            async for event in subscribe("custom_channel"):
                break  # Just test subscription setup
            
            mock_pubsub.subscribe.assert_called_once_with("custom_channel") 