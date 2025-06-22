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
from langchain_community.chat_models.fake import FakeMessagesListChatModel

from agent.chat_agent import create_chat_agent, get_all_tools_with_mcp


class TestChatAgentIntegration:
    """Integration tests for complete chat agent functionality."""
    
    @pytest.mark.asyncio
    async def test_agent_creation_with_real_tools_and_checkpointer(self):
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
        with patch('agent.chat_agent.create_llm') as mock_create_llm, \
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
            
            # Create the agent with use_cache=False to ensure fresh components
            agent = await create_chat_agent(use_cache=False)
            
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
            assert checkpointer is not None
            
            # Verify agent is returned
            assert agent == mock_agent
    
    @pytest.mark.asyncio
    async def test_tools_are_properly_combined_from_multiple_sources(self):
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
        
        with patch('agent.chat_agent.create_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.create_react_agent') as mock_create_react_agent:
            
            mock_create_llm.return_value = MagicMock()
            # Mock the combined tools function to return both local and MCP tools
            mock_get_tools_with_mcp.return_value = local_tools + mcp_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            mock_create_react_agent.return_value = MagicMock()
            
            # Create agent
            await create_chat_agent()
            
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
    async def test_checkpointer_integration(self):
        """Test that checkpointer is properly passed through to the agent."""
        
        @tool
        def remember_fact(fact: str):
            """Remember a fact."""
            return f"I'll remember: {fact}"
        
        with patch('agent.chat_agent.get_llm') as mock_get_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.create_react_agent') as mock_create_react_agent:
            
            # Setup mocks
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = [remember_fact]
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            mock_agent = MagicMock()
            mock_create_react_agent.return_value = mock_agent
            
            # Create agent with specific checkpointer
            custom_checkpointer = InMemorySaver()
            agent = await create_chat_agent(checkpointer=custom_checkpointer)
            
            # Verify agent was created successfully
            assert agent is not None
            assert agent == mock_agent
            
            # Verify create_react_agent was called with the correct checkpointer
            mock_create_react_agent.assert_called_once()
            call_args = mock_create_react_agent.call_args
            
            # Check that our custom checkpointer was passed through
            assert 'checkpointer' in call_args.kwargs
            assert call_args.kwargs['checkpointer'] is custom_checkpointer
            assert call_args.kwargs['checkpointer'].__class__.__name__ == 'InMemorySaver'
    
    @pytest.mark.asyncio
    async def test_mcp_tools_integration(self):
        """Test that MCP tools are properly integrated and passed to the agent."""
        
        # Create local tools
        @tool
        def local_tool():
            """A local tool."""
            return "Local tool result"
        
        # Create mock MCP tool
        @tool
        def mcp_tool(query: str):
            """A mock MCP tool."""
            return f"MCP result for: {query}"
        
        with patch('agent.chat_agent.get_llm') as mock_get_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.create_react_agent') as mock_create_react_agent:
            
            # Setup mocks
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = [local_tool, mcp_tool]
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            mock_agent = MagicMock()
            mock_create_react_agent.return_value = mock_agent
            
            # Create agent
            agent = await create_chat_agent()
            
            # Verify agent was created successfully
            assert agent is not None
            assert agent == mock_agent
            
            # Verify create_react_agent was called with the correct tools
            mock_create_react_agent.assert_called_once()
            call_args = mock_create_react_agent.call_args
            
            # Check that tools were passed through correctly
            assert 'tools' in call_args.kwargs
            passed_tools = call_args.kwargs['tools']
            assert len(passed_tools) == 2
            
            # Verify the tools themselves are functional
            tool_names = [tool.name for tool in passed_tools]
            assert 'local_tool' in tool_names
            assert 'mcp_tool' in tool_names
            
            # Verify tools work correctly
            assert local_tool.invoke({}) == "Local tool result" 
            assert mcp_tool.invoke({"query": "test"}) == "MCP result for: test"
    
    @pytest.mark.asyncio
    async def test_agent_stream_functionality(self):
        """Test that agent is created with proper components for streaming."""
        
        @tool
        def streaming_tool():
            """A tool for testing streaming."""
            return "Streaming tool executed"
        
        with patch('agent.chat_agent.get_llm') as mock_get_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.create_react_agent') as mock_create_react_agent:
            
            # Setup mocks
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = [streaming_tool]
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            mock_agent = MagicMock()
            mock_create_react_agent.return_value = mock_agent
            
            # Create agent
            agent = await create_chat_agent()
            
            # Verify agent was created successfully
            assert agent is not None
            assert agent == mock_agent
            
            # Verify create_react_agent was called with all necessary components
            mock_create_react_agent.assert_called_once()
            call_args = mock_create_react_agent.call_args
            
            # Check that all required arguments are present
            assert 'model' in call_args.kwargs
            assert 'tools' in call_args.kwargs
            assert 'prompt' in call_args.kwargs
            assert 'checkpointer' in call_args.kwargs
            
            # Check that the LLM is passed correctly
            assert call_args.kwargs['model'] == mock_llm
            
            # Check that tools are passed correctly
            passed_tools = call_args.kwargs['tools']
            assert len(passed_tools) == 1
            assert passed_tools[0] == streaming_tool
            
            # Verify tool functionality
            assert streaming_tool.invoke({}) == "Streaming tool executed" 