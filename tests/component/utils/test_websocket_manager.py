"""
Tests for WebSocket manager functionality.
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.models.events import NovaEvent, create_prompt_updated_event
from backend.utils.websocket_manager import (
    WebSocketManager, 
    websocket_manager,
    handle_websocket_connection
)


class TestWebSocketManager:
    """Test WebSocketManager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh WebSocketManager for each test."""
        return WebSocketManager()
    
    @pytest.mark.asyncio
    async def test_connect_with_client_id(self, manager):
        """Test connecting a WebSocket with specified client ID."""
        mock_websocket = AsyncMock(spec=WebSocket)
        client_id = "test-client-123"
        
        result_id = await manager.connect(mock_websocket, client_id)
        
        assert result_id == client_id
        assert client_id in manager.active_connections
        assert manager.active_connections[client_id] is mock_websocket
        assert client_id in manager.client_metadata
        assert manager.get_connection_count() == 1
        
        mock_websocket.accept.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_without_client_id(self, manager):
        """Test connecting a WebSocket without client ID generates one."""
        mock_websocket = AsyncMock(spec=WebSocket)
        
        result_id = await manager.connect(mock_websocket)
        
        assert result_id is not None
        assert len(result_id) > 0  # Generated ID should exist
        assert result_id in manager.active_connections
        assert manager.get_connection_count() == 1
        
        mock_websocket.accept.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, manager):
        """Test disconnecting a WebSocket client."""
        mock_websocket = AsyncMock(spec=WebSocket)
        client_id = await manager.connect(mock_websocket, "test-client")
        
        assert manager.get_connection_count() == 1
        
        await manager.disconnect(client_id)
        
        assert client_id not in manager.active_connections
        assert client_id not in manager.client_metadata
        assert manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_client(self, manager):
        """Test disconnecting a non-existent client doesn't crash."""
        await manager.disconnect("nonexistent-client")
        
        assert manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_send_personal_message_success(self, manager):
        """Test sending a personal message successfully."""
        mock_websocket = AsyncMock(spec=WebSocket)
        client_id = await manager.connect(mock_websocket, "test-client")
        
        message = {"type": "test", "data": "hello"}
        await manager.send_personal_message(message, client_id)
        
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        assert json.loads(sent_data) == message
        
        # Check metadata updated
        assert manager.client_metadata[client_id]["messages_sent"] == 1
    
    @pytest.mark.asyncio
    async def test_send_personal_message_failure_removes_client(self, manager):
        """Test that failed message sending removes the client."""
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.send_text.side_effect = Exception("Connection failed")
        client_id = await manager.connect(mock_websocket, "test-client")
        
        message = {"type": "test", "data": "hello"}
        await manager.send_personal_message(message, client_id)
        
        # Client should be removed after failure
        assert client_id not in manager.active_connections
        assert manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_send_personal_message_nonexistent_client(self, manager):
        """Test sending message to non-existent client."""
        message = {"type": "test", "data": "hello"}
        await manager.send_personal_message(message, "nonexistent-client")
        
        # Should not crash
        assert manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self, manager):
        """Test broadcasting with no active connections."""
        message = {"type": "test", "data": "hello"}
        await manager.broadcast(message)
        
        # Should not crash
        assert manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_successful(self, manager):
        """Test successful broadcasting to multiple clients."""
        # Connect multiple clients
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)
        
        client1 = await manager.connect(mock_ws1, "client-1")
        client2 = await manager.connect(mock_ws2, "client-2")
        
        message = {"type": "test", "data": "broadcast"}
        await manager.broadcast(message)
        
        # Both clients should receive the message
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()
        
        # Check message content
        sent_data = json.loads(mock_ws1.send_text.call_args[0][0])
        assert sent_data == message
        
        # Check metadata
        assert manager.client_metadata[client1]["messages_sent"] == 1
        assert manager.client_metadata[client2]["messages_sent"] == 1
    
    @pytest.mark.asyncio
    async def test_broadcast_with_failed_connection(self, manager):
        """Test broadcasting when one connection fails."""
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)
        mock_ws2.send_text.side_effect = Exception("Connection failed")
        
        client1 = await manager.connect(mock_ws1, "client-1")
        client2 = await manager.connect(mock_ws2, "client-2")
        
        assert manager.get_connection_count() == 2
        
        message = {"type": "test", "data": "broadcast"}
        await manager.broadcast(message)
        
        # Successful client should receive message
        mock_ws1.send_text.assert_called_once()
        
        # Failed client should be removed
        assert client1 in manager.active_connections
        assert client2 not in manager.active_connections
        assert manager.get_connection_count() == 1
    
    @pytest.mark.asyncio
    async def test_broadcast_event_success(self, manager):
        """Test broadcasting a NovaEvent."""
        mock_websocket = AsyncMock(spec=WebSocket)
        client_id = await manager.connect(mock_websocket, "test-client")
        
        event = create_prompt_updated_event(
            prompt_file="test.md",
            change_type="modified"
        )
        
        await manager.broadcast_event(event)
        
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        
        # Should be in WebSocketMessage format
        assert "id" in sent_data
        assert sent_data["type"] == "prompt_updated"
        assert "timestamp" in sent_data
        assert sent_data["data"]["prompt_file"] == "test.md"
    
    @pytest.mark.asyncio
    async def test_broadcast_event_validation_error(self, manager):
        """Test broadcasting event with validation error."""
        mock_websocket = AsyncMock(spec=WebSocket)
        await manager.connect(mock_websocket, "test-client")
        
        # Create an invalid event
        invalid_event = Mock()
        invalid_event.id = "test-id"
        invalid_event.type = "invalid_type"
        
        with patch('backend.utils.websocket_manager.WebSocketMessage.from_nova_event') as mock_convert:
            mock_convert.side_effect = Exception("Validation failed")
            
            await manager.broadcast_event(invalid_event)
            
            # Should not crash, just log error
            mock_websocket.send_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_ping(self, manager):
        """Test sending ping to specific client."""
        mock_websocket = AsyncMock(spec=WebSocket)
        client_id = await manager.connect(mock_websocket, "test-client")
        
        await manager.send_ping(client_id)
        
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "ping"
        assert "timestamp" in sent_data
    
    @pytest.mark.asyncio
    async def test_send_ping_to_all(self, manager):
        """Test sending ping to all clients."""
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)
        
        await manager.connect(mock_ws1, "client-1")
        await manager.connect(mock_ws2, "client-2")
        
        await manager.send_ping_to_all()
        
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()
        
        # Check ping message format
        sent_data = json.loads(mock_ws1.send_text.call_args[0][0])
        assert sent_data["type"] == "ping"
    
    def test_get_connection_metrics(self, manager):
        """Test getting connection metrics."""
        assert manager.get_connection_count() == 0
        assert manager.get_client_ids() == set()
        assert manager.get_all_client_metadata() == {}
    
    @pytest.mark.asyncio
    async def test_get_client_metadata(self, manager):
        """Test getting client metadata."""
        mock_websocket = AsyncMock(spec=WebSocket)
        client_id = await manager.connect(mock_websocket, "test-client")
        
        metadata = manager.get_client_metadata(client_id)
        assert "connected_at" in metadata
        assert metadata["messages_sent"] == 0
        
        # Test non-existent client
        assert manager.get_client_metadata("nonexistent") == {}


