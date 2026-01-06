"""
Tests for MCP server management endpoints.

Per ADR-015, MCP servers are now managed by LiteLLM.
These endpoints are read-only, fetching server status from LiteLLM's MCP Gateway.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.mcp_endpoints import router


@pytest.fixture
def app():
    """Create test FastAPI app with MCP router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestMCPEndpoints:
    """Test MCP management endpoints (LiteLLM-based per ADR-015)."""

    @patch('backend.api.mcp_endpoints.mcp_manager.get_mcp_servers_status')
    def test_get_mcp_servers_empty(self, mock_get_status, client):
        """Test GET /api/mcp with no servers available."""
        mock_get_status.return_value = []

        response = client.get("/api/mcp/")

        assert response.status_code == 200
        data = response.json()
        assert data["servers"] == []
        assert data["total_servers"] == 0
        assert data["total_tools"] == 0
        assert data["source"] == "litellm"

    @patch('backend.api.mcp_endpoints.mcp_manager.get_mcp_servers_status')
    def test_get_mcp_servers_with_servers(self, mock_get_status, client):
        """Test GET /api/mcp with servers from LiteLLM."""
        mock_get_status.return_value = [
            {
                "name": "outlook_mac",
                "description": "Local Outlook for Mac",
                "tools_count": 4,
                "healthy": True,
                "enabled": True,
                "tool_names": ["list_emails", "read_email", "create_draft", "list_calendar_events"]
            },
            {
                "name": "feature_request",
                "description": "Linear integration",
                "tools_count": 1,
                "healthy": True,
                "enabled": True,
                "tool_names": ["request_feature"]
            }
        ]

        response = client.get("/api/mcp/")

        assert response.status_code == 200
        data = response.json()

        assert data["total_servers"] == 2
        assert data["total_tools"] == 5
        assert data["source"] == "litellm"

        # Check server details
        servers = {server["name"]: server for server in data["servers"]}

        assert "outlook_mac" in servers
        assert servers["outlook_mac"]["healthy"] is True
        assert servers["outlook_mac"]["tools_count"] == 4
        assert "list_emails" in servers["outlook_mac"]["tool_names"]

        assert "feature_request" in servers
        assert servers["feature_request"]["tools_count"] == 1

    @patch('backend.api.mcp_endpoints.mcp_manager.get_mcp_servers_status')
    def test_get_mcp_servers_error_handling(self, mock_get_status, client):
        """Test GET /api/mcp handles errors gracefully."""
        mock_get_status.side_effect = Exception("LiteLLM connection failed")

        response = client.get("/api/mcp/")

        assert response.status_code == 500
        assert "Failed to retrieve MCP servers" in response.json()["detail"]

    @patch('backend.api.mcp_endpoints.mcp_manager.list_tools_from_litellm')
    def test_get_mcp_tools_endpoint(self, mock_list_tools, client):
        """Test GET /api/mcp/tools returns raw tool list."""
        mock_list_tools.return_value = {
            "tools": [
                {
                    "name": "list_emails",
                    "description": "List emails from inbox",
                    "inputSchema": {"type": "object"},
                    "mcp_info": {
                        "server_name": "outlook_mac",
                        "description": "Local Outlook"
                    }
                }
            ]
        }

        response = client.get("/api/mcp/tools")

        assert response.status_code == 200
        data = response.json()

        assert data["total_tools"] == 1
        assert data["source"] == "litellm"
        assert len(data["tools"]) == 1
        assert data["tools"][0]["name"] == "list_emails"

    @patch('backend.api.mcp_endpoints.mcp_manager.list_tools_from_litellm')
    def test_get_mcp_tools_empty(self, mock_list_tools, client):
        """Test GET /api/mcp/tools with no tools."""
        mock_list_tools.return_value = {"tools": []}

        response = client.get("/api/mcp/tools")

        assert response.status_code == 200
        data = response.json()

        assert data["total_tools"] == 0
        assert data["tools"] == []
