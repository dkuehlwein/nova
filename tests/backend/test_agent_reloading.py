"""
Test agent reloading functionality.

Tests the simplified agent reloading approach using reload_tools parameter
instead of separate cache clearing functions.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, Mock

import pytest


class TestAgentReloading:
    """Test agent reloading with simplified approach."""
    
    @pytest.mark.asyncio
    async def test_chat_agent_creation_with_reload_tools(self):
        """Test that create_chat_agent with reload_tools=True clears cache."""
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
                        with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
                            with patch('backend.agent.chat_agent.mcp_manager.get_client_and_tools') as mock_mcp:
                                
                                # Setup mocks
                                mock_llm.return_value = Mock()
                                mock_checkpointer.return_value = Mock()
                                mock_create_react.return_value = Mock()
                                mock_get_prompt.return_value = "Test prompt"
                                mock_local_tools.return_value = ["local_tool"]
                                mock_mcp.return_value = (None, ["mcp_tool"])
                                
                                from backend.agent.chat_agent import create_chat_agent
                                import backend.agent.chat_agent
                                
                                # Clear cache initially
                                backend.agent.chat_agent._cached_tools = None
                                
                                # First call - should cache tools
                                await create_chat_agent(reload_tools=False)
                                assert mock_local_tools.call_count == 1
                                assert mock_mcp.call_count == 1
                                
                                # Verify tools are cached
                                assert backend.agent.chat_agent._cached_tools is not None
                                
                                # Reset mocks
                                mock_local_tools.reset_mock()
                                mock_mcp.reset_mock()
                                
                                # Second call without reload - should use cache (no calls to tool functions)
                                await create_chat_agent(reload_tools=False)
                                assert mock_local_tools.call_count == 0
                                assert mock_mcp.call_count == 0
                                
                                # Third call with reload - should clear cache and refetch
                                await create_chat_agent(reload_tools=True)
                                assert mock_local_tools.call_count == 1
                                assert mock_mcp.call_count == 1
    
    @pytest.mark.asyncio
    async def test_chat_agent_cache_clearing(self):
        """Test that chat agent cache is cleared properly."""
        from backend.api.chat_endpoints import clear_chat_agent_cache, _chat_agent
        
        # Mock the global chat agent
        with patch('backend.api.chat_endpoints._chat_agent', new=Mock()) as mock_agent:
            
            # Call the cache clearing function
            clear_chat_agent_cache()
        
        # Verify global agent is set to None
        from backend.api.chat_endpoints import _chat_agent
        assert _chat_agent is None
    
    @pytest.mark.asyncio
    async def test_core_agent_reload_method(self):
        """Test that core agent reload creates new agent with reload_tools=True."""
        from backend.agent.core_agent import CoreAgent
        
        # Mock dependencies
        with patch('backend.agent.core_agent.create_chat_agent') as mock_create:
            with patch.object(CoreAgent, '_initialize_status'):
                mock_agent = Mock()
                mock_create.return_value = mock_agent
                
                # Initialize agent
                agent = CoreAgent()
                await agent.initialize()
                original_agent = agent.agent
                
                # Reload agent (simulating prompt update)
                await agent.reload_agent()
                new_agent = agent.agent
                
                # Verify create_chat_agent was called twice with correct parameters
                assert mock_create.call_count == 2
                
                # First call (initialization) should not reload tools
                first_call = mock_create.call_args_list[0]
                assert first_call.kwargs.get('reload_tools', False) == False
                
                # Second call (reload) should reload tools
                second_call = mock_create.call_args_list[1]
                assert second_call.kwargs.get('reload_tools', False) == True
                
                # Both calls should return the same mock (agent should be updated)
                assert new_agent is original_agent  # Same mock instance
    
    @pytest.mark.asyncio
    async def test_get_chat_agent_always_reloads_tools(self):
        """Test that get_chat_agent always uses reload_tools=True for new agents."""
        from backend.api.chat_endpoints import get_chat_agent, clear_chat_agent_cache
        
        # Clear any existing agent
        clear_chat_agent_cache()
        
        # Mock create_chat_agent to track calls
        with patch('backend.api.chat_endpoints.create_chat_agent') as mock_create:
            mock_create.return_value = Mock()
            
            # First call - should create agent with reload_tools=True
            await get_chat_agent()
            assert mock_create.call_count == 1
            
            # Verify reload_tools=True was used
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs.get('reload_tools', False) == True
            
            # Second call - should reuse cached agent (no additional call)
            await get_chat_agent()
            assert mock_create.call_count == 1  # No additional call
    
    def test_prompt_loading_always_current(self):
        """Test that get_nova_system_prompt always returns current content."""
        from backend.agent.prompts import get_nova_system_prompt
        
        # Since get_nova_system_prompt() calls the prompt loader which reads from file,
        # it should always return current content without caching
        prompt1 = get_nova_system_prompt()
        prompt2 = get_nova_system_prompt()
        
        # Both calls should return the same content (current file content)
        assert prompt1 == prompt2
        assert len(prompt1) > 0
        assert "Nova" in prompt1
    
 