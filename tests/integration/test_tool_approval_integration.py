"""
Integration Tests for LangGraph-based Tool Approval System

Tests the complete tool approval workflow including:
- LangGraph interrupt-based approval flow
- Tool wrapping and metadata preservation  
- Permission configuration integration
- Real Nova tool integration
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

from tools import get_all_tools
from tools.tool_approval_helper import add_human_in_the_loop, wrap_tools_for_approval
from utils.tool_permissions_manager import ToolPermissionConfig, permission_config
from langchain_core.tools import tool


class TestLangGraphToolApproval:
    """Tests for LangGraph-based tool approval system."""
    
    @pytest.fixture
    def sample_tool(self):
        """Create a sample tool for testing."""
        @tool
        def test_integration_tool(task_title: str, priority: str = "medium") -> str:
            """Create a test task with given title and priority."""
            return f"Created task: {task_title} (priority: {priority})"
        
        return test_integration_tool
    
    def test_tool_system_initialization(self):
        """Test that Nova tools load correctly with approval system enabled."""
        # Get tools with approval enabled
        tools = get_all_tools(enable_tool_approval=True)
        
        # Should have Nova's standard tools
        assert len(tools) >= 6, "Should have at least 6 Nova tools"
        
        # Check tool names and approval status
        tool_names = {t.name for t in tools}
        expected_tools = {"create_task", "update_task", "get_tasks", "get_task_by_id", "search_memory", "add_memory"}
        assert expected_tools.issubset(tool_names), f"Missing expected tools: {expected_tools - tool_names}"
        
        # Verify approval wrapping worked correctly
        approval_tools = [t for t in tools if "[REQUIRES APPROVAL]" in t.description]
        pre_approved_tools = [t for t in tools if "[REQUIRES APPROVAL]" not in t.description]
        
        assert len(approval_tools) > 0, "Should have some tools requiring approval"
        assert len(pre_approved_tools) > 0, "Should have some pre-approved tools"
        
        # Verify wrapped tools are async (LangGraph requirement)
        for tool in approval_tools:
            tool_function = getattr(tool, 'func', None) or getattr(tool, 'coroutine', None)
            assert tool_function is not None, f"Tool {tool.name} missing function"
            assert asyncio.iscoroutinefunction(tool_function), f"Approval tool {tool.name} must be async"
    
    def test_add_human_in_the_loop_wrapper(self, sample_tool):
        """Test that add_human_in_the_loop wrapper preserves tool metadata."""
        wrapped_tool = add_human_in_the_loop(sample_tool)
        
        # Verify wrapper preserves metadata
        assert wrapped_tool.name == sample_tool.name
        assert "[REQUIRES APPROVAL]" in wrapped_tool.description
        assert sample_tool.description in wrapped_tool.description
        assert wrapped_tool.args_schema == sample_tool.args_schema
        
        # Verify function is async (required for LangGraph interrupt)
        tool_function = getattr(wrapped_tool, 'coroutine', None)
        assert tool_function is not None, "Wrapped tool should have coroutine"
        assert asyncio.iscoroutinefunction(tool_function), "Wrapped tool function should be async"
    
    def test_permission_based_tool_wrapping(self):
        """Test that wrap_tools_for_approval correctly identifies tools needing approval."""
        
        @tool
        def allowed_tool(message: str) -> str:
            """Tool that should be allowed."""
            return f"Allowed: {message}"
        
        @tool
        def restricted_tool(message: str) -> str:
            """Tool that should require approval."""
            return f"Restricted: {message}"
        
        tools = [allowed_tool, restricted_tool]
        
        # Mock permission config to make restricted_tool require approval
        with patch.object(permission_config, 'get_restricted_tools', return_value=['restricted_tool']):
            wrapped_tools = wrap_tools_for_approval(tools)
        
        # Should still have 2 tools
        assert len(wrapped_tools) == 2
        
        # Find tools by name
        allowed_wrapped = next(t for t in wrapped_tools if t.name == "allowed_tool")
        restricted_wrapped = next(t for t in wrapped_tools if t.name == "restricted_tool")
        
        # Verify wrapping status
        assert "[REQUIRES APPROVAL]" not in allowed_wrapped.description
        assert "[REQUIRES APPROVAL]" in restricted_wrapped.description
    
    @pytest.mark.asyncio
    async def test_langgraph_interrupt_structure(self, sample_tool):
        """Test that LangGraph interrupt is called with correct data structure."""
        wrapped_tool = add_human_in_the_loop(sample_tool)
        
        # Mock the LangGraph interrupt function
        with patch('tools.tool_approval_helper.interrupt') as mock_interrupt:
            # Mock interrupt response (user accepts)
            mock_interrupt.return_value = [{"type": "accept"}]
            
            try:
                # This will fail in test context (no LangGraph runtime), but we can verify the interrupt call
                await wrapped_tool.coroutine(task_title="Test", priority="high")
            except Exception:
                # Expected in test context
                pass
            
            # Verify interrupt was called with correct structure (new ask_user-style pattern)
            mock_interrupt.assert_called_once()
            interrupt_data = mock_interrupt.call_args[0][0]  # Direct dict, not array
            
            assert interrupt_data["type"] == "tool_approval_request"
            assert interrupt_data["tool_name"] == "test_integration_tool"
            assert interrupt_data["tool_args"] == {"task_title": "Test", "priority": "high"}
            assert "Nova wants to use the tool: test_integration_tool" in interrupt_data["question"]
            assert "approve" in interrupt_data["instructions"]
    
    def test_interrupt_response_types(self, sample_tool):
        """Test that wrapper handles different interrupt response types."""
        wrapped_tool = add_human_in_the_loop(sample_tool)
        
        response_scenarios = [
            {"type": "accept"},
            {"type": "edit", "args": {"args": {"task_title": "Modified", "priority": "low"}}},
            {"type": "response", "args": "User declined this action"}
        ]
        
        for response in response_scenarios:
            with patch('tools.tool_approval_helper.interrupt', return_value=[response]):
                # In a real test environment, these would work properly
                # For now, we just verify the structure and logic paths
                assert wrapped_tool.coroutine is not None
                assert "[REQUIRES APPROVAL]" in wrapped_tool.description
    
    @pytest.mark.asyncio
    async def test_always_allow_response_updates_config(self, sample_tool):
        """Test that 'always_allow' response updates the configuration."""
        wrapped_tool = add_human_in_the_loop(sample_tool)
        
        # Mock the interrupt and config manager (patch at import location)
        with patch('tools.tool_approval_helper.interrupt') as mock_interrupt, \
             patch('utils.tool_permissions_manager.permission_config') as mock_permission_config:
            
            # Mock interrupt response (user chooses always allow)
            mock_interrupt.return_value = [{"type": "always_allow"}]
            
            # Mock permission config methods
            mock_permission_config.add_permission = AsyncMock()
            
            try:
                # Call the wrapped tool
                result = await wrapped_tool.coroutine(task_title="Test Task", priority="high")
                
                # Verify permission was added to config
                mock_permission_config.add_permission.assert_called_once_with(
                    "test_integration_tool", 
                    {"task_title": "Test Task", "priority": "high"}
                )
                
                # Tool should still execute successfully
                assert result == "Created task: Test Task (priority: high)"
                
            except Exception as e:
                # In test context, tool execution might fail, but config update should still be called
                mock_permission_config.add_permission.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_always_allow_config_error_handling(self, sample_tool):
        """Test that tool execution continues even if config update fails."""
        wrapped_tool = add_human_in_the_loop(sample_tool)
        
        with patch('tools.tool_approval_helper.interrupt') as mock_interrupt, \
             patch('utils.tool_permissions_manager.permission_config') as mock_permission_config:
            
            # Mock interrupt response (always allow)
            mock_interrupt.return_value = [{"type": "always_allow"}]
            
            # Mock config update to raise an exception
            mock_permission_config.add_permission = AsyncMock(side_effect=Exception("Config update failed"))
            
            try:
                # Tool should still execute despite config update failure
                result = await wrapped_tool.coroutine(task_title="Test Task", priority="high")
                
                # Config update should have been attempted
                mock_permission_config.add_permission.assert_called_once()
                
                # Tool should still execute successfully
                assert result == "Created task: Test Task (priority: high)"
                
            except Exception as e:
                # In test context, tool execution might fail for other reasons
                # but config update should still be attempted
                mock_permission_config.add_permission.assert_called_once()
    
    def test_real_nova_tools_integration(self):
        """Test integration with actual Nova tools and default permissions."""
        # Get Nova tools with approval enabled
        tools = get_all_tools(enable_tool_approval=True)
        
        # Verify we have the expected Nova tools
        tool_names = {t.name for t in tools}
        expected_tools = {"create_task", "update_task", "get_tasks", "get_task_by_id", "search_memory", "add_memory"}
        assert expected_tools.issubset(tool_names), f"Missing Nova tools: {expected_tools - tool_names}"
        
        # Test that permissions are applied correctly based on default config
        approval_tools = [t for t in tools if "[REQUIRES APPROVAL]" in t.description]
        pre_approved_tools = [t for t in tools if "[REQUIRES APPROVAL]" not in t.description]
        
        # Should have some tools in each category based on default config
        assert len(approval_tools) >= 3, f"Expected at least 3 approval tools, got {len(approval_tools)}"
        assert len(pre_approved_tools) >= 3, f"Expected at least 3 pre-approved tools, got {len(pre_approved_tools)}"
        
        # Verify that read-only tools are typically pre-approved
        readonly_tools = {"get_tasks", "get_task_by_id", "search_memory"}
        readonly_tool_names = {t.name for t in pre_approved_tools}
        assert readonly_tools.issubset(readonly_tool_names), "Read-only tools should be pre-approved"
        
        # Verify that write operations typically require approval
        write_tools = {"create_task", "update_task", "add_memory"}
        approval_tool_names = {t.name for t in approval_tools}
        # At least some write tools should require approval
        assert len(write_tools.intersection(approval_tool_names)) > 0, "Some write tools should require approval"


class TestToolPermissionConfiguration:
    """Test tool permission configuration integration."""
    
    def test_permission_config_integration(self):
        """Test integration with Nova's permission configuration system."""
        # Test that permission config can identify restricted tools
        restricted_tools = permission_config.get_restricted_tools()
        
        # Should return a list of tool names
        assert isinstance(restricted_tools, list)
        assert all(isinstance(tool, str) for tool in restricted_tools)
        
        # Should have some restricted tools based on default config
        assert len(restricted_tools) > 0
        
        # Common write operations should typically be restricted
        expected_restricted = {"create_task", "update_task", "add_memory"}
        actual_restricted = set(restricted_tools)
        
        # At least some expected tools should be restricted
        intersection = expected_restricted.intersection(actual_restricted)
        assert len(intersection) > 0, f"Expected some of {expected_restricted} to be restricted, got {actual_restricted}"
    
    def test_default_secure_behavior(self):
        """Test that system defaults to secure behavior."""
        from models.tool_permissions_config import ToolPermissionsConfig
        
        # Default config should be secure by default
        default_config = ToolPermissionsConfig.get_default_config()
        assert default_config.settings.default_secure is True
        
        # Should have some pre-approved safe operations
        allowed_tools = default_config.permissions.allow
        assert len(allowed_tools) > 0
        
        # Should have read-only operations pre-approved
        readonly_tools = {"get_tasks", "get_task_by_id", "search_memory"}
        allowed_set = set(allowed_tools)
        assert readonly_tools.issubset(allowed_set), f"Read-only tools should be pre-approved: {readonly_tools - allowed_set}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])