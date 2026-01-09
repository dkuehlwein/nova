"""
Integration Tests for Chat and Conversation Services

Tests the service layer with real infrastructure (PostgreSQL, Redis).
These tests verify the full service layer pattern works correctly with
actual database connections and checkpointers.

NOTE: These tests require full infrastructure:
- PostgreSQL database
- Redis
- Config files

Skip these tests when running quick unit tests with NOVA_SKIP_DB=1.
"""

import os
import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# Skip if DB tests are disabled
SKIP_DB_TESTS = os.environ.get("NOVA_SKIP_DB", "0") == "1"

# Disable Phoenix for tests
os.environ["PHOENIX_ENABLED"] = "false"


def create_mock_checkpointer(state_data=None):
    """Create a mock checkpointer that behaves like a real one for testing.

    The InMemorySaver has a complex API that requires checkpoint_ns and other
    config values. For integration tests of the service layer, we use a mock
    that simulates the checkpointer interface.
    """
    mock = MagicMock()
    mock.aget = AsyncMock(return_value=state_data)

    async def mock_alist(config):
        if state_data:
            checkpoint_tuple = MagicMock()
            checkpoint_tuple.config = config or {"configurable": {"thread_id": "test"}}
            checkpoint_tuple.checkpoint = {"ts": datetime.now().isoformat()}
            checkpoint_tuple.metadata = {"writes": {}}
            yield checkpoint_tuple

    mock.alist = mock_alist
    return mock


@pytest.fixture
def mock_checkpointer():
    """Create a mock checkpointer for isolated tests."""
    return create_mock_checkpointer()


class TestChatServiceWithCheckpointer:
    """Integration tests for ChatService with checkpointer operations."""

    @pytest.mark.asyncio
    async def test_is_first_turn_no_state(self):
        """Test first turn detection when no state exists."""
        from backend.services.chat_service import ChatService

        service = ChatService()
        thread_id = f"test-thread-{uuid4()}"

        # Create checkpointer that returns None (no state)
        checkpointer = create_mock_checkpointer(state_data=None)

        result = await service.is_first_turn(thread_id, checkpointer)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_first_turn_with_messages(self):
        """Test first turn detection when messages exist."""
        from backend.services.chat_service import ChatService

        service = ChatService()
        thread_id = f"test-thread-{uuid4()}"

        # Create checkpointer that returns state with messages
        checkpointer = create_mock_checkpointer(
            state_data={
                "channel_values": {"messages": [HumanMessage(content="Hello")]},
            }
        )

        result = await service.is_first_turn(thread_id, checkpointer)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_first_turn_empty_messages(self):
        """Test first turn detection when state exists but no messages."""
        from backend.services.chat_service import ChatService

        service = ChatService()
        thread_id = f"test-thread-{uuid4()}"

        # Create checkpointer that returns state with empty messages
        checkpointer = create_mock_checkpointer(
            state_data={"channel_values": {"messages": []}}
        )

        result = await service.is_first_turn(thread_id, checkpointer)
        assert result is True

    @pytest.mark.asyncio
    async def test_memory_injection_graceful_degradation(self):
        """Test that memory injection fails gracefully when Neo4j is unavailable."""
        from backend.services.chat_service import ChatService

        service = ChatService()

        # This should not raise an exception even if Neo4j is down
        result = await service.inject_memory_context("Hello world")

        # Should return either valid messages or empty list
        assert isinstance(result, list)
        if result:
            assert len(result) == 2
            assert isinstance(result[0], AIMessage)
            assert isinstance(result[1], ToolMessage)


