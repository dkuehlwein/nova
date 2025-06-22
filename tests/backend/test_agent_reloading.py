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
    async def test_chat_agent_creation_with_use_cache(self):
        """Test that create_chat_agent with use_cache=False clears cache."""
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('backend.agent.prompts.get_nova_system_prompt') as mock_get_prompt:
                        with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
                            with patch('backend.agent.chat_agent.mcp_manager.get_tools') as mock_mcp:
                                
                                # Setup mocks
                                mock_llm.return_value = Mock()
                                mock_checkpointer.return_value = Mock()
                                mock_create_react.return_value = Mock()
                                mock_get_prompt.return_value = "Test prompt"
                                mock_local_tools.return_value = ["local_tool"]
                                mock_mcp.return_value = ["mcp_tool"]
                                
                                from backend.agent.chat_agent import create_chat_agent
                                import backend.agent.chat_agent
                                
                                # Clear cache initially
                                backend.agent.chat_agent._cached_tools = None
                                
                                # First call - should cache tools
                                await create_chat_agent(use_cache=True)
                                assert mock_local_tools.call_count == 1
                                assert mock_mcp.call_count == 1
                                
                                # Verify tools are cached
                                assert backend.agent.chat_agent._cached_tools is not None
                                
                                # Reset mocks
                                mock_local_tools.reset_mock()
                                mock_mcp.reset_mock()
                                
                                # Second call without reload - should use cache (no calls to tool functions)
                                await create_chat_agent(use_cache=True)
                                assert mock_local_tools.call_count == 0
                                assert mock_mcp.call_count == 0
                                
                                # Third call with reload - should clear cache and refetch
                                await create_chat_agent(use_cache=False)
                                assert mock_local_tools.call_count == 1
                                assert mock_mcp.call_count == 1
    
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
        from backend.agent.chat_agent import get_all_tools_with_mcp, clear_chat_agent_cache
        import backend.agent.chat_agent
        
        # Clear cache initially
        clear_chat_agent_cache()
        assert backend.agent.chat_agent._cached_tools is None
        
        # Mock the underlying functions to avoid real network calls
        with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
            with patch('backend.agent.chat_agent.mcp_manager.get_tools') as mock_mcp_tools:
                
                mock_local_tools.return_value = ["local_tool"]
                mock_mcp_tools.return_value = ["mcp_tool"]
                
                # First call with use_cache=True - should cache tools
                tools1 = await get_all_tools_with_mcp(use_cache=True)
                assert backend.agent.chat_agent._cached_tools is not None
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
        from backend.agent.prompts import get_nova_system_prompt
        
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
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
                        with patch('backend.agent.chat_agent.mcp_manager.get_tools') as mock_mcp:
                            
                            # Setup mocks
                            mock_llm.return_value = Mock()
                            mock_checkpointer.return_value = Mock()
                            mock_create_react.return_value = Mock()
                            mock_local_tools.return_value = ["local_tool"]
                            mock_mcp.return_value = ["mcp_tool"]
                            
                            from backend.agent.chat_agent import create_chat_agent
                            
                            # Create agent
                            await create_chat_agent()
                            
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
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
                        with patch('backend.agent.chat_agent.mcp_manager.get_tools') as mock_mcp:
                            with patch('backend.agent.chat_agent.get_nova_system_prompt') as mock_get_prompt:
                                
                                # Setup mocks
                                mock_llm.return_value = Mock()
                                mock_checkpointer.return_value = Mock()
                                mock_create_react.return_value = Mock()
                                mock_local_tools.return_value = ["local_tool"]
                                mock_mcp.return_value = ["mcp_tool"]
                                
                                from backend.agent.chat_agent import create_chat_agent
                                import backend.agent.chat_agent
                                
                                # Clear cache initially
                                backend.agent.chat_agent._cached_tools = None
                                
                                # First agent creation with original prompt
                                mock_get_prompt.return_value = "Original system prompt with Nova capabilities"
                                await create_chat_agent(use_cache=True)
                                
                                # Verify original prompt was used
                                first_call = mock_create_react.call_args
                                assert first_call.kwargs['prompt'] == "Original system prompt with Nova capabilities"
                                
                                # Reset mock
                                mock_create_react.reset_mock()
                                
                                # Simulate prompt file change and agent reload
                                mock_get_prompt.return_value = "Updated system prompt with new Nova instructions"
                                await create_chat_agent(use_cache=False)
                                
                                # Verify new prompt was used
                                second_call = mock_create_react.call_args
                                assert second_call.kwargs['prompt'] == "Updated system prompt with new Nova instructions"
                                
                                # Verify the prompts are different
                                assert first_call.kwargs['prompt'] != second_call.kwargs['prompt']
    
    @pytest.mark.asyncio
    async def test_chat_agent_cache_clear_forces_prompt_reload(self):
        """Test that cache clear forces agent to reload with new prompt."""
        from agent.chat_agent import create_chat_agent, clear_chat_agent_cache
        
        # Mock the prompt loading to track calls
        with patch('agent.chat_agent.get_nova_system_prompt') as mock_get_prompt:
            with patch('agent.chat_agent.create_react_agent') as mock_create_react:
                with patch('agent.chat_agent.get_llm') as mock_get_llm:
                    with patch('backend.agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools:
                        with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                            
                            mock_get_prompt.return_value = "Test prompt"
                            mock_create_react.return_value = Mock()
                            mock_get_llm.return_value = Mock() 
                            mock_get_tools.return_value = []
                            mock_checkpointer.return_value = Mock()
                            
                            # Create agent first time with caching
                            await create_chat_agent(use_cache=True)
                            first_prompt_calls = mock_get_prompt.call_count
                            
                            # Create agent second time with caching - prompt is always loaded (not cached)
                            await create_chat_agent(use_cache=True)
                            second_prompt_calls = mock_get_prompt.call_count
                            
                            # Clear cache and create agent again - should reload everything
                            clear_chat_agent_cache()
                            await create_chat_agent(use_cache=True)
                            third_prompt_calls = mock_get_prompt.call_count
                            
                            # Prompt should be loaded every time (it's not cached)
                            assert first_prompt_calls > 0
                            assert second_prompt_calls > first_prompt_calls
                            assert third_prompt_calls > second_prompt_calls


class TestMCPServerToolReloading:
    """Test that MCP server enable/disable changes affect agent tools."""
    
    @pytest.mark.asyncio
    async def test_mcp_server_disable_removes_tools_from_agent(self):
        """Test that disabling an MCP server removes its tools from the agent."""
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
                        with patch('backend.agent.chat_agent.mcp_manager.get_tools') as mock_mcp:
                            
                            # Setup mocks
                            mock_llm.return_value = Mock()
                            mock_checkpointer.return_value = Mock()
                            mock_create_react.return_value = Mock()
                            mock_local_tools.return_value = ["local_tool1", "local_tool2"]
                            
                            from backend.agent.chat_agent import create_chat_agent
                            import backend.agent.chat_agent
                            
                            # Clear cache initially
                            backend.agent.chat_agent._cached_tools = None
                            
                            # First agent creation with MCP tools available
                            mock_mcp.return_value = ["mcp_tool1", "mcp_tool2", "mcp_tool3"]
                            await create_chat_agent(use_cache=True)
                            
                            # Verify agent was created with all tools
                            first_call = mock_create_react.call_args
                            first_tools = first_call.kwargs['tools']
                            assert len(first_tools) == 5  # 2 local + 3 MCP
                            assert "local_tool1" in first_tools
                            assert "local_tool2" in first_tools
                            assert "mcp_tool1" in first_tools
                            assert "mcp_tool2" in first_tools
                            assert "mcp_tool3" in first_tools
                            
                            # Reset create_react_agent mock
                            mock_create_react.reset_mock()
                            
                            # Simulate MCP server being disabled (fewer tools available)
                            mock_mcp.return_value = ["mcp_tool1"]  # Only one tool now
                            await create_chat_agent(use_cache=False)
                            
                            # Verify agent was recreated with fewer tools
                            second_call = mock_create_react.call_args
                            second_tools = second_call.kwargs['tools']
                            assert len(second_tools) == 3  # 2 local + 1 MCP
                            assert "local_tool1" in second_tools
                            assert "local_tool2" in second_tools
                            assert "mcp_tool1" in second_tools
                            # These should no longer be available
                            assert "mcp_tool2" not in second_tools
                            assert "mcp_tool3" not in second_tools
    
    @pytest.mark.asyncio
    async def test_mcp_server_enable_adds_tools_to_agent(self):
        """Test that enabling an MCP server adds its tools to the agent."""
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
                        with patch('backend.agent.chat_agent.mcp_manager.get_tools') as mock_mcp:
                            
                            # Setup mocks
                            mock_llm.return_value = Mock()
                            mock_checkpointer.return_value = Mock()
                            mock_create_react.return_value = Mock()
                            mock_local_tools.return_value = ["local_tool1", "local_tool2"]
                            
                            from backend.agent.chat_agent import create_chat_agent
                            import backend.agent.chat_agent
                            
                            # Clear cache initially
                            backend.agent.chat_agent._cached_tools = None
                            
                            # First agent creation with no MCP tools (all servers disabled)
                            mock_mcp.return_value = []
                            await create_chat_agent(use_cache=True)
                            
                            # Verify agent was created with only local tools
                            first_call = mock_create_react.call_args
                            first_tools = first_call.kwargs['tools']
                            assert len(first_tools) == 2  # 2 local + 0 MCP
                            
                            # Reset mock
                            mock_create_react.reset_mock()
                            
                            # Simulate MCP server being enabled (new tools available)
                            mock_mcp.return_value = ["mcp_tool1", "mcp_tool2"]
                            await create_chat_agent(use_cache=False)
                            
                            # Verify agent was created with additional tools
                            second_call = mock_create_react.call_args
                            second_tools = second_call.kwargs['tools']
                            assert len(second_tools) == 4  # 2 local + 2 MCP
                            
                            # Verify tool count increased
                            assert len(second_tools) > len(first_tools)
    
    @pytest.mark.asyncio
    async def test_mcp_tools_respect_enabled_disabled_status(self):
        """Test that MCP tools are only loaded from enabled servers."""
        # This test verifies the integration between config.py MCP_SERVERS property
        # and the MCP client manager's server discovery
        
        with patch('utils.config_loader.load_mcp_yaml') as mock_load_yaml:
            # Mock YAML configuration with mixed enabled/disabled servers
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
            
            # Import config to get filtered server list
            from config import settings
            
            # Verify that only enabled servers are included  
            mcp_servers = settings.MCP_SERVERS
            # Note: Real environment has 2 enabled servers (feature-request and google-workspace)
            assert len(mcp_servers) >= 1  # At least one enabled server
            server_names = [s["name"] for s in mcp_servers]
            
            # Verify disabled server is not included
            assert "disabled_server" not in server_names
    
    @pytest.mark.asyncio
    async def test_mcp_toggle_event_clears_chat_agent_cache(self):
        """Test that MCP toggle events clear the chat agent cache for real-time tool updates."""
        from agent.chat_agent import clear_chat_agent_cache
        from start_website import create_website_event_handler
        from models.events import create_mcp_toggled_event
        
        # Mock the unified cache clearing function used by the event handler
        with patch('api.chat_endpoints.clear_chat_agent_cache') as mock_clear_cache:
            
            # Create the event handler and simulate MCP toggle event
            event_handler = await create_website_event_handler()
            mcp_event = create_mcp_toggled_event("gmail", False, "test")
            
            # Process the event - this should call the unified clearing function
            await event_handler(mcp_event)
            
            # Verify the unified cache clearing function was called
            mock_clear_cache.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_system_prompt_loading_in_agent_creation(self):
        """Test that system prompt is properly loaded when creating agents."""
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('backend.agent.chat_agent.get_all_tools_with_mcp') as mock_tools:
                        
                        # Setup mocks
                        mock_llm.return_value = Mock()
                        mock_checkpointer.return_value = Mock()
                        mock_create_react.return_value = Mock()
                        mock_tools.return_value = ["test_tool"]
                        
                        from backend.agent.chat_agent import create_chat_agent
                        
                        # Create agent
                        await create_chat_agent()
                        
                        # Verify create_react_agent was called with a prompt
                        assert mock_create_react.called
                        call_kwargs = mock_create_react.call_args.kwargs
                        assert 'prompt' in call_kwargs
                        
                        # Verify prompt contains Nova content
                        prompt = call_kwargs['prompt']
                        assert isinstance(prompt, str)
                        assert len(prompt) > 0
                        assert "Nova" in prompt  # Should contain the Nova system prompt
                        
                        # Verify other parameters are correct
                        assert 'model' in call_kwargs
                        assert 'tools' in call_kwargs
                        assert 'checkpointer' in call_kwargs

    @pytest.mark.asyncio
    async def test_tools_cache_cleared_on_reload_tools_true(self):
        """Test that tools cache is properly cleared when reload_tools=True."""
        with patch('backend.agent.chat_agent.create_llm') as mock_llm:
            with patch('backend.agent.chat_agent.create_checkpointer') as mock_checkpointer:
                with patch('backend.agent.chat_agent.create_react_agent') as mock_create_react:
                    with patch('backend.agent.chat_agent.get_all_tools') as mock_local_tools:
                        with patch('backend.agent.chat_agent.mcp_manager.get_tools') as mock_mcp:
                            
                            # Setup mocks
                            mock_llm.return_value = Mock()
                            mock_checkpointer.return_value = Mock()
                            mock_create_react.return_value = Mock()
                            mock_local_tools.return_value = ["local_tool"]
                            mock_mcp.return_value = ["mcp_tool"]
                            
                            from backend.agent.chat_agent import create_chat_agent
                            import backend.agent.chat_agent
                            
                            # Clear cache initially
                            backend.agent.chat_agent._cached_tools = None
                            
                            # First call - should fetch and cache tools
                            await create_chat_agent(use_cache=True)
                            assert mock_local_tools.call_count == 1
                            assert mock_mcp.call_count == 1
                            assert backend.agent.chat_agent._cached_tools is not None
                            cached_tools = backend.agent.chat_agent._cached_tools
                            
                            # Reset mocks
                            mock_local_tools.reset_mock()
                            mock_mcp.reset_mock()
                            
                            # Second call with use_cache=False - should clear cache and refetch
                            await create_chat_agent(use_cache=False)
                            
                            # Verify cache was cleared (new tools fetched)
                            assert mock_local_tools.call_count == 1
                            assert mock_mcp.call_count == 1
                            
                            # Verify tools were refetched (cache should be repopulated)
                            assert backend.agent.chat_agent._cached_tools is not None
    
 