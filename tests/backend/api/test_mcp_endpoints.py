"""
Tests for MCP server management endpoints.
Tests work package B5 implementation.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
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
    """Test MCP management endpoints."""
    
    @patch('backend.api.mcp_endpoints.get_config')
    @patch('backend.api.mcp_endpoints.mcp_manager.check_server_health_and_get_tools_count')
    def test_get_mcp_servers_empty_config(self, mock_health_check, mock_get_config, client):
        """Test GET /api/mcp with empty configuration."""
        mock_get_config.return_value = {}
        
        response = client.get("/api/mcp/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["servers"] == []
        assert data["total_servers"] == 0
        assert data["healthy_servers"] == 0
        assert data["enabled_servers"] == 0
    
    @patch('backend.api.mcp_endpoints.get_config')
    @patch('backend.api.mcp_endpoints.mcp_manager.check_server_health_and_get_tools_count')
    async def test_get_mcp_servers_with_config(self, mock_health_check, mock_get_config, client):
        """Test GET /api/mcp with server configuration."""
        mock_get_config.return_value = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "description": "Gmail MCP Server",
                "enabled": True
            },
            "disabled_server": {
                "url": "http://localhost:8003/mcp",
                "description": "Disabled Server",
                "enabled": False
            }
        }
        
        # Mock health check to return (healthy, tools_count) tuple for enabled servers
        mock_health_check.return_value = (True, 14)  # Google Workspace has 14 tools
        
        response = client.get("/api/mcp/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_servers"] == 2
        assert data["enabled_servers"] == 1
        assert data["healthy_servers"] == 1
        
        # Check server details
        servers = {server["name"]: server for server in data["servers"]}
        
        assert "gmail" in servers
        assert servers["gmail"]["enabled"] is True
        assert servers["gmail"]["healthy"] is True
        assert servers["gmail"]["tools_count"] == 14  # Now includes tools count
        
        assert "disabled_server" in servers
        assert servers["disabled_server"]["enabled"] is False
        assert servers["disabled_server"]["healthy"] is False
        assert servers["disabled_server"]["tools_count"] is None  # Disabled servers have no tools count
    
    @patch('backend.api.mcp_endpoints.get_config')
    @patch('backend.api.mcp_endpoints.save_config')
    @patch('backend.api.mcp_endpoints.publish')
    def test_toggle_mcp_server_enable(self, mock_publish, mock_save_config, mock_get_config, client):
        """Test PUT /api/mcp/{name}/toggle to enable server."""
        mock_get_config.return_value = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "description": "Gmail MCP Server",
                "enabled": False  # Currently disabled
            }
        }
        
        # Mock the save config function
        mock_save_config.return_value = None
        
        response = client.put("/api/mcp/gmail/toggle", json={"enabled": True})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["server_name"] == "gmail"
        assert data["enabled"] is True
        assert "enabled" in data["message"]
        
        # Verify config was saved
        mock_save_config.assert_called_once()
        # Check that save_config was called with the correct arguments
        call_args = mock_save_config.call_args
        assert call_args[0][0] == "mcp_servers"  # config type
        saved_config = call_args[0][1]  # config data
        assert saved_config["gmail"]["enabled"] is True
        
        # Verify event was published
        mock_publish.assert_called_once()
    
    @patch('backend.api.mcp_endpoints.get_config')
    def test_toggle_mcp_server_not_found(self, mock_get_config, client):
        """Test PUT /api/mcp/{name}/toggle with non-existent server."""
        mock_get_config.return_value = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "description": "Gmail MCP Server",
                "enabled": True
            }
        }
        
        response = client.put("/api/mcp/nonexistent/toggle", json={"enabled": False})
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('backend.api.mcp_endpoints.get_config')
    def test_toggle_mcp_server_no_change(self, mock_get_config, client):
        """Test PUT /api/mcp/{name}/toggle when status is already set."""
        mock_get_config.return_value = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "description": "Gmail MCP Server",
                "enabled": True  # Already enabled
            }
        }
        
        response = client.put("/api/mcp/gmail/toggle", json={"enabled": True})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["server_name"] == "gmail"
        assert data["enabled"] is True
        assert "already enabled" in data["message"] 