class TestConversationServiceWithCheckpointer:
    """Integration tests for ConversationService with checkpointer."""

    @pytest.mark.asyncio
    async def test_list_threads_with_checkpointer(self):
        """Test listing threads from a checkpointer."""
        from backend.services.conversation_service import ConversationService

        service = ConversationService()

        # Create a mock checkpointer that yields multiple threads
        thread_ids = [f"test-thread-{uuid4()}" for _ in range(3)]

        async def mock_alist(config):
            for thread_id in thread_ids:
                checkpoint_tuple = MagicMock()
                checkpoint_tuple.config = {"configurable": {"thread_id": thread_id}}
                yield checkpoint_tuple

        checkpointer = MagicMock()
        checkpointer.alist = mock_alist

        # List threads
        result = await service.list_threads(checkpointer)

        # All test threads should be found
        assert len(result) == 3
        for thread_id in thread_ids:
            assert thread_id in result

    @pytest.mark.asyncio
    async def test_list_threads_deduplicates(self):
        """Test that list_threads removes duplicate thread IDs."""
        from backend.services.conversation_service import ConversationService

        service = ConversationService()
        thread_id = f"test-thread-{uuid4()}"

        # Create checkpointer that yields the same thread ID twice
        async def mock_alist(config):
            for _ in range(3):  # Same thread 3 times
                checkpoint_tuple = MagicMock()
                checkpoint_tuple.config = {"configurable": {"thread_id": thread_id}}
                yield checkpoint_tuple

        checkpointer = MagicMock()
        checkpointer.alist = mock_alist

        result = await service.list_threads(checkpointer)

        # Should only have one entry
        assert len(result) == 1
        assert result[0] == thread_id

    @pytest.mark.asyncio
    async def test_get_history_reconstructs_messages(self):
        """Test that get_history correctly reconstructs conversation messages."""
        from backend.services.conversation_service import ConversationService

        service = ConversationService()
        thread_id = f"test-thread-{uuid4()}"

        # Create a conversation with user and AI messages
        messages = [
            HumanMessage(content="Hello, can you help me?"),
            AIMessage(content="Of course! What do you need?"),
            HumanMessage(content="I need to create a task"),
            AIMessage(content="I'll help you create that task."),
        ]

        checkpointer = create_mock_checkpointer(
            state_data={
                "channel_values": {"messages": messages},
                "ts": datetime.now().isoformat(),
            }
        )

        # Get history
        result = await service.get_history(thread_id, checkpointer)

        # Should have reconstructed all messages
        assert len(result) >= 2  # At least user and assistant messages

        # Verify message content
        user_messages = [m for m in result if m.sender == "user"]
        assistant_messages = [m for m in result if m.sender == "assistant"]

        assert len(user_messages) >= 1
        assert len(assistant_messages) >= 1
        assert "Hello" in user_messages[0].content

    @pytest.mark.asyncio
    async def test_get_history_with_tool_calls(self):
        """Test that get_history correctly handles messages with tool calls."""
        from backend.services.conversation_service import ConversationService

        service = ConversationService()
        thread_id = f"test-thread-{uuid4()}"

        # Create a conversation with tool calls
        messages = [
            HumanMessage(content="Create a task for me"),
            AIMessage(
                content="I'll create that task for you.",
                tool_calls=[
                    {
                        "name": "create_task",
                        "args": {"title": "Test Task"},
                        "id": "call-123",
                    }
                ],
            ),
            ToolMessage(
                content="Task created successfully",
                tool_call_id="call-123",
                name="create_task",
            ),
            AIMessage(content="Done! I've created the task for you."),
        ]

        checkpointer = create_mock_checkpointer(
            state_data={
                "channel_values": {"messages": messages},
                "ts": datetime.now().isoformat(),
            }
        )

        # Get history
        result = await service.get_history(thread_id, checkpointer)

        # Find the assistant message with tool calls
        assistant_with_tools = [
            m for m in result if m.sender == "assistant" and m.tool_calls
        ]

        # Should have at least one message with tool calls
        assert len(assistant_with_tools) >= 1
        assert assistant_with_tools[0].tool_calls[0]["tool"] == "create_task"

    @pytest.mark.asyncio
    async def test_get_title_for_regular_chat(self):
        """Test title generation for regular chat threads."""
        from backend.services.conversation_service import ConversationService
        from backend.models.chat import ChatMessageDetail

        service = ConversationService()

        messages = [
            ChatMessageDetail(
                id="1",
                sender="user",
                content="How do I configure the email settings?",
                created_at=datetime.now().isoformat(),
                needs_decision=False,
            ),
            ChatMessageDetail(
                id="2",
                sender="assistant",
                content="Here's how to configure email...",
                created_at=datetime.now().isoformat(),
                needs_decision=False,
            ),
        ]

        title = await service.get_title("regular-chat-123", messages)

        # Title should be based on first user message
        assert "email" in title.lower() or "configure" in title.lower()

    @pytest.mark.asyncio
    async def test_get_summary_builds_complete_summary(self):
        """Test that get_summary builds a complete conversation summary."""
        from backend.services.conversation_service import ConversationService

        service = ConversationService()
        thread_id = f"test-thread-{uuid4()}"

        # Create a conversation
        messages = [
            HumanMessage(content="What's the status of my tasks?"),
            AIMessage(content="You have 3 tasks in progress."),
        ]

        checkpointer = create_mock_checkpointer(
            state_data={
                "channel_values": {"messages": messages},
                "ts": datetime.now().isoformat(),
            }
        )

        # Get summary
        summary = await service.get_summary(thread_id, checkpointer)

        assert summary is not None
        assert summary.id == thread_id
        assert summary.message_count >= 2
        assert "tasks" in summary.title.lower() or "status" in summary.title.lower()
        assert summary.last_message is not None


