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
        with patch('start_website.clear_chat_agent_cache') as mock_clear_agent:
            with patch('start_website.clear_tools_cache') as mock_clear_tools:
                
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
        with patch('start_website.clear_chat_agent_cache') as mock_clear_agent:
            with patch('start_website.clear_tools_cache') as mock_clear_tools:
                
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
        """Test that streaming-style agents get fresh tools after cache is cleared."""
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
                        with patch('backend.agent.chat_agent.mcp_manager.get_client_and_tools') as mock_mcp:
                            
                            # Setup mocks
                            mock_llm.return_value = Mock()
                            mock_checkpointer.return_value = Mock()
                            mock_create_react.return_value = Mock()
                            mock_local_tools.return_value = ["local_tool"]
                            
                            # First call - with MCP tools
                            mock_mcp.return_value = (Mock(), ["mcp_tool1", "mcp_tool2"])
                            agent1 = await create_chat_agent()
                            
                            # Verify tools were fetched
                            assert mock_mcp.call_count == 1
                            first_call_tools = mock_create_react.call_args.kwargs['tools']
                            assert len(first_call_tools) == 3  # 1 local + 2 MCP
                            
                            # Simulate MCP server being disabled - change mock return
                            mock_mcp.return_value = (Mock(), [])  # No MCP tools
                            
                            # Second call without clearing cache - should use cached tools
                            mock_mcp.reset_mock()
                            mock_create_react.reset_mock()
                            agent2 = await create_chat_agent(checkpointer=Mock())
                            
                            # Verify MCP tools were NOT fetched again (cache used)
                            assert mock_mcp.call_count == 0
                            second_call_tools = mock_create_react.call_args.kwargs['tools']
                            assert len(second_call_tools) == 3  # Still uses cached tools
                            
                            # NOW clear the cache (simulate MCP toggle event)
                            clear_tools_cache()
                            
                            # Third call - should fetch fresh tools
                            mock_mcp.reset_mock()
                            mock_create_react.reset_mock()
                            agent3 = await create_chat_agent(checkpointer=Mock())
                            
                            # Verify fresh tools were fetched
                            assert mock_mcp.call_count == 1
                            third_call_tools = mock_create_react.call_args.kwargs['tools']
                            assert len(third_call_tools) == 1  # Only local tools (MCP disabled)

    @pytest.mark.asyncio
    async def test_fix_resolves_original_issue(self):
        """Integration test verifying the original issue is resolved."""
        import backend.agent.chat_agent
        import backend.api.chat_endpoints
        
        # Mock the agent creation components
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
                        with patch('backend.agent.chat_agent.mcp_manager.get_client_and_tools') as mock_mcp:
                            
                            # Setup mocks
                            mock_llm.return_value = Mock()
                            mock_checkpointer.return_value = Mock()
                            mock_create_react.return_value = Mock()
                            mock_local_tools.return_value = ["local_tool"]
                            
                            # Step 1: Start with MCP tools enabled (simulate first chat)
                            mock_mcp.return_value = (Mock(), ["gmail_tool1", "gmail_tool2"])
                            backend.agent.chat_agent._cached_tools = None
                            first_agent = await create_chat_agent()
                            
                            # Step 2: Simulate MCP server being disabled
                            mock_mcp.return_value = (Mock(), [])  # No MCP tools
                            
                            # Step 3: Clear both caches (this is the fix)
                            backend.api.chat_endpoints._chat_agent = None  # Clear global agent cache
                            clear_tools_cache()  # Clear tools cache (THE FIX)
                            
                            # Step 4: Create streaming-style agent (existing chat behavior)
                            existing_chat_agent = await create_chat_agent(checkpointer=Mock())
                            
                            # Step 5: Create new chat agent  
                            new_chat_agent = await create_chat_agent()
                            
                            # Verify: Both agents should have same number of tools (no Gmail tools)
                            existing_tools = mock_create_react.call_args_list[-2].kwargs['tools']
                            new_tools = mock_create_react.call_args_list[-1].kwargs['tools']
                            
                            assert len(existing_tools) == len(new_tools) == 1  # Only local tools
                            assert "gmail_tool1" not in str(existing_tools)
                            assert "gmail_tool1" not in str(new_tools) 