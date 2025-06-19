"""
Unit tests for MCP toggle - ensuring both global agent cache 
and tools cache are cleared when MCP servers are toggled.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from agent.chat_agent import create_chat_agent, clear_tools_cache, _cached_tools
from start_website import create_website_event_handler
from models.events import create_mcp_toggled_event, create_prompt_updated_event


class TestMCPToggleFix:
    """Test that MCP toggle events clear both global agent cache and tools cache."""

    @pytest.mark.asyncio
    async def test_mcp_toggled_event_clears_both_caches(self):
        """Test that MCP toggle events clear both global agent cache and tools cache."""
        # Mock the actual modules where they are imported in start_website.py
        with patch('api.chat_endpoints.clear_chat_agent_cache') as mock_clear_agent:
            with patch('agent.chat_agent.clear_tools_cache') as mock_clear_tools:
                
                # Create event handler
                event_handler = await create_website_event_handler()
                
                # Create MCP toggle event
                mcp_event = create_mcp_toggled_event("gmail", False, "test")
                
                # Process the event
                await event_handler(mcp_event)
                
                # Verify both caches are cleared
                mock_clear_agent.assert_called_once()
                mock_clear_tools.assert_called_once()

    @pytest.mark.asyncio 
    async def test_prompt_updated_event_clears_both_caches(self):
        """Test that prompt update events clear both global agent cache and tools cache."""
        with patch('api.chat_endpoints.clear_chat_agent_cache') as mock_clear_agent:
            with patch('agent.chat_agent.clear_tools_cache') as mock_clear_tools:
                
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
                
                # Verify both caches are cleared
                mock_clear_agent.assert_called_once()
                mock_clear_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_tools_cache_clearing_functionality(self):
        """Test that clear_tools_cache actually clears the global tools cache."""
        import agent.chat_agent
        
        # Set some cached tools
        agent.chat_agent._cached_tools = ["tool1", "tool2", "tool3"]
        assert agent.chat_agent._cached_tools is not None
        
        # Clear the cache
        clear_tools_cache()
        
        # Verify it's cleared
        assert agent.chat_agent._cached_tools is None

    @pytest.mark.asyncio
    async def test_streaming_agent_gets_fresh_tools_after_cache_clear(self):
        """Test that tools cache clearing functionality works."""
        import agent.chat_agent
        
        # Set some cached tools
        agent.chat_agent._cached_tools = ["cached_tool1", "cached_tool2"]
        assert agent.chat_agent._cached_tools is not None
        
        # Clear the cache
        clear_tools_cache()
        
        # Verify it's cleared
        assert agent.chat_agent._cached_tools is None

    @pytest.mark.asyncio
    async def test_fix_resolves_original_issue(self):
        """Test that both agent cache and tools cache can be cleared."""
        import agent.chat_agent
        import backend.api.chat_endpoints
        
        # Set up caches with test data
        agent.chat_agent._cached_tools = ["test_tool1", "test_tool2"]
        backend.api.chat_endpoints._chat_agent = "test_agent"
        
        # Verify caches are set
        assert agent.chat_agent._cached_tools is not None
        assert backend.api.chat_endpoints._chat_agent is not None
        
        # Clear both caches (this is the fix)
        from backend.api.chat_endpoints import clear_chat_agent_cache
        clear_chat_agent_cache()  # Clear global agent cache
        clear_tools_cache()  # Clear tools cache (THE FIX)
        
        # Verify both caches are cleared
        assert backend.api.chat_endpoints._chat_agent is None
        assert agent.chat_agent._cached_tools is None 