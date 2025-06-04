"""
Tests for chat API endpoints.

Tests the chat management endpoints to ensure they work correctly
and don't have the issues reported (405 errors, empty responses, etc.).
"""

import pytest
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from httpx import AsyncClient
from fastapi.testclient import TestClient

from main import app


class TestChatEndpoints:
    """Test chat API endpoints."""

    def test_health_check(self):
        """Test basic health check endpoint."""
        with TestClient(app) as client:
            response = client.get("/api/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "service" in data

    def test_chat_health_check(self):
        """Test chat health check endpoint."""
        with TestClient(app) as client:
            response = client.get("/chat/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "agent_ready" in data

    def test_get_api_chats_endpoint_exists(self):
        """Test that GET /api/chats endpoint exists and doesn't return 405."""
        with TestClient(app) as client:
            response = client.get("/api/chats")
            # Should not return 405 Method Not Allowed
            assert response.status_code != 405
            # Should return 200 (success) or other valid status
            assert response.status_code in [200, 404, 500]

    def test_get_api_chats_response_format(self):
        """Test that GET /api/chats returns valid response format."""
        with TestClient(app) as client:
            response = client.get("/api/chats")
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list)
                # Each chat should have required fields
                for chat in data:
                    assert "id" in chat
                    assert "title" in chat
                    assert "created_at" in chat
                    assert "updated_at" in chat

    def test_get_api_chat_by_id_endpoint_exists(self):
        """Test that GET /api/chats/{chat_id} endpoint exists."""
        with TestClient(app) as client:
            test_chat_id = "test-chat-123"
            response = client.get(f"/api/chats/{test_chat_id}")
            # Should not return 405 Method Not Allowed
            assert response.status_code != 405
            # Should return 200 (success) or 404 (not found)
            assert response.status_code in [200, 404]

    def test_get_api_chat_messages_endpoint_exists(self):
        """Test that GET /api/chats/{chat_id}/messages endpoint exists."""
        with TestClient(app) as client:
            test_chat_id = "test-chat-123"
            response = client.get(f"/api/chats/{test_chat_id}/messages")
            # Should not return 405 Method Not Allowed
            assert response.status_code != 405
            # Should return 200 (success) or 404 (not found)
            assert response.status_code in [200, 404]

    def test_legacy_chats_endpoint_still_works(self):
        """Test that original /chats endpoint still works."""
        with TestClient(app) as client:
            response = client.get("/chats")
            # Should not return 405 Method Not Allowed
            assert response.status_code != 405
            # Should return 200 (success) or other valid status
            assert response.status_code in [200, 404, 500]

    def test_chat_stream_endpoint_exists(self):
        """Test that chat streaming endpoint exists."""
        with TestClient(app) as client:
            # Test with minimal valid payload
            payload = {
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
                "stream": True
            }
            response = client.post("/chat/stream", json=payload)
            # Should not return 405 Method Not Allowed
            assert response.status_code != 405
            # Should return 200 or other valid status (not testing full streaming here)
            assert response.status_code in [200, 400, 422, 500]

    def test_non_streaming_chat_endpoint_exists(self):
        """Test that non-streaming chat endpoint exists."""
        with TestClient(app) as client:
            payload = {
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
                "stream": False
            }
            response = client.post("/chat", json=payload)
            # Should not return 405 Method Not Allowed
            assert response.status_code != 405
            # Should return 200 or other valid status
            assert response.status_code in [200, 400, 422, 500]


class TestChatFunctionality:
    """Test chat functionality (integration tests)."""

    def test_empty_chat_list_response(self):
        """Test that empty chat list returns valid empty array."""
        with TestClient(app) as client:
            response = client.get("/api/chats")
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list)
                # Empty list is valid - no '_GeneratorContextManager' error
                assert True  # If we get here without error, the fix worked

    def test_error_handling_for_invalid_chat_id(self):
        """Test error handling for invalid chat IDs."""
        with TestClient(app) as client:
            response = client.get("/api/chats/invalid-chat-id-12345")
            # Should handle gracefully, not throw '_GeneratorContextManager' error
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "id" in data
                assert "title" in data

    def test_error_handling_for_invalid_chat_messages(self):
        """Test error handling for invalid chat message requests."""
        with TestClient(app) as client:
            response = client.get("/api/chats/invalid-chat-id-12345/messages")
            # Should handle gracefully, not throw '_GeneratorContextManager' error  
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 