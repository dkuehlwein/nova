"""
Integration tests for Nova's real-time event system.
Tests the complete flow: File changes → Redis events → WebSocket broadcasts.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend.models.events import create_prompt_updated_event
from backend.utils.prompt_loader import PromptLoader
from backend.utils.redis_manager import publish, subscribe
from backend.utils.websocket_manager import WebSocketManager


class TestRealTimeFlow:
    """Test complete real-time event flows."""
    
    @pytest.mark.asyncio
    async def test_prompt_file_to_websocket_flow(self):
        """Test complete flow: prompt file change → Redis → WebSocket broadcast."""
        
        # Create a temporary prompt file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Initial prompt content")
            temp_path = Path(f.name)
        
        try:
            # Set up components
            ws_manager = WebSocketManager()
            mock_websocket = AsyncMock()
            client_id = await ws_manager.connect(mock_websocket, "test-client")
            
            # Mock Redis to capture published events
            published_events = []
            
            async def mock_publish(event, channel="nova_events"):
                published_events.append(event)
                return True
            
            with patch('utils.redis_manager.publish', side_effect=mock_publish):
                # Create prompt loader and modify file
                loader = PromptLoader(temp_path, debounce_seconds=0.1)
                
                # Modify the file to trigger event
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write("Updated prompt content")
                
                # Trigger the reload manually (simulating file watcher)
                loader._load_prompt()
                loader._publish_prompt_updated_event()
                
                # Give async operations time to complete
                await asyncio.sleep(0.2)
                
                # Verify event was published
                assert len(published_events) == 1
                event = published_events[0]
                assert event.type == "prompt_updated"
                assert event.data["prompt_file"] == temp_path.name
                assert event.data["change_type"] == "modified"
                
                # Simulate the Redis → WebSocket bridge
                await ws_manager.broadcast_event(event)
                
                # Verify WebSocket received the message
                mock_websocket.send_text.assert_called_once()
                sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
                
                assert sent_data["type"] == "prompt_updated"
                assert sent_data["data"]["prompt_file"] == temp_path.name
                
        finally:
            temp_path.unlink()
            await ws_manager.disconnect(client_id)
    
    @pytest.mark.asyncio
    async def test_redis_to_multiple_websockets_flow(self):
        """Test Redis event broadcasting to multiple WebSocket clients."""
        
        # Set up multiple WebSocket clients
        ws_manager = WebSocketManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()
        
        client1 = await ws_manager.connect(mock_ws1, "client-1")
        client2 = await ws_manager.connect(mock_ws2, "client-2")
        client3 = await ws_manager.connect(mock_ws3, "client-3")
        
        try:
            # Create and broadcast an event
            event = create_prompt_updated_event(
                prompt_file="test.md",
                change_type="modified",
                source="integration-test"
            )
            
            await ws_manager.broadcast_event(event)
            
            # Verify all clients received the message
            mock_ws1.send_text.assert_called_once()
            mock_ws2.send_text.assert_called_once()
            mock_ws3.send_text.assert_called_once()
            
            # Verify message content is consistent
            for mock_ws in [mock_ws1, mock_ws2, mock_ws3]:
                sent_data = json.loads(mock_ws.send_text.call_args[0][0])
                assert sent_data["type"] == "prompt_updated"
                assert sent_data["data"]["prompt_file"] == "test.md"
                assert sent_data["source"] == "integration-test"
                
        finally:
            await ws_manager.disconnect(client1)
            await ws_manager.disconnect(client2)  
            await ws_manager.disconnect(client3)
    
    @pytest.mark.asyncio
    async def test_websocket_client_lifecycle_with_events(self):
        """Test WebSocket client connecting, receiving events, then disconnecting."""
        
        ws_manager = WebSocketManager()
        mock_websocket = AsyncMock()
        
        # Test connection
        client_id = await ws_manager.connect(mock_websocket, "lifecycle-test")
        assert ws_manager.get_connection_count() == 1
        
        # Send a few events
        events = [
            create_prompt_updated_event("file1.md", "modified"),
            create_prompt_updated_event("file2.md", "created"),
            create_prompt_updated_event("file3.md", "deleted")
        ]
        
        for event in events:
            await ws_manager.broadcast_event(event)
        
        # Verify all events were sent
        assert mock_websocket.send_text.call_count == 3
        
        # Verify client metadata tracks messages
        metadata = ws_manager.get_client_metadata(client_id)
        assert metadata["messages_sent"] == 3
        
        # Test disconnection
        await ws_manager.disconnect(client_id)
        assert ws_manager.get_connection_count() == 0
        assert client_id not in ws_manager.client_metadata
    
    @pytest.mark.asyncio
    async def test_failed_websocket_cleanup_during_broadcast(self):
        """Test that failed WebSocket connections are cleaned up during broadcast."""
        
        ws_manager = WebSocketManager()
        
        # Set up one good and one bad connection
        mock_good_ws = AsyncMock()
        mock_bad_ws = AsyncMock()
        mock_bad_ws.send_text.side_effect = Exception("Connection lost")
        
        good_client = await ws_manager.connect(mock_good_ws, "good-client")
        bad_client = await ws_manager.connect(mock_bad_ws, "bad-client")
        
        assert ws_manager.get_connection_count() == 2
        
        # Broadcast an event
        event = create_prompt_updated_event("test.md", "modified")
        await ws_manager.broadcast_event(event)
        
        # Good client should receive message, bad client should be removed
        mock_good_ws.send_text.assert_called_once()
        assert ws_manager.get_connection_count() == 1
        assert good_client in ws_manager.active_connections
        assert bad_client not in ws_manager.active_connections
        
        # Cleanup
        await ws_manager.disconnect(good_client)
    
    @pytest.mark.asyncio
    async def test_redis_subscription_flow(self):
        """Test Redis subscription and event reception."""
        
        # Mock Redis client and pubsub
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        
        # Set up mock pubsub correctly
        from unittest.mock import Mock
        mock_client.pubsub = Mock(return_value=mock_pubsub)
        
        # Create test event
        test_event = create_prompt_updated_event("redis_test.md", "modified")
        
        # Mock Redis messages
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
            received_events = []
            
            # Subscribe and collect one event
            async for event in subscribe():
                received_events.append(event)
                break  # Only collect one event for test
            
            # Verify event was received correctly
            assert len(received_events) == 1
            received_event = received_events[0]
            assert received_event.type == "prompt_updated"
            assert received_event.data["prompt_file"] == "redis_test.md"
            assert received_event.source == test_event.source
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_without_redis(self):
        """Test that system works gracefully when Redis is unavailable."""
        
        # Set up WebSocket manager
        ws_manager = WebSocketManager()
        mock_websocket = AsyncMock()
        client_id = await ws_manager.connect(mock_websocket, "no-redis-test")
        
        try:
            # Mock Redis as unavailable
            with patch('backend.utils.redis_manager.get_redis', return_value=None):
                # Try to publish an event (should fail gracefully)
                event = create_prompt_updated_event("test.md", "modified")
                result = await publish(event)
                
                assert result is False  # Should indicate failure
                
                # Direct WebSocket broadcast should still work
                await ws_manager.broadcast_event(event)
                mock_websocket.send_text.assert_called_once()
                
                # Verify message was still delivered
                sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
                assert sent_data["type"] == "prompt_updated"
                
        finally:
            await ws_manager.disconnect(client_id)
    
    @pytest.mark.asyncio
    async def test_concurrent_websocket_operations(self):
        """Test concurrent WebSocket operations don't cause issues."""
        
        ws_manager = WebSocketManager()
        
        # Create multiple clients concurrently
        async def create_client(client_id):
            mock_ws = AsyncMock()
            return await ws_manager.connect(mock_ws, client_id)
        
        # Create 10 clients concurrently
        client_tasks = [create_client(f"client-{i}") for i in range(10)]
        client_ids = await asyncio.gather(*client_tasks)
        
        assert len(client_ids) == 10
        assert ws_manager.get_connection_count() == 10
        
        # Broadcast events concurrently
        async def broadcast_event(event_id):
            event = create_prompt_updated_event(f"file-{event_id}.md", "modified")
            await ws_manager.broadcast_event(event)
        
        # Broadcast 5 events concurrently
        broadcast_tasks = [broadcast_event(i) for i in range(5)]
        await asyncio.gather(*broadcast_tasks)
        
        # Verify all clients received all messages
        for client_id in client_ids:
            mock_ws = ws_manager.active_connections[client_id]
            assert mock_ws.send_text.call_count == 5
        
        # Cleanup all clients
        cleanup_tasks = [ws_manager.disconnect(client_id) for client_id in client_ids]
        await asyncio.gather(*cleanup_tasks)
        
        assert ws_manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_event_serialization_deserialization(self):
        """Test that events maintain integrity through the Redis pipeline."""
        
        # Create a complex event with various data types
        event = create_prompt_updated_event(
            prompt_file="complex_test.md",
            change_type="modified",
            source="serialization-test"
        )
        
        # Add some complex data
        event.data.update({
            "number": 42,
            "boolean": True,
            "list": ["a", "b", "c"],
            "nested": {"key": "value", "count": 123}
        })
        
        # Serialize to JSON (as Redis would)
        event_json = event.model_dump_json()
        
        # Deserialize back (as subscription would)
        import json
        from backend.models.events import NovaEvent
        
        event_data = json.loads(event_json)
        reconstructed_event = NovaEvent(**event_data)
        
        # Verify all data is preserved
        assert reconstructed_event.type == event.type
        assert reconstructed_event.source == event.source
        assert reconstructed_event.data["prompt_file"] == "complex_test.md"
        assert reconstructed_event.data["number"] == 42
        assert reconstructed_event.data["boolean"] is True
        assert reconstructed_event.data["list"] == ["a", "b", "c"]
        assert reconstructed_event.data["nested"]["key"] == "value"
        
        # Test WebSocket conversion
        from backend.models.events import WebSocketMessage
        ws_message = WebSocketMessage.from_nova_event(reconstructed_event)
        
        assert ws_message.type == event.type
        assert ws_message.source == event.source
        assert ws_message.data == reconstructed_event.data 