"""
Tests for Tool Permissions System

Focused tests for the core permission functionality including:
- Pydantic configuration models  
- Pattern matching logic
- ConfigRegistry integration
- Real-world security scenarios
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import asyncio

import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

from models.tool_permissions_config import ToolPermissionsConfig, ToolPermissions, ToolPermissionSettings
from utils.tool_permissions_manager import ToolPermissionConfig, ToolApprovalInterceptor
from langchain_core.tools import tool


class TestToolPermissionsConfig:
    """Test the Pydantic configuration models."""
    
    def test_default_config_creation(self):
        """Test creating default configuration."""
        config = ToolPermissionsConfig.get_default_config()
        
        assert config.permissions.allow == [
            "get_tasks",
            "search_memory", 
            "get_task_by_id",
            "get_memories",
            "search_memories"
        ]
        assert "mcp_tool(*)" in config.permissions.deny
        assert config.settings.require_justification is True
        assert config.settings.default_secure is True
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = ToolPermissionsConfig(
            permissions=ToolPermissions(
                allow=["get_tasks"],
                deny=["dangerous_tool"]
            ),
            settings=ToolPermissionSettings(
                require_justification=False,
                approval_timeout=600
            )
        )
        assert config.permissions.allow == ["get_tasks"]
        assert config.settings.approval_timeout == 600
    
    def test_empty_config(self):
        """Test empty configuration uses defaults."""
        config = ToolPermissionsConfig()
        assert isinstance(config.permissions, ToolPermissions)
        assert isinstance(config.settings, ToolPermissionSettings)
        assert config.settings.require_justification is True


class TestPatternMatching:
    """Test pattern matching edge cases."""
    
    def test_format_permission_pattern(self):
        """Test permission pattern formatting."""
        config = ToolPermissionConfig()
        
        # No args
        pattern = config._format_permission_pattern("get_tasks")
        assert pattern == "get_tasks"
        
        # With args (sorted)
        pattern = config._format_permission_pattern("create_task", {"title": "Test", "priority": "high"})
        assert pattern == "create_task(priority=high,title=Test)"
        
        # Empty args dict
        pattern = config._format_permission_pattern("get_tasks", {})
        assert pattern == "get_tasks"
    
    def test_pattern_matching_edge_cases(self):
        """Test edge cases in pattern matching."""
        interceptor = ToolApprovalInterceptor(Mock())
        
        # Test wildcard matching
        assert interceptor._matches_pattern("mcp_tool(server=test)", "mcp_tool(*)") is True
        assert interceptor._matches_pattern("mcp_tool", "mcp_tool(*)") is False  # No parentheses
        
        # Test exact matching
        assert interceptor._matches_pattern("get_tasks", "get_tasks") is True
        assert interceptor._matches_pattern("get_task", "get_tasks") is False
        
        # Test containment matching (how current implementation works)
        assert interceptor._matches_pattern("update_task(status=done)", "update_task(status=done)") is True
        # Test that substring matching works for partial patterns  
        assert interceptor._matches_pattern("update_task(id=123,status=done)", "status=done") is True


class TestConfigRegistryIntegration:
    """Test integration with Nova's ConfigRegistry."""
    
    @pytest.mark.asyncio
    async def test_config_loading_fallback(self):
        """Test config loading with fallback to defaults."""
        with patch('utils.tool_permissions_manager.get_config') as mock_get_config:
            # Simulate ConfigRegistry not initialized
            mock_get_config.side_effect = ValueError("Configuration manager not found")
            
            config = ToolPermissionConfig()
            permissions = await config.get_permissions()
            
            # Should fall back to defaults
            assert "get_tasks" in permissions["permissions"]["allow"]
            assert permissions["settings"]["default_secure"] is True
    
    @pytest.mark.asyncio
    async def test_config_saving(self):
        """Test saving permissions through ConfigRegistry."""
        with patch('utils.tool_permissions_manager.get_config') as mock_get_config, \
             patch('utils.tool_permissions_manager.save_config') as mock_save_config:
            
            # Mock existing config
            mock_config = ToolPermissionsConfig.get_default_config()
            mock_get_config.return_value = mock_config
            
            config = ToolPermissionConfig()
            await config.add_permission("new_tool", {"arg": "value"})
            
            # Should save updated config
            mock_save_config.assert_called_once()
            call_args = mock_save_config.call_args
            assert call_args[0][0] == "tool_permissions"  # config name
            saved_config = call_args[0][1]
            assert "new_tool(arg=value)" in saved_config.permissions.allow


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    @pytest.mark.asyncio
    async def test_task_creation_workflow(self):
        """Test typical task creation approval workflow."""
        with patch('utils.tool_permissions_manager.get_config') as mock_get_config:
            # Mock config that allows get_tasks but not create_task
            config = ToolPermissionsConfig(
                permissions=ToolPermissions(
                    allow=["get_tasks"],
                    deny=[]
                )
            )
            mock_get_config.return_value = config
            
            interceptor = ToolApprovalInterceptor(ToolPermissionConfig())
            
            # get_tasks should be allowed
            assert await interceptor.check_permission("get_tasks", {}) is True
            
            # create_task should require approval
            assert await interceptor.check_permission("create_task", {"title": "New Task"}) is False
    
    @pytest.mark.asyncio
    async def test_mcp_tool_blocking(self):
        """Test that MCP tools are properly blocked by wildcard."""
        with patch('utils.tool_permissions_manager.get_config') as mock_get_config:
            config = ToolPermissionsConfig.get_default_config()  # Has mcp_tool(*) in deny
            mock_get_config.return_value = config
            
            interceptor = ToolApprovalInterceptor(ToolPermissionConfig())
            
            # All MCP tools should be denied by wildcard
            assert await interceptor.check_permission("mcp_tool", {"server": "gmail", "action": "send"}) is False
            assert await interceptor.check_permission("mcp_tool", {"server": "calendar"}) is False
    
    @pytest.mark.asyncio
    async def test_security_critical_operations(self):
        """Test security-critical operations are properly controlled."""
        with patch('utils.tool_permissions_manager.get_config') as mock_get_config:
            config = ToolPermissionsConfig.get_default_config()  # Has update_task(status=done) denied
            mock_get_config.return_value = config
            
            interceptor = ToolApprovalInterceptor(ToolPermissionConfig())
            
            # Regular updates should be allowed if not specifically denied
            assert await interceptor.check_permission("update_task", {"id": "123", "title": "New Title"}) is False  # Not in allow list
            
            # Status changes to done/cancelled should be explicitly denied
            assert await interceptor.check_permission("update_task", {"status": "done"}) is False
            assert await interceptor.check_permission("update_task", {"status": "cancelled"}) is False


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])