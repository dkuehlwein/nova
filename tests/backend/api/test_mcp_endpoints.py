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
    
    @patch('backend.api.mcp_endpoints.load_mcp_yaml')
    @patch('backend.api.mcp_endpoints.mcp_manager.check_server_health_with_tools_count')
    def test_get_mcp_servers_empty_config(self, mock_health_check, mock_load_yaml, client):
        """Test GET /api/mcp with empty configuration."""
        mock_load_yaml.return_value = {}
        
        response = client.get("/api/mcp/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["servers"] == []
        assert data["total_servers"] == 0
        assert data["healthy_servers"] == 0
        assert data["enabled_servers"] == 0
    
    @patch('backend.api.mcp_endpoints.load_mcp_yaml')
    @patch('backend.api.mcp_endpoints.mcp_manager.check_server_health_with_tools_count')
    async def test_get_mcp_servers_with_config(self, mock_health_check, mock_load_yaml, client):
        """Test GET /api/mcp with server configuration."""
        mock_load_yaml.return_value = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health", 
                "description": "Gmail MCP Server",
                "enabled": True
            },
            "disabled_server": {
                "url": "http://localhost:8003/mcp",
                "health_url": "http://localhost:8003/health",
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
    
    @patch('backend.api.mcp_endpoints.load_mcp_yaml')
    @patch('utils.config_loader.get_mcp_config_loader')
    @patch('backend.api.mcp_endpoints.publish')
    def test_toggle_mcp_server_enable(self, mock_publish, mock_get_loader, mock_load_yaml, client):
        """Test PUT /api/mcp/{name}/toggle to enable server."""
        mock_load_yaml.return_value = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health",
                "description": "Gmail MCP Server",
                "enabled": False  # Currently disabled
            }
        }
        
        # Mock the config loader
        mock_loader = MagicMock()
        mock_get_loader.return_value = mock_loader
        
        response = client.put("/api/mcp/gmail/toggle", json={"enabled": True})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["server_name"] == "gmail"
        assert data["enabled"] is True
        assert "enabled" in data["message"]
        
        # Verify config was saved through the loader
        mock_loader.save_config.assert_called_once()
        saved_config = mock_loader.save_config.call_args[0][0]
        assert saved_config["gmail"]["enabled"] is True
        
        # Verify event was published
        mock_publish.assert_called_once()
    
    @patch('backend.api.mcp_endpoints.load_mcp_yaml')
    def test_toggle_mcp_server_not_found(self, mock_load_yaml, client):
        """Test PUT /api/mcp/{name}/toggle with non-existent server."""
        mock_load_yaml.return_value = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health",
                "description": "Gmail MCP Server",
                "enabled": True
            }
        }
        
        response = client.put("/api/mcp/nonexistent/toggle", json={"enabled": False})
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('backend.api.mcp_endpoints.load_mcp_yaml')
    def test_toggle_mcp_server_no_change(self, mock_load_yaml, client):
        """Test PUT /api/mcp/{name}/toggle when status is already set."""
        mock_load_yaml.return_value = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health", 
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