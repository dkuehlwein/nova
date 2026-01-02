"""
Tests for Tool Permissions API Endpoints

Tests the FastAPI endpoints for managing tool permissions including:
- GET /tool-permissions
- POST /tool-permissions/add
- POST /tool-permissions/remove
- POST /tool-permissions/clear-cache
- GET /tool-permissions/test/{tool_name}
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

from api.tool_permissions_endpoints import router
from models.tool_permissions_config import ToolPermissionsConfig
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)

client = TestClient(app)


class TestToolPermissionsAPI:
    """Test the tool permissions API endpoints."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock tool permissions configuration."""
        config = ToolPermissionsConfig.get_default_config()
        return config
    
    def test_get_tool_permissions_success(self, mock_config):
        """Test successful retrieval of tool permissions."""
        with patch('api.tool_permissions_endpoints.get_config', return_value=mock_config):
            response = client.get("/tool-permissions")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "permissions" in data
            assert "settings" in data
            assert "allow" in data["permissions"]
            assert "deny" in data["permissions"]
            
            # Check default values
            assert "get_tasks" in data["permissions"]["allow"]
            assert "mcp_tool(*)" in data["permissions"]["deny"]
            assert data["settings"]["default_secure"] is True
    
    def test_get_tool_permissions_config_error(self):
        """Test error handling when config loading fails."""
        with patch('api.tool_permissions_endpoints.get_config', side_effect=Exception("Config error")):
            response = client.get("/tool-permissions")
            
            assert response.status_code == 500
            assert "Failed to get tool permissions" in response.json()["detail"]
    
    def test_add_permission_success(self, mock_config):
        """Test successfully adding a tool permission."""
        with patch('api.tool_permissions_endpoints.get_config', return_value=mock_config), \
             patch('api.tool_permissions_endpoints.save_config') as mock_save, \
             patch('api.tool_permissions_endpoints.clear_chat_agent_cache') as mock_clear:
            
            response = client.post("/tool-permissions/add", json={
                "tool_name": "new_tool",
                "tool_args": {"param": "value"}
            })
            
            assert response.status_code == 200
            assert "Permission added for new_tool" in response.json()["message"]
            
            # Verify config was saved and cache cleared
            mock_save.assert_called_once_with("tool_permissions", mock_config)
            mock_clear.assert_called_once()
    
    def test_add_permission_no_args(self, mock_config):
        """Test adding permission for tool with no arguments."""
        with patch('api.tool_permissions_endpoints.get_config', return_value=mock_config), \
             patch('api.tool_permissions_endpoints.save_config') as mock_save:
            
            response = client.post("/tool-permissions/add", json={
                "tool_name": "simple_tool"
            })
            
            assert response.status_code == 200
            # Should add simple tool name to allow list
            assert "simple_tool" in mock_config.permissions.allow
    
    def test_add_permission_duplicate(self, mock_config):
        """Test adding duplicate permission (should be idempotent)."""
        # Pre-add the permission
        mock_config.permissions.allow.append("duplicate_tool")
        
        with patch('api.tool_permissions_endpoints.get_config', return_value=mock_config), \
             patch('api.tool_permissions_endpoints.save_config') as mock_save:
            
            response = client.post("/tool-permissions/add", json={
                "tool_name": "duplicate_tool"
            })
            
            assert response.status_code == 200
            # Should still succeed but not add duplicate
            assert mock_config.permissions.allow.count("duplicate_tool") == 1
    
    def test_remove_permission_from_allow_list(self, mock_config):
        """Test removing permission from allow list."""
        # Pre-add permission to remove
        mock_config.permissions.allow.append("removable_tool")
        
        with patch('api.tool_permissions_endpoints.get_config', return_value=mock_config), \
             patch('api.tool_permissions_endpoints.save_config') as mock_save, \
             patch('api.tool_permissions_endpoints.clear_chat_agent_cache') as mock_clear:
            
            response = client.post("/tool-permissions/remove", json={
                "pattern": "removable_tool"
            })
            
            assert response.status_code == 200
            assert "Permission removed: removable_tool" in response.json()["message"]
            assert "removable_tool" not in mock_config.permissions.allow
            mock_save.assert_called_once()
            mock_clear.assert_called_once()
    
    def test_remove_permission_from_deny_list(self, mock_config):
        """Test removing permission from deny list."""
        # Pre-add permission to deny list
        mock_config.permissions.deny.append("denied_tool")
        
        with patch('api.tool_permissions_endpoints.get_config', return_value=mock_config), \
             patch('api.tool_permissions_endpoints.save_config') as mock_save:
            
            response = client.post("/tool-permissions/remove", json={
                "pattern": "denied_tool"
            })
            
            assert response.status_code == 200
            assert "denied_tool" not in mock_config.permissions.deny
    
    def test_remove_nonexistent_permission(self, mock_config):
        """Test removing permission that doesn't exist."""
        with patch('api.tool_permissions_endpoints.get_config', return_value=mock_config), \
             patch('api.tool_permissions_endpoints.save_config') as mock_save:
            
            response = client.post("/tool-permissions/remove", json={
                "pattern": "nonexistent_tool"
            })
            
            assert response.status_code == 200
            # Should still succeed but not save config since nothing changed
            mock_save.assert_not_called()
    
    def test_clear_cache_success(self):
        """Test cache clearing endpoint."""
        with patch('api.tool_permissions_endpoints.clear_chat_agent_cache') as mock_clear:
            response = client.post("/tool-permissions/clear-cache")
            
            assert response.status_code == 200
            assert "cache cleared" in response.json()["message"]
            mock_clear.assert_called_once()
    
    def test_clear_cache_error(self):
        """Test cache clearing error handling."""
        with patch('api.tool_permissions_endpoints.clear_chat_agent_cache', side_effect=Exception("Cache error")):
            response = client.post("/tool-permissions/clear-cache")
            
            assert response.status_code == 500
            assert "Failed to clear cache" in response.json()["detail"]
    
    def test_permission_test_error(self, mock_config):
        """Test permission testing error handling."""
        with patch('api.tool_permissions_endpoints.ToolApprovalInterceptor', side_effect=Exception("Test error")):
            response = client.get("/tool-permissions/test/test_tool")
            
            assert response.status_code == 500
            assert "Failed to test permission" in response.json()["detail"]


class TestToolPermissionsAPIIntegration:
    """Integration tests for the tool permissions API."""
    
    def test_add_and_remove_workflow(self):
        """Test complete add and remove workflow."""
        mock_config = ToolPermissionsConfig.get_default_config()
        
        with patch('api.tool_permissions_endpoints.get_config', return_value=mock_config), \
             patch('api.tool_permissions_endpoints.save_config') as mock_save, \
             patch('api.tool_permissions_endpoints.clear_chat_agent_cache'):
            
            # Add permission
            response = client.post("/tool-permissions/add", json={
                "tool_name": "workflow_tool",
                "tool_args": {"action": "test"}
            })
            assert response.status_code == 200
            
            # Verify it was added
            assert "workflow_tool(action=test)" in mock_config.permissions.allow
            
            # Remove permission
            response = client.post("/tool-permissions/remove", json={
                "pattern": "workflow_tool(action=test)"
            })
            assert response.status_code == 200
            
            # Verify it was removed
            assert "workflow_tool(action=test)" not in mock_config.permissions.allow
    


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])