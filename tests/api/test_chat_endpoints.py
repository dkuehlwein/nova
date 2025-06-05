"""
Tests for Nova Chat API Endpoints
"""

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage, AIMessage

from main import app
from agent.chat_agent import create_chat_agent


client = TestClient(app)


class TestChatEndpoints:
    """Test cases for chat API endpoints."""
    
    def test_health_endpoint(self):
        """Test the health check endpoint."""
        response = client.get("/chat/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "agent_ready" in data
        assert "timestamp" in data
        assert data["agent_ready"] is True
    
    def test_tools_endpoint(self):
        """Test the tools listing endpoint."""
        response = client.get("/chat/tools")
        assert response.status_code == 200
        
        data = response.json()
        assert "tools" in data
        assert "count" in data
        assert "timestamp" in data
        assert isinstance(data["tools"], list)
        assert data["count"] >= 0
    
    def test_chat_non_streaming(self):
        """Test non-streaming chat endpoint."""
        chat_request = {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello! Please introduce yourself and tell me what you can help with."
                }
            ],
            "stream": False
        }
        
        response = client.post("/chat/", json=chat_request)
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "thread_id" in data
        
        message = data["message"]
        assert message["role"] == "assistant"
        assert isinstance(message["content"], str)
        assert len(message["content"]) > 0
    
    def test_chat_streaming(self):
        """Test streaming chat endpoint."""
        chat_request = {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello! This is a test message."
                }
            ],
            "stream": True
        }
        
        response = client.post("/chat/stream", json=chat_request)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
    
    def test_chat_with_thread_id(self):
        """Test chat with specific thread ID for continuity."""
        thread_id = "test-thread-123"
        
        # First message
        chat_request1 = {
            "messages": [
                {
                    "role": "user", 
                    "content": "Remember that my name is TestUser."
                }
            ],
            "thread_id": thread_id,
            "stream": False
        }
        
        response1 = client.post("/chat/", json=chat_request1)
        assert response1.status_code == 200
        
        # Second message in same thread
        chat_request2 = {
            "messages": [
                {
                    "role": "user",
                    "content": "What is my name?"
                }
            ],
            "thread_id": thread_id,
            "stream": False
        }
        
        response2 = client.post("/chat/", json=chat_request2)
        assert response2.status_code == 200
        
        # Both should return the same thread_id
        data1 = response1.json()
        data2 = response2.json()
        assert data1["thread_id"] == thread_id
        assert data2["thread_id"] == thread_id


class TestChatEndpointsIntegration:
    """Integration tests for chat endpoints."""
    
    @pytest.mark.asyncio
    async def test_agent_integration(self):
        """Test that the endpoint properly integrates with the agent."""
        # Test direct agent call
        test_message = HumanMessage(content="Hello! Please introduce yourself and tell me what you can help with.")
        
        # Add required configuration for checkpointer
        config = {
            "configurable": {
                "thread_id": "test-integration-thread"
            }
        }
        
        # Create the async graph instance
        agent_graph = await create_chat_agent()
        
        result = await agent_graph.ainvoke({
            "messages": [test_message]
        }, config=config)
        
        # Verify agent response
        assert result is not None
        assert "messages" in result
        assert len(result["messages"]) > 0
        
        # Extract response
        last_message = result["messages"][-1]
        assert isinstance(last_message, AIMessage)
        assert isinstance(last_message.content, str)
        assert len(last_message.content) > 0
    
    def test_error_handling(self):
        """Test error handling in chat endpoints."""
        # Test with malformed request
        malformed_request = {
            "messages": "this should be a list",
            "stream": False
        }
        
        response = client.post("/chat/", json=malformed_request)
        assert response.status_code == 422  # Validation error
    
    def test_empty_messages(self):
        """Test handling of empty messages."""
        empty_request = {
            "messages": [],
            "stream": False
        }
        
        response = client.post("/chat/", json=empty_request)
        # Should handle gracefully, either with 200 or 422
        assert response.status_code in [200, 422]


# Manual test function for development
async def manual_test_chat_endpoints():
    """Manual test function for development testing."""
    print("\n🧪 Testing Nova Chat Endpoints...")
    
    # Test health endpoint
    response = client.get("/chat/health")
    print(f"Health check: {response.status_code}, {response.json()}")
    
    # Test tools endpoint
    response = client.get("/chat/tools")
    print(f"Tools: {response.status_code}, tool count: {response.json().get('count', 0)}")
    
    # Test basic chat
    chat_request = {
        "messages": [
            {
                "role": "user",
                "content": "Hello! Please introduce yourself briefly."
            }
        ],
        "stream": False
    }
    
    response = client.post("/chat/", json=chat_request)
    if response.status_code == 200:
        data = response.json()
        print(f"Chat response: {data['message']['content'][:100]}...")
    else:
        print(f"Chat failed: {response.status_code}, {response.text}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(manual_test_chat_endpoints()) 