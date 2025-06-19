"""
Tests for Nova LangGraph Chat Agent

Unit tests that test real functionality while mocking only external dependencies
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
    create_checkpointer, 
    get_all_tools_with_mcp,
    clear_tools_cache,
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
    """Clear tools cache before each test."""
    clear_tools_cache()


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


class TestCheckpointerCreation:
    """Test checkpointer creation with real logic."""
    
    @pytest.mark.asyncio
    async def test_create_checkpointer_force_memory(self):
        """Test forced memory checkpointer."""
        with patch('agent.chat_agent.settings') as mock_settings:
            mock_settings.FORCE_MEMORY_CHECKPOINTER = True
            
            checkpointer = await create_checkpointer()
            
            assert isinstance(checkpointer, MemorySaver)
    
    @pytest.mark.asyncio
    async def test_create_checkpointer_no_database_url(self):
        """Test memory checkpointer when no database configured."""
        with patch('agent.chat_agent.settings') as mock_settings:
            mock_settings.FORCE_MEMORY_CHECKPOINTER = False
            mock_settings.DATABASE_URL = None
            
            checkpointer = await create_checkpointer()
            
            assert isinstance(checkpointer, MemorySaver)
    
    @pytest.mark.asyncio 
    async def test_create_checkpointer_postgres_success(self):
        """Test PostgreSQL checkpointer creation."""
        with patch('agent.chat_agent.settings') as mock_settings, \
             patch('langgraph.checkpoint.postgres.aio.AsyncPostgresSaver') as mock_pg_saver, \
             patch('psycopg_pool.AsyncConnectionPool') as mock_pool_class:
            
            mock_settings.FORCE_MEMORY_CHECKPOINTER = False
            mock_settings.DATABASE_URL = "postgresql://test:test@localhost/test"
            
            # Mock successful pool and checkpointer creation
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool
            
            mock_checkpointer = AsyncMock()
            mock_pg_saver.return_value = mock_checkpointer
            
            checkpointer = await create_checkpointer()
            
            # Verify pool was created and opened
            mock_pool_class.assert_called_once_with(mock_settings.DATABASE_URL, open=False)
            mock_pool.open.assert_called_once()
            mock_pg_saver.assert_called_once_with(mock_pool)
            mock_checkpointer.setup.assert_called_once()
            
            assert checkpointer == mock_checkpointer
    
    @pytest.mark.asyncio
    async def test_create_checkpointer_postgres_failure(self):
        """Test fallback to memory when PostgreSQL fails."""
        with patch('agent.chat_agent.settings') as mock_settings, \
             patch('langgraph.checkpoint.postgres.aio.AsyncPostgresSaver') as mock_pg_saver:
            
            mock_settings.FORCE_MEMORY_CHECKPOINTER = False
            mock_settings.DATABASE_URL = "postgresql://test:test@localhost/test"
            
            # Mock PostgreSQL import failure
            mock_pg_saver.side_effect = ImportError("PostgreSQL not available")
            
            checkpointer = await create_checkpointer()
            
            # Should fallback to MemorySaver
            assert isinstance(checkpointer, MemorySaver)


class TestToolsManagement:
    """Test tools management with real tool loading logic."""
    
    @pytest.mark.asyncio
    async def test_get_all_tools_with_mcp_caching(self, sample_tools):
        """Test tools are cached after first load."""
        with patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp:
            
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_client_and_tools = AsyncMock(return_value=(None, []))
            
            # First call - should fetch tools
            tools1 = await get_all_tools_with_mcp()
            assert len(tools1) == 3
            assert tools1[0].name == "get_tasks"
            
            # Second call - should use cache  
            tools2 = await get_all_tools_with_mcp()
            assert tools1 is tools2  # Same object reference
            
            # Should only call get_all_tools once due to caching
            mock_get_tools.assert_called_once()
            mock_mcp.get_client_and_tools.assert_called_once()
    
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
            mock_mcp.get_client_and_tools = AsyncMock(return_value=(None, [mcp_search]))  # 1 MCP tool
            
            tools = await get_all_tools_with_mcp()
            
            assert len(tools) == 4  # 3 local + 1 MCP
            tool_names = [tool.name for tool in tools]
            assert "get_tasks" in tool_names
            assert "create_task" in tool_names
            assert "get_weather" in tool_names
            assert "mcp_search" in tool_names
    
    def test_clear_tools_cache(self, sample_tools):
        """Test tools cache is properly cleared."""
        with patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp:
            
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_client_and_tools = AsyncMock(return_value=(None, []))
            
            # Load tools and verify cache
            import agent.chat_agent
            agent.chat_agent._cached_tools = sample_tools
            assert agent.chat_agent._cached_tools is not None
            
            # Clear cache
            clear_tools_cache()
            
            # Verify cache is cleared
            assert agent.chat_agent._cached_tools is None
    
    @pytest.mark.asyncio
    async def test_get_all_tools_mcp_error_handling(self, sample_tools):
        """Test graceful handling of MCP errors."""
        with patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp:
            
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_client_and_tools = AsyncMock(side_effect=Exception("MCP connection failed"))
            
            tools = await get_all_tools_with_mcp()
            
            # Should still return local tools despite MCP failure
            assert len(tools) == 3
            assert tools[0].name == "get_tasks"


class TestChatAgentCreation:
    """Test chat agent creation with real LangGraph integration."""
    
    @pytest.mark.asyncio
    async def test_create_chat_agent_basic(self, fake_chat_model, sample_tools):
        """Test basic agent creation."""
        with patch('agent.chat_agent.create_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
            
            mock_create_llm.return_value = fake_chat_model
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_client_and_tools = AsyncMock(return_value=(None, []))
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            agent = await create_chat_agent()
            
            # Verify agent was created
            assert agent is not None
            assert hasattr(agent, 'invoke')
            assert hasattr(agent, 'stream')
            
            # Verify tools were bound to model
            assert len(fake_chat_model.bound_tools) == 3
    
    @pytest.mark.asyncio 
    async def test_create_chat_agent_with_custom_checkpointer(self, fake_chat_model, sample_tools):
        """Test agent creation with custom checkpointer."""
        custom_checkpointer = MemorySaver()
        
        with patch('agent.chat_agent.create_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
            
            mock_create_llm.return_value = fake_chat_model
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_client_and_tools = AsyncMock(return_value=(None, []))
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            agent = await create_chat_agent(checkpointer=custom_checkpointer)
            
            assert agent is not None
    
    @pytest.mark.asyncio
    async def test_create_chat_agent_reload_tools(self, fake_chat_model, sample_tools):
        """Test agent creation with tools reload."""
        with patch('agent.chat_agent.create_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
            
            mock_create_llm.return_value = fake_chat_model
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_client_and_tools = AsyncMock(return_value=(None, []))
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            # Pre-cache some tools
            import agent.chat_agent
            agent.chat_agent._cached_tools = ["old_tool"]
            
            agent = await create_chat_agent(reload_tools=True)
            
            # Verify agent created and cache was cleared
            assert agent is not None
            # Tools should have been reloaded
            mock_get_tools.assert_called_once()


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
    async def test_agent_simple_invoke(self, fake_chat_model, sample_tools):
        """Test agent can be invoked with a simple message."""
        with patch('agent.chat_agent.create_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools') as mock_get_tools, \
             patch('agent.chat_agent.mcp_manager') as mock_mcp, \
             patch('agent.prompts.get_nova_system_prompt') as mock_get_prompt:
            
            mock_create_llm.return_value = fake_chat_model
            mock_get_tools.return_value = sample_tools
            mock_mcp.get_client_and_tools = AsyncMock(return_value=(None, []))
            mock_get_prompt.return_value = "You are Nova, an AI assistant."
            
            agent = await create_chat_agent()
            
            # Test simple invocation with required config for checkpointer
            config = {"configurable": {"thread_id": "test-thread"}}
            result = await agent.ainvoke({"messages": [HumanMessage(content="Hello")]}, config)
            
            # Verify response structure
            assert "messages" in result
            assert len(result["messages"]) > 0
            # Should contain the original message plus agent response
            assert isinstance(result["messages"][-1], AIMessage) 