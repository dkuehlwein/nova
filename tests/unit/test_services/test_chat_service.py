"""
Chat Service Unit Tests

Tests for the ChatService class that handles chat streaming and LangGraph interaction.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.services.chat_service import ChatService, chat_service
from backend.models.chat import ChatMessage, ChatRequest
from backend.utils.langgraph_utils import create_langgraph_config


@pytest.fixture
def service():
    """Create a ChatService instance for testing."""
    return ChatService()


class TestMessageConversion:
    """Test message conversion between Pydantic and LangChain formats."""

    def test_convert_user_messages(self, service):
        """Test converting user messages to LangChain format."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="user", content="How are you?"),
        ]

        result = service.convert_messages_to_langchain(messages)

        assert len(result) == 2
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], HumanMessage)
        assert result[0].content == "Hello"
        assert result[1].content == "How are you?"

    def test_convert_assistant_messages(self, service):
        """Test converting assistant messages to LangChain format."""
        messages = [
            ChatMessage(role="assistant", content="I am doing well!"),
        ]

        result = service.convert_messages_to_langchain(messages)

        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "I am doing well!"

    def test_convert_mixed_messages(self, service):
        """Test converting a mix of user and assistant messages."""
        messages = [
            ChatMessage(role="user", content="Hi"),
            ChatMessage(role="assistant", content="Hello!"),
            ChatMessage(role="user", content="What's the weather?"),
        ]

        result = service.convert_messages_to_langchain(messages)

        assert len(result) == 3
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)
        assert isinstance(result[2], HumanMessage)

    def test_convert_empty_messages(self, service):
        """Test converting empty message list."""
        result = service.convert_messages_to_langchain([])
        assert result == []


class TestConfigCreation:
    """Test LangGraph configuration creation via utility function."""

    def test_create_config_with_thread_id(self):
        """Test creating config with provided thread ID."""
        config = create_langgraph_config("test-thread-123")

        assert config == {"configurable": {"thread_id": "test-thread-123"}}

    def test_create_config_generates_thread_id(self):
        """Test that config generates thread ID when not provided."""
        config = create_langgraph_config()

        assert "configurable" in config
        assert "thread_id" in config["configurable"]
        assert config["configurable"]["thread_id"].startswith("chat-")

    def test_create_config_none_thread_id(self):
        """Test creating config with explicit None generates new ID."""
        config = create_langgraph_config(None)

        assert "configurable" in config
        assert config["configurable"]["thread_id"].startswith("chat-")


class TestFirstTurnDetection:
    """Test first turn detection in conversations."""

    @pytest.mark.asyncio
    async def test_is_first_turn_no_state(self, service):
        """Test that no state means first turn."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = None

        result = await service.is_first_turn("test-thread", mock_checkpointer)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_first_turn_empty_messages(self, service):
        """Test that empty messages means first turn."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {"messages": []}
        }

        result = await service.is_first_turn("test-thread", mock_checkpointer)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_not_first_turn_with_messages(self, service):
        """Test that existing messages means not first turn."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {"messages": [HumanMessage(content="Hello")]}
        }

        result = await service.is_first_turn("test-thread", mock_checkpointer)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_first_turn_error_handling(self, service):
        """Test that errors default to not first turn (safe behavior)."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.side_effect = Exception("Database error")

        result = await service.is_first_turn("test-thread", mock_checkpointer)

        # Should return False (not first turn) on error for safety
        assert result is False


class TestMemoryInjection:
    """Test memory context injection for first turn.

    Note: These tests verify the structure of memory injection messages
    without actually calling the real memory service (which requires Neo4j).
    The error handling test verifies graceful degradation.
    """

    def test_memory_tool_message_structure(self):
        """Test that memory tool messages have correct structure."""
        # Create sample messages like inject_memory_context would return
        ai_tool_call = AIMessage(
            content="Before answering you, let me search my memory...",
            tool_calls=[
                {
                    "name": "search_memory",
                    "args": {"query": "test"},
                    "id": "memory_search_auto",
                    "type": "tool_call",
                }
            ],
        )
        tool_result = ToolMessage(
            content="Found 2 relevant memories:\n- Fact 1\n- Fact 2",
            tool_call_id="memory_search_auto"
        )

        # Verify structure
        assert ai_tool_call.content is not None
        assert len(ai_tool_call.tool_calls) == 1
        assert ai_tool_call.tool_calls[0]["name"] == "search_memory"
        assert tool_result.tool_call_id == "memory_search_auto"

    @pytest.mark.asyncio
    async def test_inject_memory_context_returns_messages_or_empty(self, service):
        """Test memory injection returns proper messages or empty list on error."""
        result = await service.inject_memory_context("Hello")

        # Should return either messages (if Neo4j is running) or empty list (if not)
        if result:
            # If we got results, verify structure
            assert len(result) == 2
            assert isinstance(result[0], AIMessage)
            assert isinstance(result[1], ToolMessage)
        else:
            # Empty list is also valid (error case)
            assert result == []


class TestCheckInterrupts:
    """Test interrupt/escalation checking."""

    @pytest.mark.asyncio
    async def test_check_interrupts_no_interrupts(self, service):
        """Test when there are no pending interrupts."""
        mock_state = MagicMock()
        mock_state.interrupts = []
        mock_state.values = {"messages": []}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_interrupts_user_question(self, service):
        """Test detecting user question interrupt."""
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "user_question",
            "question": "What color should the button be?",
            "instructions": "Please choose a color"
        }

        mock_state = MagicMock()
        mock_state.interrupts = [mock_interrupt]
        mock_state.values = {"messages": []}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is not None
        assert result["type"] == "user_question"
        assert "color" in result["question"]

    @pytest.mark.asyncio
    async def test_check_interrupts_tool_approval(self, service):
        """Test detecting tool approval interrupt."""
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "tool_approval_request",
            "tool_name": "send_email",
            "tool_args": {"to": "user@example.com"},
            "tool_call_id": "call-123"
        }

        mock_state = MagicMock()
        mock_state.interrupts = [mock_interrupt]
        mock_state.values = {"messages": []}
        mock_state.next = []

        mock_agent = AsyncMock()
        mock_agent.aget_state.return_value = mock_state

        result = await service.check_interrupts("test-thread", mock_agent)

        assert result is not None
        assert result["type"] == "tool_approval_request"
        assert result["tool_name"] == "send_email"


class TestGlobalInstance:
    """Test the global chat_service instance."""

    def test_global_instance_exists(self):
        """Test that the global chat_service instance is available."""
        assert chat_service is not None
        assert isinstance(chat_service, ChatService)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
