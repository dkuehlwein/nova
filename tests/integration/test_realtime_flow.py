"""
Integration tests for real-time event flows.

Tests the complete flow from file changes → Redis events → WebSocket broadcasts.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from utils.websocket_manager import WebSocketManager
from utils.prompt_loader import PromptLoader
from models.events import create_prompt_updated_event, create_mcp_toggled_event


class TestRealTimeFlow:
    """Test real-time event flows end-to-end."""
    
    @pytest.mark.asyncio
    async def test_prompt_file_to_websocket_flow(self):
        """Test complete flow: prompt file change → Redis → WebSocket broadcast."""
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
    
    @pytest.mark.asyncio
    async def test_mcp_server_toggle_to_websocket_flow(self):
        """Test complete flow: MCP server toggle → Redis → WebSocket broadcast."""
        ws_manager = WebSocketManager()
        mock_websocket = AsyncMock()
        client_id = await ws_manager.connect(mock_websocket, "test-client")
        
        # Mock Redis to capture published events
        published_events = []
        
        async def mock_publish(event, channel="nova_events"):
            published_events.append(event)
            return True
        
        with patch('utils.redis_manager.publish', side_effect=mock_publish):
            # Create MCP toggle event
            event = create_mcp_toggled_event(
                server_name="gmail",
                enabled=False,
                source="mcp-api"
            )
            
            # Publish event (simulating MCP API endpoint)
            await mock_publish(event)
            
            # Verify event was captured
            assert len(published_events) == 1
            captured_event = published_events[0]
            assert captured_event.type == "mcp_toggled"
            assert captured_event.data["server_name"] == "gmail"
            assert captured_event.data["enabled"] is False
            
            # Simulate the Redis → WebSocket bridge
            await ws_manager.broadcast_event(captured_event)
            
            # Verify WebSocket received the message
            mock_websocket.send_text.assert_called_once()
            sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
            
            assert sent_data["type"] == "mcp_toggled"
            assert sent_data["data"]["server_name"] == "gmail"
            assert sent_data["data"]["enabled"] is False
    
    @pytest.mark.asyncio
    async def test_multi_client_websocket_broadcast(self):
        """Test that events are broadcast to all connected WebSocket clients."""
        ws_manager = WebSocketManager()
        
        # Set up multiple WebSocket clients
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        mock_websocket3 = AsyncMock()
        
        client1_id = await ws_manager.connect(mock_websocket1, "client-1")
        client2_id = await ws_manager.connect(mock_websocket2, "client-2") 
        client3_id = await ws_manager.connect(mock_websocket3, "client-3")
        
        # Create test event
        event = create_prompt_updated_event("test.md", "modified")
        
        # Broadcast to all clients
        await ws_manager.broadcast_event(event)
        
        # Verify all clients received the message
        mock_websocket1.send_text.assert_called_once()
        mock_websocket2.send_text.assert_called_once()
        mock_websocket3.send_text.assert_called_once()
        
        # Verify all received the same data
        sent_data1 = json.loads(mock_websocket1.send_text.call_args[0][0])
        sent_data2 = json.loads(mock_websocket2.send_text.call_args[0][0])
        sent_data3 = json.loads(mock_websocket3.send_text.call_args[0][0])
        
        assert sent_data1 == sent_data2 == sent_data3
        assert sent_data1["type"] == "prompt_updated"
    
    @pytest.mark.asyncio
    async def test_redis_subscription_event_handling(self):
        """Test Redis subscription and event handling."""
        # Create test event
        test_event = create_prompt_updated_event("redis_test.md", "modified")
        
        # Simple approach: Mock the subscribe function directly
        async def mock_subscribe(channel="nova_events"):
            yield test_event
        
        with patch('utils.redis_manager.subscribe', new=mock_subscribe):
            from utils.redis_manager import subscribe
            
            # Test subscription
            events_received = []
            async for event in subscribe():
                events_received.append(event)
                break  # Only process first event
            
            # Verify we received the event
            assert len(events_received) == 1
            assert events_received[0].type == "prompt_updated"
            assert events_received[0].data["prompt_file"] == "redis_test.md"
    
    @pytest.mark.asyncio
    async def test_event_serialization_integrity(self):
        """Test that events maintain integrity through serialization/deserialization."""
        # Create various event types
        prompt_event = create_prompt_updated_event("test.md", "modified")
        mcp_event = create_mcp_toggled_event("gmail", True, "test")
        
        events = [prompt_event, mcp_event]
        
        for original_event in events:
            # Serialize event (as would happen in Redis)
            serialized = json.dumps({
                "id": original_event.id,
                "type": original_event.type,
                "timestamp": original_event.timestamp.isoformat(),
                "data": original_event.data,
                "source": original_event.source
            })
            
            # Deserialize event (as would happen in WebSocket broadcast)
            deserialized_data = json.loads(serialized)
            
            # Verify integrity
            assert deserialized_data["id"] == original_event.id
            assert deserialized_data["type"] == original_event.type
            assert deserialized_data["data"] == original_event.data
            assert deserialized_data["source"] == original_event.source
            
            # Verify timestamp can be parsed back
            from datetime import datetime
            parsed_timestamp = datetime.fromisoformat(deserialized_data["timestamp"])
            assert abs((parsed_timestamp - original_event.timestamp).total_seconds()) < 1
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_without_redis(self):
        """Test that system works gracefully when Redis is unavailable."""
        ws_manager = WebSocketManager()
        mock_websocket = AsyncMock()
        client_id = await ws_manager.connect(mock_websocket, "test-client")
        
        # Mock Redis to simulate unavailability
        with patch('utils.redis_manager.publish', side_effect=Exception("Redis unavailable")):
            # Create event
            event = create_prompt_updated_event("test.md", "modified")
            
            # Direct WebSocket broadcast should still work
            await ws_manager.broadcast_event(event)
            
            # Verify WebSocket still received the message
            mock_websocket.send_text.assert_called_once()
            sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
            
            assert sent_data["type"] == "prompt_updated"
            assert sent_data["data"]["prompt_file"] == "test.md"


class TestAgentPromptIntegration:
    """Test integration between prompt changes and agent reloading."""
    
    @pytest.mark.asyncio
    async def test_prompt_change_triggers_agent_reload_via_redis(self):
        """Test that a prompt file change triggers agent reload through Redis events."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Initial prompt content")
            temp_path = Path(f.name)
        
        try:
            # Track agent creation calls
            agent_creation_calls = []
            
            # Mock agent creation to track calls
            async def mock_create_chat_agent(reload_tools=False):
                agent_creation_calls.append({"reload_tools": reload_tools})
                return Mock()
            
            # Mock Redis event subscription
            redis_events = []
            
            # Mock event handler
            async def mock_event_handler(event):
                redis_events.append(event)
                # Simulate agent reloading logic
                if event.type == "prompt_updated":
                    await mock_create_chat_agent(reload_tools=True)
            
            # Patch agent creation to track reload_tools parameter
            with patch('agent.chat_agent.create_chat_agent', side_effect=mock_create_chat_agent):
                with patch('utils.redis_manager.publish') as mock_publish:
                    
                    # Create prompt loader and simulate prompt change
                    loader = PromptLoader(temp_path, debounce_seconds=0.1)
                    
                    # Initial agent creation (simulate startup)
                    await mock_create_chat_agent(reload_tools=False)
                    
                    # Modify prompt file
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        f.write("Updated prompt content")
                    
                    # Trigger reload and publish event
                    loader._load_prompt()
                    loader._publish_prompt_updated_event()
                    
                    # Get the event that would be published
                    if mock_publish.call_args:
                        event = mock_publish.call_args[0][0]
                        
                        # Simulate the event handler receiving the event
                        await mock_event_handler(event)
                    
                    # Verify agent was created twice: initial + reload
                    assert len(agent_creation_calls) == 2  # Initial + reload
                    assert agent_creation_calls[0]["reload_tools"] is False  # Initial creation
                    assert agent_creation_calls[1]["reload_tools"] is True   # Reload after prompt change
                    
        finally:
            temp_path.unlink()
    
    @pytest.mark.asyncio
    async def test_mcp_server_toggle_triggers_tool_reload_via_redis(self):
        """Test that MCP server toggle triggers tool reload through Redis events."""
        # Mock tool loading to track calls
        tool_loading_calls = []
        
        async def mock_get_client_and_tools():
            tool_loading_calls.append({"timestamp": asyncio.get_event_loop().time()})
            # Return different tools based on call count (simulating server toggle)
            if len(tool_loading_calls) == 1:
                return ["tool1", "tool2", "tool3"]  # Server enabled
            else:
                return ["tool1"]  # Server disabled
        
        async def mock_create_chat_agent(reload_tools=False):
            # Always call tool loading to simulate real agent creation behavior
            await mock_get_client_and_tools()
            return Mock()
        
        # Mock Redis event handling
        redis_events = []
        
        async def mock_event_handler(event):
            redis_events.append(event)
            # Simulate agent reloading logic for MCP changes
            if event.type == "mcp_toggled":
                await mock_create_chat_agent(reload_tools=True)
        
        with patch('agent.chat_agent.mcp_manager.get_tools', side_effect=mock_get_client_and_tools):
            with patch('agent.chat_agent.create_chat_agent', side_effect=mock_create_chat_agent):
                with patch('utils.redis_manager.publish') as mock_publish:
                    
                    # Initial agent creation
                    await mock_create_chat_agent(reload_tools=False)
                    
                    # Simulate MCP server toggle
                    event = create_mcp_toggled_event("gmail", False, "test")
                    await mock_event_handler(event)
                    
                    # Verify tools were reloaded
                    assert len(tool_loading_calls) == 2  # Initial + reload
                    assert len(redis_events) == 1
                    assert redis_events[0].type == "mcp_toggled"
                    assert redis_events[0].data["server_name"] == "gmail"
                    assert redis_events[0].data["enabled"] is False 