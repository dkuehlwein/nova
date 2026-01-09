"""
Memory API Endpoints Tests

Tests the memory API endpoints including search, add, health, and delete operations
with proper mocking of memory functions.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from uuid import uuid4

from backend.api.memory_endpoints import router


@pytest.fixture
def app():
    """Create test FastAPI app with memory router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestMemorySearchEndpoint:
    """Test POST /api/memory/search endpoint."""

    def test_search_memory_success(self, client):
        """Test successful memory search."""
        mock_result = {
            "success": True,
            "results": [
                {
                    "fact": "Test fact",
                    "uuid": str(uuid4()),
                    "source_node": str(uuid4()),
                    "target_node": str(uuid4()),
                    "created_at": "2025-01-08T10:00:00Z"
                }
            ],
            "count": 1,
            "query": "test",
            "limit": 10
        }

        with patch('backend.api.memory_endpoints.search_memory', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_result

            response = client.post(
                "/api/memory/search",
                json={"query": "test", "limit": 10}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["count"] == 1
            assert len(data["results"]) == 1

    def test_search_memory_error(self, client):
        """Test memory search error handling."""
        # Use the MemorySearchError as imported by the endpoint module
        from backend.api.memory_endpoints import MemorySearchError

        with patch('backend.api.memory_endpoints.search_memory', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = MemorySearchError("Connection failed")

            response = client.post(
                "/api/memory/search",
                json={"query": "test"}
            )

            assert response.status_code == 503


class TestMemoryAddEndpoint:
    """Test POST /api/memory/add endpoint."""

    def test_add_memory_success(self, client):
        """Test successful memory addition."""
        mock_result = {
            "success": True,
            "episode_uuid": str(uuid4()),
            "nodes_created": 2,
            "edges_created": 1,
            "entities": [
                {"name": "Test", "labels": ["Entity"], "uuid": str(uuid4())}
            ]
        }

        with patch('backend.api.memory_endpoints.add_memory', new_callable=AsyncMock) as mock_add:
            mock_add.return_value = mock_result

            response = client.post(
                "/api/memory/add",
                json={
                    "content": "Test content to remember",
                    "source_description": "Test source"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["nodes_created"] == 2
            assert data["edges_created"] == 1

    def test_add_memory_error(self, client):
        """Test memory add error handling."""
        # Use the MemoryAddError as imported by the endpoint module
        from backend.api.memory_endpoints import MemoryAddError

        with patch('backend.api.memory_endpoints.add_memory', new_callable=AsyncMock) as mock_add:
            mock_add.side_effect = MemoryAddError("Failed to add")

            response = client.post(
                "/api/memory/add",
                json={
                    "content": "Test content",
                    "source_description": "Test"
                }
            )

            assert response.status_code == 503


class TestDeleteEpisodeEndpoint:
    """Test DELETE /api/memory/episodes/{episode_uuid} endpoint."""

    def test_delete_episode_success(self, client):
        """Test successful episode deletion."""
        episode_uuid = str(uuid4())
        mock_result = {
            "success": True,
            "deleted_uuid": episode_uuid
        }

        with patch('backend.api.memory_endpoints.delete_episode', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_result

            response = client.delete(f"/api/memory/episodes/{episode_uuid}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["deleted_uuid"] == episode_uuid

    def test_delete_episode_error(self, client):
        """Test episode deletion error handling."""
        # Use the MemoryDeleteError as imported by the endpoint module
        from backend.api.memory_endpoints import MemoryDeleteError

        with patch('backend.api.memory_endpoints.delete_episode', new_callable=AsyncMock) as mock_delete:
            mock_delete.side_effect = MemoryDeleteError("Failed to delete")

            response = client.delete("/api/memory/episodes/invalid-uuid")

            assert response.status_code == 503


class TestDeleteFactEndpoint:
    """Test DELETE /api/memory/facts/{fact_uuid} endpoint."""

    def test_delete_fact_success(self, client):
        """Test successful fact deletion."""
        fact_uuid = str(uuid4())
        mock_result = {
            "success": True,
            "deleted_uuid": fact_uuid,
            "deleted_count": 1
        }

        with patch('backend.api.memory_endpoints.delete_fact', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_result

            response = client.delete(f"/api/memory/facts/{fact_uuid}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["deleted_uuid"] == fact_uuid
            assert data["deleted_count"] == 1

    def test_delete_fact_not_found(self, client):
        """Test fact deletion when not found."""
        mock_result = {
            "success": False,
            "error": "not_found",
            "message": "No fact found with UUID"
        }

        with patch('backend.api.memory_endpoints.delete_fact', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_result

            response = client.delete("/api/memory/facts/non-existent")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "not_found"

    def test_delete_fact_error(self, client):
        """Test fact deletion error handling."""
        # Use the MemoryDeleteError as imported by the endpoint module
        from backend.api.memory_endpoints import MemoryDeleteError

        with patch('backend.api.memory_endpoints.delete_fact', new_callable=AsyncMock) as mock_delete:
            mock_delete.side_effect = MemoryDeleteError("Database error")

            response = client.delete("/api/memory/facts/some-uuid")

            assert response.status_code == 503


class TestRecentFactsEndpoint:
    """Test GET /api/memory/recent endpoint."""

    def test_get_recent_facts_success(self, client):
        """Test successful retrieval of recent facts."""
        mock_result = {
            "success": True,
            "results": [
                {
                    "fact": "Recent fact 1",
                    "uuid": str(uuid4()),
                    "source_node": str(uuid4()),
                    "target_node": str(uuid4()),
                    "created_at": "2025-01-08T10:00:00Z"
                },
                {
                    "fact": "Recent fact 2",
                    "uuid": str(uuid4()),
                    "source_node": str(uuid4()),
                    "target_node": str(uuid4()),
                    "created_at": "2025-01-08T09:00:00Z"
                }
            ],
            "count": 2,
            "limit": 5
        }

        with patch('backend.api.memory_endpoints.get_recent_facts', new_callable=AsyncMock) as mock_recent:
            mock_recent.return_value = mock_result

            response = client.get("/api/memory/recent?limit=5")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["count"] == 2
            assert len(data["results"]) == 2

    def test_get_recent_facts_error(self, client):
        """Test recent facts error handling."""
        from backend.api.memory_endpoints import MemorySearchError

        with patch('backend.api.memory_endpoints.get_recent_facts', new_callable=AsyncMock) as mock_recent:
            mock_recent.side_effect = MemorySearchError("Database error")

            response = client.get("/api/memory/recent")

            assert response.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
