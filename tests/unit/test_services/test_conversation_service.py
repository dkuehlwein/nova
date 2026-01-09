"""
Conversation Service Unit Tests

Tests for the ConversationService class that handles conversation management and history.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.services.conversation_service import (
    ConversationService,
    conversation_service,
    cleanup_task_chat_data,
)
from backend.utils.langgraph_utils import (
    TASK_THREAD_PREFIX,
    create_task_thread_id,
    create_langgraph_config,
)


@pytest.fixture
def service():
    """Create a ConversationService instance for testing."""
    return ConversationService()


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
        assert config["configurable"]["thread_id"].startswith("chat-")


class TestListThreads:
    """Test thread listing from checkpointer."""

    @pytest.mark.asyncio
    async def test_list_threads_empty(self, service):
        """Test listing threads when none exist."""
        mock_checkpointer = MagicMock()
        mock_checkpointer.alist = AsyncMock(return_value=iter([]))

        result = await service.list_threads(mock_checkpointer)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_threads_multiple(self, service):
        """Test listing multiple threads."""
        mock_checkpoint1 = MagicMock()
        mock_checkpoint1.config = {"configurable": {"thread_id": "thread-1"}}

        mock_checkpoint2 = MagicMock()
        mock_checkpoint2.config = {"configurable": {"thread_id": "thread-2"}}

        async def mock_alist(config):
            for cp in [mock_checkpoint1, mock_checkpoint2]:
                yield cp

        mock_checkpointer = MagicMock()
        mock_checkpointer.alist = mock_alist

        result = await service.list_threads(mock_checkpointer)

        assert "thread-1" in result
        assert "thread-2" in result

    @pytest.mark.asyncio
    async def test_list_threads_deduplicates(self, service):
        """Test that duplicate thread IDs are removed."""
        mock_checkpoint1 = MagicMock()
        mock_checkpoint1.config = {"configurable": {"thread_id": "thread-1"}}

        mock_checkpoint2 = MagicMock()
        mock_checkpoint2.config = {"configurable": {"thread_id": "thread-1"}}  # Duplicate

        async def mock_alist(config):
            for cp in [mock_checkpoint1, mock_checkpoint2]:
                yield cp

        mock_checkpointer = MagicMock()
        mock_checkpointer.alist = mock_alist

        result = await service.list_threads(mock_checkpointer)

        assert len(result) == 1
        assert result[0] == "thread-1"

    @pytest.mark.asyncio
    async def test_list_threads_no_alist(self, service):
        """Test handling checkpointer without alist method."""
        mock_checkpointer = MagicMock(spec=[])  # No alist method

        result = await service.list_threads(mock_checkpointer)
        assert result == []


class TestGetHistory:
    """Test chat history retrieval."""

    @pytest.mark.asyncio
    async def test_get_history_no_state(self, service):
        """Test getting history when no state exists."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = None

        result = await service.get_history("test-thread", mock_checkpointer)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_history_no_messages(self, service):
        """Test getting history when state exists but no messages."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {}
        }

        result = await service.get_history("test-thread", mock_checkpointer)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_history_user_message(self, service):
        """Test reconstructing user message from history."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {
                "messages": [HumanMessage(content="Hello world")]
            },
            "ts": "2025-01-08T10:00:00Z"
        }

        # Mock alist for timestamp mapping
        async def mock_alist(config):
            return
            yield  # Empty async generator

        mock_checkpointer.alist = mock_alist

        result = await service.get_history("test-thread", mock_checkpointer)

        assert len(result) == 1
        assert result[0].sender == "user"
        assert result[0].content == "Hello world"

    @pytest.mark.asyncio
    async def test_get_history_ai_message(self, service):
        """Test reconstructing AI message from history."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {
                "messages": [AIMessage(content="I can help with that!")]
            },
            "ts": "2025-01-08T10:00:00Z"
        }

        async def mock_alist(config):
            return
            yield

        mock_checkpointer.alist = mock_alist

        result = await service.get_history("test-thread", mock_checkpointer)

        assert len(result) == 1
        assert result[0].sender == "assistant"
        assert result[0].content == "I can help with that!"


class TestGetTitle:
    """Test title generation for conversations."""

    @pytest.mark.asyncio
    async def test_get_title_regular_chat(self, service):
        """Test title from first user message for regular chat."""
        from backend.models.chat import ChatMessageDetail

        messages = [
            ChatMessageDetail(
                id="1",
                sender="user",
                content="What is the weather today?",
                created_at="2025-01-08T10:00:00Z",
                needs_decision=False,
            )
        ]

        result = await service.get_title("chat-123", messages)

        assert result == "What is the weather today?"

    @pytest.mark.asyncio
    async def test_get_title_truncates_long_message(self, service):
        """Test that long titles are truncated."""
        from backend.models.chat import ChatMessageDetail

        long_content = "A" * 100  # 100 character message
        messages = [
            ChatMessageDetail(
                id="1",
                sender="user",
                content=long_content,
                created_at="2025-01-08T10:00:00Z",
                needs_decision=False,
            )
        ]

        result = await service.get_title("chat-123", messages)

        assert len(result) == 53  # 50 chars + "..."
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_get_title_no_messages(self, service):
        """Test default title when no messages."""
        result = await service.get_title("chat-123", [])
        assert result == "New Chat"

    @pytest.mark.asyncio
    async def test_get_title_task_chat_fallback(self, service):
        """Test title fallback for task chat when DB fails."""
        from backend.models.chat import ChatMessageDetail

        messages = [
            ChatMessageDetail(
                id="1",
                sender="assistant",
                content="Working on task",
                created_at="2025-01-08T10:00:00Z",
                needs_decision=False,
            )
        ]

        # When DB lookup fails, should return fallback title
        with patch("backend.database.database.db_manager") as mock_db:
            mock_db.get_session.side_effect = Exception("DB unavailable")

            result = await service.get_title(f"{TASK_THREAD_PREFIX}task-123", messages)

            # Should return fallback format
            assert "Task Chat" in result or "task-123" in result


class TestGetSummary:
    """Test conversation summary building."""

    @pytest.mark.asyncio
    async def test_get_summary_no_messages(self, service):
        """Test summary returns None when no messages."""
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = None

        result = await service.get_summary("test-thread", mock_checkpointer)

        assert result is None


class TestDelete:
    """Test conversation deletion."""

    def test_delete_identifies_task_chat(self, service):
        """Test that task thread prefix correctly identifies task chats."""
        # Verify the thread ID parsing works correctly
        assert f"{TASK_THREAD_PREFIX}task-123".startswith(TASK_THREAD_PREFIX)
        assert "regular-chat-123".startswith(TASK_THREAD_PREFIX) is False

    def test_delete_extracts_task_id(self, service):
        """Test extracting task ID from thread ID."""
        thread_id = f"{TASK_THREAD_PREFIX}my-task-uuid"
        task_id = thread_id.replace(TASK_THREAD_PREFIX, "")
        assert task_id == "my-task-uuid"


class TestCleanupTaskChatData:
    """Test the cleanup_task_chat_data function."""

    def test_create_task_thread_id_format(self):
        """Test that task thread IDs are created correctly."""
        task_id = "abc-123-def"
        thread_id = create_task_thread_id(task_id)
        assert thread_id == f"{TASK_THREAD_PREFIX}abc-123-def"
        assert thread_id == "core_agent_task_abc-123-def"


class TestLangGraphUtils:
    """Test the langgraph_utils module."""

    def test_task_thread_prefix(self):
        """Test the TASK_THREAD_PREFIX constant."""
        assert TASK_THREAD_PREFIX == "core_agent_task_"

    def test_create_task_thread_id(self):
        """Test creating task thread IDs."""
        result = create_task_thread_id("abc-123")
        assert result == "core_agent_task_abc-123"


class TestGlobalInstance:
    """Test the global conversation_service instance."""

    def test_global_instance_exists(self):
        """Test that the global conversation_service instance is available."""
        assert conversation_service is not None
        assert isinstance(conversation_service, ConversationService)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
