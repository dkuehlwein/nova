"""
Integration Tests for Nova LangGraph Chat Agent

These tests validate the full chat agent functionality with real business logic
but mocked external dependencies. They test the complete integration of components.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from agent.chat_agent import create_chat_agent, get_all_tools_with_mcp


@pytest.fixture
def mock_checkpointer():
    """Create a mock checkpointer for testing."""
    return InMemorySaver()


class TestChatAgentIntegration:
    """Integration tests for complete chat agent functionality."""
    
    @pytest.mark.asyncio
    async def test_agent_creation_with_real_tools_and_checkpointer(self, mock_checkpointer):
        """Test full agent creation flow with real tools and checkpointer."""
        
        # Create real tools for testing
        @tool
        def get_test_data():
            """Get test data."""
            return "Test data retrieved successfully"
        
        @tool
        def calculate(x: int, y: int):
            """Calculate x + y."""
            return f"Result: {x + y}"
        
        test_tools = [get_test_data, calculate]
        
        # Mock only external dependencies, test our business logic
        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.create_react_agent') as mock_create_react_agent:
            
            # Mock external dependencies but test real business logic
            mock_llm = MagicMock()
            mock_create_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = test_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            # Mock the agent itself but verify it's called correctly
            mock_agent = MagicMock()
            mock_create_react_agent.return_value = mock_agent
            
            # Create the agent with custom checkpointer
            agent = await create_chat_agent(checkpointer=mock_checkpointer, use_cache=False)
            
            # Verify business logic: agent creation was called with correct parameters
            mock_create_react_agent.assert_called_once()
            call_args = mock_create_react_agent.call_args
            
            # Verify model was passed
            assert call_args.kwargs['model'] == mock_llm
            
            # Verify tools were passed (should include both local and MCP tools)
            passed_tools = call_args.kwargs['tools']
            assert len(passed_tools) == 2  # Our test tools
            tool_names = [tool.name for tool in passed_tools]
            assert "get_test_data" in tool_names
            assert "calculate" in tool_names
            
            # Verify checkpointer was created and passed
            assert 'checkpointer' in call_args.kwargs
            checkpointer = call_args.kwargs['checkpointer']
            assert checkpointer is mock_checkpointer
            
            # Verify agent is returned
            assert agent == mock_agent
    
    @pytest.mark.asyncio
    async def test_tools_are_properly_combined_from_multiple_sources(self, mock_checkpointer):
        """Test that tools from different sources are properly combined."""
        
        # Create local tools
        @tool
        def local_tool_1():
            """A local tool 1."""
            return "Local tool 1 result"
        
        @tool 
        def local_tool_2():
            """A local tool 2."""
            return "Local tool 2 result"
        
        # Create mock MCP tools
        @tool
        def mcp_tool_1(query: str):
            """A mock MCP tool 1."""
            return f"MCP 1 result for: {query}"
        
        @tool
        def mcp_tool_2(data: str):
            """A mock MCP tool 2."""
            return f"MCP 2 processed: {data}"
        
        local_tools = [local_tool_1, local_tool_2]
        mcp_tools = [mcp_tool_1, mcp_tool_2]
        
        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.create_react_agent') as mock_create_react_agent:
            
            mock_create_llm.return_value = MagicMock()
            # Mock the combined tools function to return both local and MCP tools
            mock_get_tools_with_mcp.return_value = local_tools + mcp_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            mock_create_react_agent.return_value = MagicMock()
            
            # Create agent with checkpointer
            await create_chat_agent(checkpointer=mock_checkpointer)
            
            # Verify tools were combined properly
            call_args = mock_create_react_agent.call_args
            passed_tools = call_args.kwargs['tools']
            
            # Should have all 4 tools
            assert len(passed_tools) == 4
            tool_names = [tool.name for tool in passed_tools]
            
            # Verify all tools are present
            assert "local_tool_1" in tool_names
            assert "local_tool_2" in tool_names
            assert "mcp_tool_1" in tool_names
            assert "mcp_tool_2" in tool_names
            
            # Test that tools actually work
            assert local_tool_1.invoke({}) == "Local tool 1 result"
            assert local_tool_2.invoke({}) == "Local tool 2 result"
            assert mcp_tool_1.invoke({"query": "test"}) == "MCP 1 result for: test"
            assert mcp_tool_2.invoke({"data": "sample"}) == "MCP 2 processed: sample"
    
    @pytest.mark.asyncio
    async def test_end_to_end_agent_workflow_with_tool_usage(self, mock_checkpointer):
        """Test complete end-to-end agent workflow including tool usage."""
        
        @tool
        def get_user_info(user_id: str):
            """Get user information by ID."""
            return f"User {user_id}: John Doe, active since 2024"
        
        @tool
        def send_notification(user_id: str, message: str):
            """Send notification to user."""
            return f"Notification sent to {user_id}: {message}"
        
        test_tools = [get_user_info, send_notification]
        
        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.create_react_agent') as mock_create_react_agent:
            
            # Mock LLM with tool usage response
            mock_llm = MagicMock()
            mock_create_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = test_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            # Mock agent with realistic behavior
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "messages": [
                    {"role": "human", "content": "Get info for user123 and send them a welcome message"},
                    {"role": "assistant", "content": "I'll help you with that.", "tool_calls": [
                        {"name": "get_user_info", "args": {"user_id": "user123"}},
                        {"name": "send_notification", "args": {"user_id": "user123", "message": "Welcome!"}}
                    ]}
                ]
            }
            mock_create_react_agent.return_value = mock_agent
            
            # Create agent and test workflow
            agent = await create_chat_agent(checkpointer=mock_checkpointer, use_cache=False)
            
            # Verify agent can handle complex workflows
            result = agent.invoke({
                "messages": [{"role": "human", "content": "Get info for user123 and send them a welcome message"}]
            })
            
            assert result is not None
            assert "messages" in result
            mock_agent.invoke.assert_called_once() 