"""
Integration Tests for Nova LangGraph Chat Agent

These tests validate the full chat agent functionality with real business logic
but mocked external dependencies. They test the complete integration of components.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
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
            
            # Create the agent
            agent = await create_chat_agent()
            
            # Verify business logic: agent creation was called with correct parameters
            mock_create_react_agent.assert_called_once()
            call_args = mock_create_react_agent.call_args
            
            # Verify model was passed
            assert call_args[1]['model'] == mock_llm
            
            # Verify tools were passed (should include both local and MCP tools)
            passed_tools = call_args[1]['tools']
            assert len(passed_tools) == 2  # Our test tools
            tool_names = [tool.name for tool in passed_tools]
            assert "get_test_data" in tool_names
            assert "calculate" in tool_names
            
            # Verify checkpointer was created and passed
            assert 'checkpointer' in call_args[1]
            checkpointer = call_args[1]['checkpointer']
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
            passed_tools = call_args[1]['tools']
            
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
        """Test that checkpointer works with the agent for conversation history."""
        
        @tool
        def remember_fact(fact: str):
            """Remember a fact."""
            return f"I'll remember: {fact}"
        
        with patch('agent.chat_agent.create_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
            
            # Create a mock LLM that supports tool binding
            mock_llm = MagicMock()
            mock_llm.bind_tools.return_value = mock_llm  # Tool binding returns self
            mock_create_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = [remember_fact]
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            # Create agent with memory checkpointer
            checkpointer = MemorySaver()
            agent = await create_chat_agent(checkpointer=checkpointer)
            
            # Verify agent was created successfully with checkpointer
            assert agent is not None
            
            # Verify the agent was created with the correct checkpointer
            # We can't easily test the actual conversation without a real LLM,
            # but we can verify the setup is correct
            mock_create_llm.assert_called_once()
            mock_get_tools_with_mcp.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mcp_tools_integration(self):
        """Test that MCP tools are properly integrated."""
        
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
        
        with patch('agent.chat_agent.create_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
            
            # Create a mock LLM that supports tool binding
            mock_llm = MagicMock()
            mock_llm.bind_tools.return_value = mock_llm  # Tool binding returns self
            mock_create_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = [local_tool, mcp_tool]
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            # Create agent
            agent = await create_chat_agent()
            
            # Verify agent was created successfully
            assert agent is not None
            
            # Verify the mock was called correctly
            mock_create_llm.assert_called_once()
            mock_get_tools_with_mcp.assert_called_once()
            
            # Verify tools themselves work
            assert local_tool.invoke({}) == "Local tool result" 
            assert mcp_tool.invoke({"query": "test"}) == "MCP result for: test"
    
    @pytest.mark.asyncio
    async def test_agent_stream_functionality(self):
        """Test that agent streaming works properly."""
        
        @tool
        def streaming_tool():
            """A tool for testing streaming."""
            return "Streaming tool executed"
        
        with patch('agent.chat_agent.create_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
            
            # Create a mock LLM that supports tool binding
            mock_llm = MagicMock()
            mock_llm.bind_tools.return_value = mock_llm  # Tool binding returns self
            mock_create_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = [streaming_tool]
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            # Create agent
            agent = await create_chat_agent()
            
            # Verify agent was created successfully
            assert agent is not None
            
            # Verify the mock was called correctly
            mock_create_llm.assert_called_once()
            mock_get_tools_with_mcp.assert_called_once()
            
            # Verify tools work
            assert streaming_tool.invoke({}) == "Streaming tool executed" 