"""
Tests for Nova LangGraph Chat Agent

Tests that test real functionality while mocking only external dependencies
like database connections and MCP servers. Follows LangChain testing best practices.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
import logging
from typing import List, Any, Optional

from agent.chat_agent import (
    get_all_tools_with_mcp,
    clear_chat_agent_cache,
    create_chat_agent
)


class FakeChatModel(BaseChatModel):
    """A fake chat model for testing that supports bind_tools."""
    
    responses: List[str] = ["I'll help you with that task."]
    response_index: int = 0
    bound_tools: List[Any] = []
    
    def __init__(self, responses: List[str] = None, **kwargs):
        super().__init__(**kwargs)
        if responses:
            self.responses = responses
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a fake response."""
        response = self.responses[self.response_index % len(self.responses)]
        self.response_index = (self.response_index + 1) % len(self.responses)
        
        message = AIMessage(content=response)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])
    
    def bind_tools(self, tools):
        """Mock bind_tools method."""
        self.bound_tools = tools
        return self
    
    @property 
    def _llm_type(self) -> str:
        return "fake-chat-model"


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear all caches before each test."""
    clear_chat_agent_cache()


@pytest.fixture
def fake_chat_model():
    """Create FakeChatModel for predictable testing."""
    return FakeChatModel(responses=[
        "I'll help you with that task.",
        "Let me search for that information.",
        "Task completed successfully."
    ])


@pytest.fixture
def sample_tools():
    """Create real LangChain tools for testing."""
    
    @tool
    def get_tasks():
        """Get all tasks."""
        return "Found 3 tasks"
    
    @tool  
    def create_task(title: str, description: str = ""):
        """Create a new task."""
        return f"Created task: {title}"
    
    @tool
    def get_weather(location: str):
        """Get weather for a location."""
        return f"Weather in {location}: Sunny, 72°F"
    
    return [get_tasks, create_task, get_weather]


@pytest.fixture
def mock_checkpointer():
    """Create a mock checkpointer for testing."""
    return MemorySaver()


class TestCheckpointerIntegration:
    """Test checkpointer integration within chat agent creation."""
    
    @pytest.mark.asyncio
    async def test_create_chat_agent_requires_checkpointer_or_pool(self):
        """Test that chat agent creation requires either checkpointer or pg_pool."""
        with pytest.raises(ValueError, match="PostgreSQL connection pool is required"):
            await create_chat_agent(checkpointer=None, pg_pool=None)
    
    @pytest.mark.asyncio
    async def test_create_chat_agent_with_pool_creates_checkpointer(self, fake_chat_model, sample_tools):
        """Test that providing pg_pool creates PostgreSQL checkpointer internally."""
        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.chat_agent.get_nova_system_prompt') as mock_get_prompt, \
             patch('utils.service_manager.create_postgres_checkpointer') as mock_create_pg, \
             patch('agent.chat_agent.get_skill_manager') as mock_skill_manager:
            
            # Mock components
            mock_create_llm.return_value = fake_chat_model
            mock_get_tools_with_mcp.return_value = sample_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."

            # Mock skill manager
            mock_skill_mgr = MagicMock()
            mock_skill_manager.return_value = mock_skill_mgr

            # Mock checkpointer creation
            mock_checkpointer = MagicMock()
            mock_create_pg.return_value = mock_checkpointer

            # Mock pool
            mock_pool = AsyncMock()

            # Create agent with pool
            agent = await create_chat_agent(checkpointer=None, pg_pool=mock_pool)

            # Verify checkpointer was created from pool
            mock_create_pg.assert_called_once_with(mock_pool)

            # Verify agent was created (it's a compiled StateGraph)
            assert agent is not None
            assert hasattr(agent, 'invoke')
            assert hasattr(agent, 'ainvoke')
    
    @pytest.mark.asyncio
    async def test_create_chat_agent_checkpointer_creation_failure(self, fake_chat_model, sample_tools):
        """Test that checkpointer creation failures are propagated."""
        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.chat_agent.get_nova_system_prompt') as mock_get_prompt, \
             patch('utils.service_manager.create_postgres_checkpointer') as mock_create_pg:

            # Mock components
            mock_create_llm.return_value = fake_chat_model
            mock_get_tools_with_mcp.return_value = sample_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."

            # Mock checkpointer creation failure
            mock_create_pg.side_effect = Exception("PostgreSQL creation failed")

            # Mock pool
            mock_pool = AsyncMock()

            # Should propagate the exception
            with pytest.raises(Exception, match="PostgreSQL creation failed"):
                await create_chat_agent(checkpointer=None, pg_pool=mock_pool)

            # Verify checkpointer creation was attempted
            mock_create_pg.assert_called_once_with(mock_pool)


class TestToolsManagement:
    """Test tools management with real tool loading logic."""
    
    @pytest.mark.asyncio
    async def test_get_all_tools_with_mcp_caching(self, sample_tools):
        """Test tools are cached after first load."""
        with patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp:
            
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_tools = AsyncMock(return_value=[])
            
            # First call - should fetch tools
            tools1 = await get_all_tools_with_mcp()
            assert len(tools1) == 3
            assert tools1[0].name == "get_tasks"
            
            # Second call - should use cache  
            tools2 = await get_all_tools_with_mcp()
            assert tools1 is tools2  # Same object reference
            
            # Should only call get_all_tools once due to caching
            mock_get_tools.assert_called_once()
            # Should only call MCP get_tools once due to caching  
            mock_mcp.get_tools.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_all_tools_with_mcp_combines_sources(self, sample_tools):
        """Test tools from local and MCP sources are combined."""
        
        # Create mock MCP tool
        @tool
        def mcp_search(query: str):
            """Search using MCP."""
            return f"MCP search results for: {query}"
        
        with patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp:
            
            mock_get_tools.return_value = sample_tools  # 3 local tools
            mock_mcp.get_tools = AsyncMock(return_value=[mcp_search])  # 1 MCP tool
            
            tools = await get_all_tools_with_mcp()
            
            assert len(tools) == 4  # 3 local + 1 MCP
            tool_names = [tool.name for tool in tools]
            assert "get_tasks" in tool_names
            assert "create_task" in tool_names
            assert "get_weather" in tool_names
            assert "mcp_search" in tool_names
    
    def test_clear_chat_agent_cache(self, sample_tools):
        """Test all caches are properly cleared."""
        with patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp:
            
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_tools = AsyncMock(return_value=[])
            
            # Load tools and verify cache
            import agent.chat_agent
            agent.chat_agent._cached_tools = sample_tools
            agent.chat_agent._cached_llm = "fake_llm"
            assert agent.chat_agent._cached_tools is not None
            assert agent.chat_agent._cached_llm is not None
            
            # Clear cache
            clear_chat_agent_cache()
            
            # Verify all caches are cleared
            assert agent.chat_agent._cached_tools is None
            assert agent.chat_agent._cached_llm is None
    
    @pytest.mark.asyncio
    async def test_get_all_tools_mcp_error_handling(self, sample_tools):
        """Test graceful handling of MCP errors."""
        with patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp:
            
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_tools = AsyncMock(side_effect=Exception("MCP connection failed"))
            
            tools = await get_all_tools_with_mcp()
            
            # Should still return local tools despite MCP failure
            assert len(tools) == 3
            assert tools[0].name == "get_tasks"


class TestChatAgentCreation:
    """Test chat agent creation with real LangGraph integration."""

    @pytest.mark.asyncio
    async def test_create_chat_agent_basic(self, fake_chat_model, sample_tools, mock_checkpointer):
        """Test basic agent creation."""
        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.chat_agent.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.get_skill_manager') as mock_skill_manager:

            mock_create_llm.return_value = fake_chat_model
            mock_get_tools_with_mcp.return_value = sample_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            mock_skill_manager.return_value = MagicMock()

            agent = await create_chat_agent(checkpointer=mock_checkpointer)

            # Verify agent was created
            assert agent is not None
            assert hasattr(agent, 'invoke')
            assert hasattr(agent, 'ainvoke')

    @pytest.mark.asyncio
    async def test_create_chat_agent_with_custom_checkpointer(self, fake_chat_model, sample_tools):
        """Test agent creation with custom checkpointer."""
        custom_checkpointer = MemorySaver()

        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.chat_agent.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.get_skill_manager') as mock_skill_manager:

            mock_create_llm.return_value = fake_chat_model
            mock_get_tools_with_mcp.return_value = sample_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            mock_skill_manager.return_value = MagicMock()

            agent = await create_chat_agent(checkpointer=custom_checkpointer)

            assert agent is not None

    @pytest.mark.asyncio
    async def test_create_chat_agent_use_cache_false(self, fake_chat_model, sample_tools, mock_checkpointer):
        """Test agent creation with use_cache=False."""
        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.chat_agent.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.get_skill_manager') as mock_skill_manager:

            mock_create_llm.return_value = fake_chat_model
            mock_get_tools_with_mcp.return_value = sample_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            mock_skill_manager.return_value = MagicMock()

            # Pre-cache some tools
            import agent.chat_agent
            agent.chat_agent._cached_tools = ["old_tool"]

            agent = await create_chat_agent(checkpointer=mock_checkpointer, use_cache=False)

            # Verify agent created and cache was cleared
            assert agent is not None
            # Tools should have been reloaded
            mock_get_tools_with_mcp.assert_called_once()


class TestToolInvocation:
    """Test individual tool invocation following LangChain patterns."""
    
    def test_sample_tools_invocation(self, sample_tools):
        """Test that our sample tools work correctly."""
        get_tasks, create_task, get_weather = sample_tools
        
        # Test get_tasks
        result = get_tasks.invoke({})
        assert result == "Found 3 tasks"
        
        # Test create_task
        result = create_task.invoke({"title": "Test Task", "description": "Test description"})
        assert result == "Created task: Test Task"
        
        # Test get_weather  
        result = get_weather.invoke({"location": "San Francisco"})
        assert result == "Weather in San Francisco: Sunny, 72°F"
    
    @pytest.mark.asyncio
    async def test_sample_tools_async_invocation(self, sample_tools):
        """Test async tool invocation."""
        get_tasks, create_task, get_weather = sample_tools
        
        # Test async invocation
        result = await get_tasks.ainvoke({})
        assert result == "Found 3 tasks"
        
        result = await create_task.ainvoke({"title": "Async Task"})  
        assert result == "Created task: Async Task"


class TestAgentInvocation:
    """Test agent invocation with real functionality."""

    @pytest.mark.asyncio
    async def test_agent_simple_invoke(self, fake_chat_model, sample_tools, mock_checkpointer):
        """Test agent can be invoked with a simple message."""
        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools_with_mcp') as mock_get_tools_with_mcp, \
             patch('agent.chat_agent.get_nova_system_prompt') as mock_get_prompt, \
             patch('agent.chat_agent.get_skill_manager') as mock_skill_manager:

            mock_create_llm.return_value = fake_chat_model
            mock_get_tools_with_mcp.return_value = sample_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            mock_skill_manager.return_value = MagicMock()

            agent = await create_chat_agent(checkpointer=mock_checkpointer)

            # Test simple invocation with required config for checkpointer
            config = {"configurable": {"thread_id": "test-thread"}}
            result = await agent.ainvoke({"messages": [HumanMessage(content="Hello")]}, config)

            # Verify response structure
            assert "messages" in result
            assert len(result["messages"]) > 0
            # Should contain the original message plus agent response
            assert isinstance(result["messages"][-1], AIMessage) 