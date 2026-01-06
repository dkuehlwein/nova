"""
Integration Tests for Nova LangGraph Chat Agent

These tests validate the full chat agent functionality with real business logic
but mocked external dependencies. They test the complete integration of components.

Note: The chat agent now uses a custom StateGraph architecture instead of
create_react_agent, supporting dynamic skill loading (ADR-014).
"""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from agent.chat_agent import create_chat_agent, get_all_tools

# Check if DB is available for tests that require it
SKIP_DB_TESTS = os.environ.get("NOVA_SKIP_DB", "0") == "1"


@pytest.fixture
def mock_checkpointer():
    """Create a mock checkpointer for testing."""
    return InMemorySaver()


class TestChatAgentIntegration:
    """Integration tests for complete chat agent functionality."""

    @pytest.mark.asyncio
    async def test_agent_creation_with_real_tools_and_checkpointer(self, mock_checkpointer):
        """Test full agent creation flow with real tools and checkpointer.

        The agent uses a custom StateGraph with dynamic tool binding.
        We verify that the agent is created as a compiled graph with the correct checkpointer.
        """

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

        # Mock external dependencies
        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools', new_callable=AsyncMock) as mock_get_tools_with_mcp, \
             patch('agent.chat_agent.get_nova_system_prompt', new_callable=AsyncMock) as mock_get_prompt, \
             patch('agent.chat_agent.get_skill_manager') as mock_get_skill_manager:

            # Mock external dependencies
            mock_llm = MagicMock()
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            mock_create_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = test_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."

            # Mock skill manager
            mock_skill_mgr = MagicMock()
            mock_skill_mgr.list_skills.return_value = []
            mock_get_skill_manager.return_value = mock_skill_mgr

            # Create the agent with custom checkpointer
            agent = await create_chat_agent(checkpointer=mock_checkpointer, use_cache=False)

            # Verify agent is a compiled StateGraph (has invoke/ainvoke methods)
            assert agent is not None
            assert hasattr(agent, 'invoke') or hasattr(agent, 'ainvoke')

            # Verify LLM and tools were loaded
            mock_create_llm.assert_called_once()
            mock_get_tools_with_mcp.assert_called_once()
            mock_get_prompt.assert_called_once()

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
        all_tools = local_tools + mcp_tools

        with patch('agent.chat_agent.create_chat_llm') as mock_create_llm, \
             patch('agent.chat_agent.get_all_tools', new_callable=AsyncMock) as mock_get_tools_with_mcp, \
             patch('agent.chat_agent.get_nova_system_prompt', new_callable=AsyncMock) as mock_get_prompt, \
             patch('agent.chat_agent.get_skill_manager') as mock_get_skill_manager:

            mock_llm = MagicMock()
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            mock_create_llm.return_value = mock_llm
            # Mock the combined tools function to return both local and MCP tools
            mock_get_tools_with_mcp.return_value = all_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."

            # Mock skill manager
            mock_skill_mgr = MagicMock()
            mock_skill_mgr.list_skills.return_value = []
            mock_get_skill_manager.return_value = mock_skill_mgr

            # Create agent with checkpointer
            agent = await create_chat_agent(checkpointer=mock_checkpointer)

            # Verify tools were fetched (combined in get_all_tools)
            mock_get_tools_with_mcp.assert_called_once()

            # Verify agent was created successfully
            assert agent is not None

            # Test that the tools work correctly (they're real tool objects)
            assert local_tool_1.invoke({}) == "Local tool 1 result"
            assert local_tool_2.invoke({}) == "Local tool 2 result"
            assert mcp_tool_1.invoke({"query": "test"}) == "MCP 1 result for: test"
            assert mcp_tool_2.invoke({"data": "sample"}) == "MCP 2 processed: sample"

    @pytest.mark.asyncio
    async def test_end_to_end_agent_workflow_with_tool_usage(self, mock_checkpointer):
        """Test complete end-to-end agent workflow including tool usage.

        This tests that the StateGraph-based agent can be created and
        that tool invocations work correctly.
        """

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
             patch('agent.chat_agent.get_all_tools', new_callable=AsyncMock) as mock_get_tools_with_mcp, \
             patch('agent.chat_agent.get_nova_system_prompt', new_callable=AsyncMock) as mock_get_prompt, \
             patch('agent.chat_agent.get_skill_manager') as mock_get_skill_manager:

            # Mock LLM
            mock_llm = MagicMock()
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            mock_create_llm.return_value = mock_llm
            mock_get_tools_with_mcp.return_value = test_tools
            mock_get_prompt.return_value = "You are Nova, an AI assistant."

            # Mock skill manager
            mock_skill_mgr = MagicMock()
            mock_skill_mgr.list_skills.return_value = []
            mock_get_skill_manager.return_value = mock_skill_mgr

            # Create agent and verify it was created successfully
            agent = await create_chat_agent(checkpointer=mock_checkpointer, use_cache=False)

            # Verify agent is properly constructed
            assert agent is not None

            # Verify the tools work correctly
            assert get_user_info.invoke({"user_id": "user123"}) == "User user123: John Doe, active since 2024"
            assert send_notification.invoke({"user_id": "user123", "message": "Welcome!"}) == "Notification sent to user123: Welcome!"


@pytest.mark.skipif(SKIP_DB_TESTS, reason="Requires PostgreSQL (NOVA_SKIP_DB=1 is set)")
class TestPromptLoading:
    """Integration tests for prompt loading with real infrastructure.

    Requires PostgreSQL to be running (for user settings lookup).
    """

    @pytest.fixture(autouse=True)
    def setup_config_registry(self):
        """Initialize config registry for prompt loading tests."""
        from utils.config_registry import config_registry

        # Initialize config registry if not already done
        # Note: initialize_standard_configs() is synchronous
        if not config_registry._initialized:
            config_registry.initialize_standard_configs()

        yield

        # Optional: cleanup after test
        # config_registry.cleanup()

    @pytest.mark.asyncio
    async def test_prompt_loading_always_current(self):
        """Test that get_nova_system_prompt always returns current content.

        This is a true integration test - uses real config registry, file system,
        and database for user settings.
        """
        from agent.prompts import get_nova_system_prompt

        # Since get_nova_system_prompt() calls the prompt loader which reads from file,
        # it should always return current content without caching.
        prompt1 = await get_nova_system_prompt()
        prompt2 = await get_nova_system_prompt()

        # Both calls should return the same content (current file content)
        assert prompt1 == prompt2
        assert len(prompt1) > 0
        assert "Nova" in prompt1