@pytest.mark.skipif(SKIP_DB_TESTS, reason="Requires PostgreSQL (NOVA_SKIP_DB=1 is set)")
class TestServicesWithPostgresCheckpointer:
    """Integration tests requiring full PostgreSQL infrastructure."""

    @pytest.fixture
    async def service_manager_and_checkpointer(self):
        """Create a ServiceManager and get the PostgreSQL checkpointer."""
        from utils.service_manager import ServiceManager
        from utils.checkpointer_utils import get_checkpointer_from_service_manager

        # Try to get a real checkpointer
        try:
            checkpointer = await get_checkpointer_from_service_manager()
            yield checkpointer
        except Exception:
            pytest.skip("PostgreSQL not available")

    @pytest.mark.asyncio
    async def test_conversation_persistence_with_postgres(
        self, service_manager_and_checkpointer
    ):
        """Test that conversations are properly persisted to PostgreSQL."""
        from backend.services.conversation_service import ConversationService
        from backend.utils.langgraph_utils import create_langgraph_config

        checkpointer = service_manager_and_checkpointer
        service = ConversationService()
        thread_id = f"integration-test-{uuid4()}"
        config = create_langgraph_config(thread_id)

        try:
            # Save a conversation
            messages = [
                HumanMessage(content="Integration test message"),
                AIMessage(content="Integration test response"),
            ]

            await checkpointer.aput(
                config,
                {
                    "channel_values": {"messages": messages},
                    "ts": datetime.now().isoformat(),
                    "v": 1,
                },
                metadata={},
                new_versions={},
            )

            # Retrieve and verify
            history = await service.get_history(thread_id, checkpointer)

            assert len(history) >= 2
            assert any("Integration test" in m.content for m in history)

        finally:
            # Cleanup
            try:
                await checkpointer.adelete_thread(thread_id)
            except Exception:
                pass  # Best effort cleanup


class TestLangGraphUtilityFunctions:
    """Test the langgraph_utils module functions."""

    def test_create_langgraph_config_with_thread_id(self):
        """Test config creation with explicit thread ID."""
        from backend.utils.langgraph_utils import create_langgraph_config

        config = create_langgraph_config("my-thread-123")

        assert config == {"configurable": {"thread_id": "my-thread-123"}}

    def test_create_langgraph_config_generates_id(self):
        """Test config creation generates thread ID when none provided."""
        from backend.utils.langgraph_utils import create_langgraph_config

        config = create_langgraph_config()

        assert "configurable" in config
        assert "thread_id" in config["configurable"]
        assert config["configurable"]["thread_id"].startswith("chat-")

    def test_task_thread_id_functions(self):
        """Test task thread ID creation and parsing."""
        from backend.utils.langgraph_utils import (
            TASK_THREAD_PREFIX,
            create_task_thread_id,
            get_task_id_from_thread,
        )

        task_id = "abc-123-def"
        thread_id = create_task_thread_id(task_id)

        assert thread_id == f"{TASK_THREAD_PREFIX}{task_id}"
        assert get_task_id_from_thread(thread_id) == task_id
        assert get_task_id_from_thread("regular-chat") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
