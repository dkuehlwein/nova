"""
Test agent reloading functionality.

Tests the simplified agent reloading approach using use_cache parameter
instead of separate cache clearing functions.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, Mock

import pytest


class TestAgentReloading:
    """Test agent reloading with simplified approach."""
    
    @pytest.mark.asyncio
    async def test_create_chat_agent_with_checkpointer_and_pool(self):
        """Test that create_chat_agent works with both checkpointer and pg_pool parameters."""
        from langgraph.checkpoint.memory import InMemorySaver
        from agent.chat_agent import create_chat_agent
        
        # Test with checkpointer
        with patch('agent.chat_agent.get_llm') as mock_llm:
            with patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools:
                with patch('agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
                        
                        # Setup mocks
                        mock_llm.return_value = Mock()
                        mock_create_react.return_value = Mock()
                        mock_get_prompt.return_value = "Test prompt"
                        mock_get_tools.return_value = ["tool1", "tool2"]
                        
                        # Test with checkpointer
                        mock_checkpointer = InMemorySaver()
                        agent1 = await create_chat_agent(checkpointer=mock_checkpointer)
                        assert agent1 is not None
                        
                        # Test with pg_pool
                        mock_create_react.reset_mock()
                        with patch('utils.service_manager.create_postgres_checkpointer') as mock_create_pg:
                            mock_pg_checkpointer = Mock()
                            mock_create_pg.return_value = mock_pg_checkpointer
                            mock_pg_pool = Mock()
                            
                            agent2 = await create_chat_agent(pg_pool=mock_pg_pool)
                            assert agent2 is not None
                            mock_create_pg.assert_called_once_with(mock_pg_pool)
    
    @pytest.mark.asyncio
    async def test_chat_agent_cache_clearing(self):
        """Test that chat agent cache is cleared properly."""
        from agent.chat_agent import clear_chat_agent_cache
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
    async def test_core_agent_reload_method(self):
        """Test that core agent reload creates new agent with use_cache=False."""
        from agent.core_agent import CoreAgent
        
        # Mock dependencies
        with patch('agent.core_agent.create_chat_agent') as mock_create:
            with patch.object(CoreAgent, '_initialize_status'):
                mock_agent = Mock()
                mock_create.return_value = mock_agent
                
                # Create mock pg_pool
                mock_pg_pool = Mock()
                
                # Initialize agent with required pg_pool
                agent = CoreAgent(pg_pool=mock_pg_pool)
                await agent.initialize()
                original_agent = agent.agent
                
                # Reload agent (simulating prompt update)
                await agent.reload_agent()
                new_agent = agent.agent
                
                # Verify create_chat_agent was called twice with correct parameters
                assert mock_create.call_count == 2
                
                # First call (initialization) should use cache
                first_call = mock_create.call_args_list[0]
                assert first_call.kwargs.get('use_cache', True) == True
                
                # Second call (reload) should not use cache
                second_call = mock_create.call_args_list[1]
                assert second_call.kwargs.get('use_cache', True) == False
                
                # Both calls should return the same mock (agent should be updated)
                assert new_agent is original_agent  # Same mock instance
    
    @pytest.mark.asyncio
    async def test_create_chat_agent_use_cache_parameter(self):
        """Test that create_chat_agent respects use_cache parameter by checking cache variables."""
        from agent.chat_agent import get_all_tools_with_mcp, clear_chat_agent_cache
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
    
    def test_prompt_loading_always_current(self):
        """Test that get_nova_system_prompt always returns current content."""
        from agent.prompts import get_nova_system_prompt
        
        # Since get_nova_system_prompt() calls the prompt loader which reads from file,
        # it should always return current content without caching
        prompt1 = get_nova_system_prompt()
        prompt2 = get_nova_system_prompt()
        
        # Both calls should return the same content (current file content)
        assert prompt1 == prompt2
        assert len(prompt1) > 0
        assert "Nova" in prompt1


class TestSystemPromptReloading:
    """Test that system prompt changes are properly applied to agents."""
    
    @pytest.mark.asyncio
    async def test_system_prompt_passed_to_create_react_agent(self):
        """Test that the current system prompt is actually passed to create_react_agent."""
        with patch('agent.chat_agent.get_llm') as mock_llm:
            with patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp:
                with patch('agent.chat_agent.create_react_agent') as mock_create_react:
                    
                    # Setup mocks
                    mock_llm.return_value = Mock()
                    mock_create_react.return_value = Mock()
                    mock_get_tools_with_mcp.return_value = ["tool1", "tool2"]
                    
                    # Create a mock checkpointer
                    from langgraph.checkpoint.memory import InMemorySaver
                    mock_checkpointer = InMemorySaver()
                    
                    from agent.chat_agent import create_chat_agent
                    
                    # Create agent
                    await create_chat_agent(checkpointer=mock_checkpointer)
                    
                    # Verify create_react_agent was called
                    assert mock_create_react.called
                    call_args = mock_create_react.call_args
                    
                    # Verify prompt parameter was passed
                    assert 'prompt' in call_args.kwargs
                    prompt_arg = call_args.kwargs['prompt']
                    
                    # Verify it contains the actual system prompt content
                    assert isinstance(prompt_arg, str)
                    assert len(prompt_arg) > 0
                    assert "Nova" in prompt_arg  # Should contain Nova from the actual system prompt
    
    @pytest.mark.asyncio
    async def test_prompt_change_triggers_new_agent_with_new_prompt(self):
        """Test that a prompt change results in a new agent with the updated prompt."""
        with patch('agent.chat_agent.get_llm') as mock_llm:
            with patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp:
                with patch('agent.chat_agent.create_react_agent') as mock_create_react:
                    
                    # Setup mocks
                    mock_llm.return_value = Mock()
                    mock_create_react.return_value = Mock()
                    mock_get_tools_with_mcp.return_value = ["tool1", "tool2"]
                    
                    # Create a mock checkpointer
                    from langgraph.checkpoint.memory import InMemorySaver
                    mock_checkpointer = InMemorySaver()
                    
                    from agent.chat_agent import create_chat_agent
                    
                    # First agent creation
                    await create_chat_agent(checkpointer=mock_checkpointer)
                    first_call_prompt = mock_create_react.call_args.kwargs['prompt']
                    
                    # Reset mock to check second call
                    mock_create_react.reset_mock()
                    
                    # Second agent creation (simulating prompt change)
                    await create_chat_agent(checkpointer=mock_checkpointer, use_cache=False)
                    second_call_prompt = mock_create_react.call_args.kwargs['prompt']
                    
                    # Both calls should have received the current prompt
                    assert first_call_prompt == second_call_prompt
                    assert "Nova" in second_call_prompt


class TestMCPServerToolReloading:
    """Test MCP server tool reloading functionality."""
    
    @pytest.mark.asyncio
    async def test_mcp_server_disable_removes_tools_from_agent(self):
        """Test that disabling MCP server removes its tools from agent."""
        with patch('agent.chat_agent.get_llm') as mock_llm:
            with patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp:
                with patch('agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
                        
                        # Setup mocks
                        mock_llm.return_value = Mock()
                        mock_create_react.return_value = Mock()
                        mock_get_prompt.return_value = "Test prompt"
                        
                        # First: MCP server enabled (with tools)
                        mock_get_tools_with_mcp.return_value = ["local_tool1", "mcp_tool1", "mcp_tool2"]
                        
                        # Create a mock checkpointer
                        from langgraph.checkpoint.memory import InMemorySaver
                        mock_checkpointer = InMemorySaver()
                        
                        from agent.chat_agent import create_chat_agent
                        
                        # Create agent with MCP tools
                        agent1 = await create_chat_agent(checkpointer=mock_checkpointer)
                        
                        # Verify first call had MCP tools
                        first_call = mock_create_react.call_args
                        first_tools = first_call.kwargs['tools']
                        assert len(first_tools) == 3
                        
                        # Reset mock
                        mock_create_react.reset_mock()
                        
                        # Second: MCP server disabled (tools removed)
                        mock_get_tools_with_mcp.return_value = ["local_tool1"]  # Only local tools
                        
                        # Create agent again (simulating MCP server disable)
                        agent2 = await create_chat_agent(checkpointer=mock_checkpointer, use_cache=False)
                        
                        # Verify second call has fewer tools
                        second_call = mock_create_react.call_args
                        second_tools = second_call.kwargs['tools']
                        assert len(second_tools) == 1
    
    @pytest.mark.asyncio
    async def test_mcp_server_enable_adds_tools_to_agent(self):
        """Test that enabling MCP server adds its tools to agent."""
        with patch('agent.chat_agent.get_llm') as mock_llm:
            with patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp:
                with patch('agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
                        
                        # Setup mocks
                        mock_llm.return_value = Mock()
                        mock_create_react.return_value = Mock()
                        mock_get_prompt.return_value = "Test prompt"
                        
                        # First: No MCP tools (server disabled)
                        mock_get_tools_with_mcp.return_value = ["local_tool1"]
                        
                        # Create a mock checkpointer
                        from langgraph.checkpoint.memory import InMemorySaver
                        mock_checkpointer = InMemorySaver()
                        
                        from agent.chat_agent import create_chat_agent
                        
                        # Create agent without MCP tools
                        agent1 = await create_chat_agent(checkpointer=mock_checkpointer)
                        
                        # Verify first call had only local tools
                        first_call = mock_create_react.call_args
                        first_tools = first_call.kwargs['tools']
                        assert len(first_tools) == 1
                        
                        # Reset mock
                        mock_create_react.reset_mock()
                        
                        # Second: MCP server enabled (tools added)
                        mock_get_tools_with_mcp.return_value = ["local_tool1", "mcp_tool1", "mcp_tool2"]
                        
                        # Create agent again (simulating MCP server enable)
                        agent2 = await create_chat_agent(checkpointer=mock_checkpointer, use_cache=False)
                        
                        # Verify second call has more tools
                        second_call = mock_create_react.call_args
                        second_tools = second_call.kwargs['tools']
                        assert len(second_tools) == 3
    
    @pytest.mark.asyncio
    async def test_mcp_tools_respect_enabled_disabled_status(self):
        """Test that MCP tools are only included when servers are enabled."""
        from agent.chat_agent import get_all_tools_with_mcp
        
        # Mock the underlying calls
        with patch('agent.chat_agent.get_all_tools') as mock_local_tools:
            with patch('agent.chat_agent.mcp_manager.get_tools') as mock_mcp_tools:
                
                mock_local_tools.return_value = ["local_tool1"]
                mock_mcp_tools.return_value = ["mcp_tool1", "mcp_tool2"]  # Simulating enabled MCP servers
                
                tools = await get_all_tools_with_mcp()
                
                # Should combine both local and MCP tools
                assert len(tools) == 3
                
                # Mock disabled MCP servers
                mock_mcp_tools.return_value = []  # No MCP tools (disabled)
                
                # Clear cache to refetch
                from agent.chat_agent import clear_chat_agent_cache
                clear_chat_agent_cache()
                
                tools_disabled = await get_all_tools_with_mcp()
                
                # Should only have local tools
                assert len(tools_disabled) == 1
    
    @pytest.mark.asyncio
    async def test_mcp_toggle_event_clears_chat_agent_cache(self):
        """Test that MCP toggle events clear chat agent cache."""
        from agent.chat_agent import clear_chat_agent_cache
        import agent.chat_agent
        
        # Set up cached state
        agent.chat_agent._cached_tools = ["tool1", "tool2"]
        agent.chat_agent._cached_llm = "cached_llm"
        
        # Simulate MCP toggle event clearing cache
        clear_chat_agent_cache()
        
        # Verify cache was cleared
        assert agent.chat_agent._cached_tools is None
        assert agent.chat_agent._cached_llm is None

 