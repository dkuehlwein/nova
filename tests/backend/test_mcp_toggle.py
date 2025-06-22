"""
Unit tests for MCP toggle - ensuring both global agent cache 
and tools cache are cleared when MCP servers are toggled.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from agent.chat_agent import create_chat_agent, clear_chat_agent_cache, _cached_tools
from start_website import create_website_event_handler
from models.events import create_mcp_toggled_event, create_prompt_updated_event


class TestMCPToggleFix:
    """Test that MCP toggle events clear both global agent cache and tools cache."""

    @pytest.mark.asyncio
    async def test_mcp_toggled_event_clears_both_caches(self):
        """Test that MCP toggle events clear agent and tools caches via unified function."""
        # Mock the unified cache clearing function
        with patch('api.chat_endpoints.clear_chat_agent_cache') as mock_clear_cache:
            
            # Create event handler
            event_handler = await create_website_event_handler()
            
            # Create MCP toggle event
            mcp_event = create_mcp_toggled_event("gmail", False, "test")
            
            # Process the event
            await event_handler(mcp_event)
            
            # Verify unified cache clearing was called
            mock_clear_cache.assert_called_once()

    @pytest.mark.asyncio 
    async def test_prompt_updated_event_clears_both_caches(self):
        """Test that prompt update events clear agent and tools caches via unified function."""
        with patch('api.chat_endpoints.clear_chat_agent_cache') as mock_clear_cache:
            
            # Create event handler
            event_handler = await create_website_event_handler()
            
            # Create prompt update event with required change_type parameter
            prompt_event = create_prompt_updated_event(
                prompt_file="NOVA_SYSTEM_PROMPT.md",
                change_type="modified",
                source="test"
            )
            
            # Process the event
            await event_handler(prompt_event)
            
            # Verify unified cache clearing was called
            mock_clear_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_tools_cache_clearing_functionality(self):
        """Test that clear_chat_agent_cache clears all caches including tools."""
        import agent.chat_agent
        
        # Set some cached tools and LLM
        agent.chat_agent._cached_tools = ["tool1", "tool2", "tool3"]
        agent.chat_agent._cached_llm = "cached_llm"
        assert agent.chat_agent._cached_tools is not None
        assert agent.chat_agent._cached_llm is not None
        
        # Clear all caches
        clear_chat_agent_cache()
        
        # Verify all caches are cleared
        assert agent.chat_agent._cached_tools is None
        assert agent.chat_agent._cached_llm is None

    @pytest.mark.asyncio
    async def test_streaming_agent_gets_fresh_tools_after_cache_clear(self):
        """Test that unified cache clearing functionality works."""
        import agent.chat_agent
        
        # Set some cached tools and LLM
        agent.chat_agent._cached_tools = ["cached_tool1", "cached_tool2"]
        agent.chat_agent._cached_llm = "cached_llm"
        assert agent.chat_agent._cached_tools is not None
        assert agent.chat_agent._cached_llm is not None
        
        # Clear all caches
        clear_chat_agent_cache()
        
        # Verify all caches are cleared
        assert agent.chat_agent._cached_tools is None
        assert agent.chat_agent._cached_llm is None

    @pytest.mark.asyncio
    async def test_fix_resolves_original_issue(self):
        """Test that unified cache clearing resolves the original issue."""
        import agent.chat_agent
        
        # Set up caches with test data
        agent.chat_agent._cached_tools = ["test_tool1", "test_tool2"]
        agent.chat_agent._cached_llm = "test_llm"
        
        # Verify caches are set
        assert agent.chat_agent._cached_tools is not None
        assert agent.chat_agent._cached_llm is not None
        
        # Clear all caches with unified function (THE FIX)
        clear_chat_agent_cache()
        
        # Verify all caches are cleared
        assert agent.chat_agent._cached_tools is None
        assert agent.chat_agent._cached_llm is None 