class TestHandleWebSocketConnection:
    """Test the handle_websocket_connection function."""
    
    @pytest.mark.asyncio
    async def test_normal_connection_lifecycle(self):
        """Test normal WebSocket connection lifecycle."""
        mock_websocket = AsyncMock(spec=WebSocket)
        
        # Mock receiving some messages then disconnecting
        messages = ['{"type": "subscribe"}', '{"type": "pong"}']
        mock_websocket.receive_text.side_effect = messages + [WebSocketDisconnect()]
        
        with patch('backend.utils.websocket_manager.websocket_manager') as mock_manager:
            mock_manager.connect = AsyncMock(return_value="test-client-id")
            mock_manager.disconnect = AsyncMock()
            
            await handle_websocket_connection(mock_websocket, "custom-id")
            
            mock_manager.connect.assert_called_once_with(mock_websocket, "custom-id")
            mock_manager.disconnect.assert_called_once_with("test-client-id")
    
    @pytest.mark.asyncio
    async def test_connection_with_invalid_json(self):
        """Test handling invalid JSON messages."""
        mock_websocket = AsyncMock(spec=WebSocket)
        
        # Send invalid JSON then disconnect
        mock_websocket.receive_text.side_effect = [
            "invalid json",
            WebSocketDisconnect()
        ]
        
        with patch('backend.utils.websocket_manager.websocket_manager') as mock_manager:
            mock_manager.connect = AsyncMock(return_value="test-client-id")
            mock_manager.disconnect = AsyncMock()
            
            await handle_websocket_connection(mock_websocket)
            
            # Should handle invalid JSON gracefully
            mock_manager.disconnect.assert_called_once_with("test-client-id")
    
    @pytest.mark.asyncio
    async def test_connection_with_exception(self):
        """Test handling unexpected exceptions."""
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.receive_text.side_effect = Exception("Unexpected error")
        
        with patch('backend.utils.websocket_manager.websocket_manager') as mock_manager:
            mock_manager.connect = AsyncMock(return_value="test-client-id")
            mock_manager.disconnect = AsyncMock()
            
            await handle_websocket_connection(mock_websocket)
            
            # Should disconnect client even on unexpected error
            mock_manager.disconnect.assert_called_once_with("test-client-id")


class TestGlobalWebSocketManager:
    """Test the global websocket_manager instance."""
    
    def test_global_manager_exists(self):
        """Test that global websocket_manager exists."""
        assert websocket_manager is not None
        assert isinstance(websocket_manager, WebSocketManager)
    
    @pytest.mark.asyncio
    async def test_global_manager_functionality(self):
        """Test that global manager works correctly."""
        mock_websocket = AsyncMock(spec=WebSocket)
        
        # Use the global manager
        client_id = await websocket_manager.connect(mock_websocket, "global-test")
        assert client_id == "global-test"
        
        # Cleanup
        await websocket_manager.disconnect(client_id) 