"""
Test agent reloading functionality.

Focused tests for cache clearing and prompt loading behavior.
"""

import pytest
from unittest.mock import patch, Mock

from agent.chat_agent import clear_chat_agent_cache


class TestAgentReloading:
    """Test agent reloading with simplified approach."""
    
    @pytest.mark.asyncio
    async def test_chat_agent_cache_clearing(self):
        """Test that chat agent cache is cleared properly."""
        import agent.chat_agent
        
        # Set up some cached components
        agent.chat_agent._cached_tools = ["tool1", "tool2"]
        agent.chat_agent._cached_llm = "cached_llm"
        
        # Call the cache clearing function
        clear_chat_agent_cache()
        
        # Verify all component caches are cleared
        assert agent.chat_agent._cached_tools is None
        assert agent.chat_agent._cached_llm is None
    
    @pytest.mark.asyncio
    async def test_prompt_loading_always_current(self):
        """Test that get_nova_system_prompt always returns current content."""
        from agent.prompts import get_nova_system_prompt
        
        # Since get_nova_system_prompt() calls the prompt loader which reads from file,
        # it should always return current content without caching
        prompt1 = await get_nova_system_prompt()
        prompt2 = await get_nova_system_prompt()
        
        # Both calls should return the same content (current file content)
        assert prompt1 == prompt2
        assert len(prompt1) > 0
        assert "Nova" in prompt1


class TestCacheManagement:
    """Test cache management for tools and LLM."""
    
    @pytest.mark.asyncio
    async def test_use_cache_parameter_behavior(self):
        """Test that use_cache parameter controls caching behavior."""
        from agent.chat_agent import get_all_tools_with_mcp
        import agent.chat_agent
        
        # Clear cache initially
        clear_chat_agent_cache()
        assert agent.chat_agent._cached_tools is None
        
        # Mock the underlying functions to avoid real network calls
        with patch('agent.chat_agent.get_all_tools') as mock_local_tools:
            with patch('agent.chat_agent.mcp_manager.get_tools') as mock_mcp_tools:
                
                mock_local_tools.return_value = ["local_tool"]
                mock_mcp_tools.return_value = ["mcp_tool"]
                
                # First call with use_cache=True - should cache tools
                tools1 = await get_all_tools_with_mcp(use_cache=True)
                assert agent.chat_agent._cached_tools is not None
                assert len(tools1) == 2
                assert mock_local_tools.call_count == 1
                assert mock_mcp_tools.call_count == 1
                
                # Reset call counts
                mock_local_tools.reset_mock()
                mock_mcp_tools.reset_mock()
                
                # Second call with use_cache=True - should use cache (no calls)
                tools2 = await get_all_tools_with_mcp(use_cache=True)
                assert tools2 is tools1  # Should be same cached instance
                assert mock_local_tools.call_count == 0
                assert mock_mcp_tools.call_count == 0
                
                # Third call with use_cache=False - should clear cache and reload
                tools3 = await get_all_tools_with_mcp(use_cache=False)
                assert len(tools3) == 2
                assert mock_local_tools.call_count == 1
                assert mock_mcp_tools.call_count == 1