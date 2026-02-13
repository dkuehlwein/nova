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

        with patch("services.chat_metadata_service.chat_metadata_service.get_approved_tool_calls", new_callable=AsyncMock, return_value=set()):
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

        with patch("services.chat_metadata_service.chat_metadata_service.get_approved_tool_calls", new_callable=AsyncMock, return_value=set()):
            result = await service.get_history("test-thread", mock_checkpointer)

        assert len(result) == 1
        assert result[0].sender == "assistant"
        assert result[0].content == "I can help with that!"


class TestGetHistoryApprovedToolCalls:
    """Test that approved tool calls are marked in history."""

    @pytest.mark.asyncio
    async def test_approved_tool_call_marked_in_history(self, service):
        """Test that tool calls with matching approval metadata get approved=True."""
        ai_msg = AIMessage(
            content="I'll send that email for you.",
            tool_calls=[
                {"name": "ms_graph-send_email", "args": {"to": "test@example.com"}, "id": "call_abc123", "type": "tool_call"}
            ],
        )
        tool_msg = ToolMessage(
            content="Email sent successfully",
            tool_call_id="call_abc123",
            name="ms_graph-send_email",
        )

        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {
                "messages": [
                    HumanMessage(content="Send an email"),
                    ai_msg,
                    tool_msg,
                ]
            },
            "ts": "2025-01-08T10:00:00Z",
        }

        async def mock_alist(config):
            return
            yield

        mock_checkpointer.alist = mock_alist

        # Simulate that this tool call was previously approved
        with patch(
            "services.chat_metadata_service.chat_metadata_service.get_approved_tool_calls",
            new_callable=AsyncMock,
            return_value={"call_abc123"},
        ):
            result = await service.get_history("test-thread", mock_checkpointer)

        # Find the assistant message with tool calls
        assistant_msgs = [m for m in result if m.sender == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].tool_calls is not None
        assert len(assistant_msgs[0].tool_calls) == 1
        assert assistant_msgs[0].tool_calls[0]["approved"] is True

    @pytest.mark.asyncio
    async def test_unapproved_tool_call_not_marked(self, service):
        """Test that tool calls without matching approval don't get approved flag."""
        ai_msg = AIMessage(
            content="I'll send that email for you.",
            tool_calls=[
                {"name": "ms_graph-send_email", "args": {"to": "test@example.com"}, "id": "call_xyz789", "type": "tool_call"}
            ],
        )
        tool_msg = ToolMessage(
            content="Email sent successfully",
            tool_call_id="call_xyz789",
            name="ms_graph-send_email",
        )

        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "channel_values": {
                "messages": [
                    HumanMessage(content="Send an email"),
                    ai_msg,
                    tool_msg,
                ]
            },
            "ts": "2025-01-08T10:00:00Z",
        }

        async def mock_alist(config):
            return
            yield

        mock_checkpointer.alist = mock_alist

        # No approvals recorded
        with patch(
            "services.chat_metadata_service.chat_metadata_service.get_approved_tool_calls",
            new_callable=AsyncMock,
            return_value=set(),
        ):
            result = await service.get_history("test-thread", mock_checkpointer)

        assistant_msgs = [m for m in result if m.sender == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].tool_calls is not None
        assert "approved" not in assistant_msgs[0].tool_calls[0]


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

        with patch("services.chat_metadata_service.chat_metadata_service.get_title", new_callable=AsyncMock, return_value=None):
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

        with patch("services.chat_metadata_service.chat_metadata_service.get_title", new_callable=AsyncMock, return_value=None):
            result = await service.get_title("chat-123", messages)

        assert len(result) == 53  # 50 chars + "..."
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_get_title_no_messages(self, service):
        """Test default title when no messages."""
        with patch("services.chat_metadata_service.chat_metadata_service.get_title", new_callable=AsyncMock, return_value=None):
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


class TestGenerateTitle:
    """Test LLM-based title generation."""

    @pytest.mark.asyncio
    async def test_generate_title_success(self, service):
        """Test successful title generation via LiteLLM HTTP API."""
        from backend.models.chat import ChatMessageDetail

        messages = [
            ChatMessageDetail(
                id="1", sender="user", content="How do I deploy to Kubernetes?",
                created_at="2025-01-08T10:00:00Z", needs_decision=False,
            ),
            ChatMessageDetail(
                id="2", sender="assistant", content="Here's how to deploy to K8s...",
                created_at="2025-01-08T10:00:01Z", needs_decision=False,
            ),
        ]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Kubernetes Deployment Guide"}}]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("utils.llm_factory.get_chat_llm_config", return_value={"model": "test-model"}), \
             patch("utils.llm_factory.get_litellm_config", return_value={"base_url": "http://localhost:4000", "api_key": "sk-test"}), \
             patch("services.chat_metadata_service.chat_metadata_service.set_title", new_callable=AsyncMock) as mock_set_title:
            result = await service.generate_title("chat-123", messages)

        assert result == "Kubernetes Deployment Guide"
        mock_set_title.assert_called_once_with("chat-123", "Kubernetes Deployment Guide")

    @pytest.mark.asyncio
    async def test_generate_title_skips_task_chats(self, service):
        """Test that task chats are skipped."""
        result = await service.generate_title(f"{TASK_THREAD_PREFIX}task-1", [])
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_title_needs_both_messages(self, service):
        """Test that both user and assistant messages are needed."""
        from backend.models.chat import ChatMessageDetail

        user_only = [
            ChatMessageDetail(
                id="1", sender="user", content="Hello",
                created_at="2025-01-08T10:00:00Z", needs_decision=False,
            ),
        ]
        result = await service.generate_title("chat-123", user_only)
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_title_http_error_returns_none(self, service):
        """Test that HTTP errors return None gracefully."""
        from backend.models.chat import ChatMessageDetail

        messages = [
            ChatMessageDetail(
                id="1", sender="user", content="Hello",
                created_at="2025-01-08T10:00:00Z", needs_decision=False,
            ),
            ChatMessageDetail(
                id="2", sender="assistant", content="Hi there!",
                created_at="2025-01-08T10:00:01Z", needs_decision=False,
            ),
        ]

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("utils.llm_factory.get_chat_llm_config", return_value={"model": "test-model"}), \
             patch("utils.llm_factory.get_litellm_config", return_value={"base_url": "http://localhost:4000", "api_key": "sk-test"}):
            result = await service.generate_title("chat-123", messages)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_title_truncates_long_title(self, service):
        """Test that generated titles over 60 chars are truncated."""
        from backend.models.chat import ChatMessageDetail

        messages = [
            ChatMessageDetail(
                id="1", sender="user", content="Tell me everything",
                created_at="2025-01-08T10:00:00Z", needs_decision=False,
            ),
            ChatMessageDetail(
                id="2", sender="assistant", content="Sure, here's a lot of info...",
                created_at="2025-01-08T10:00:01Z", needs_decision=False,
            ),
        ]

        long_title = "A" * 80

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": long_title}}]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("utils.llm_factory.get_chat_llm_config", return_value={"model": "test-model"}), \
             patch("utils.llm_factory.get_litellm_config", return_value={"base_url": "http://localhost:4000", "api_key": "sk-test"}), \
             patch("services.chat_metadata_service.chat_metadata_service.set_title", new_callable=AsyncMock):
            result = await service.generate_title("chat-123", messages)

        assert len(result) == 60
        assert result.endswith("...")


class TestGenerateTitleSanitization:
    """Test that generate_title rejects bad LLM responses."""

    def _make_messages(self):
        from backend.models.chat import ChatMessageDetail
        return [
            ChatMessageDetail(
                id="1", sender="user", content="How do I deploy to Kubernetes?",
                created_at="2025-01-08T10:00:00Z", needs_decision=False,
            ),
            ChatMessageDetail(
                id="2", sender="assistant", content="Here's how to deploy to K8s...",
                created_at="2025-01-08T10:00:01Z", needs_decision=False,
            ),
        ]

    def _mock_llm_response(self, content):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": content}}]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        return mock_session

    @pytest.mark.asyncio
    async def test_rejects_title_containing_prompt_text(self, service):
        """Test that titles echoing the prompt instruction are rejected.

        Bug NOV-114: Some LLMs echo back the prompt instead of generating a title.
        """
        messages = self._make_messages()

        # LLM echoes back the prompt
        echoed_prompt = "Generate a short, descriptive title (max 6 words) for this conversation."
        mock_session = self._mock_llm_response(echoed_prompt)

        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("utils.llm_factory.get_chat_llm_config", return_value={"model": "test-model"}), \
             patch("utils.llm_factory.get_litellm_config", return_value={"base_url": "http://localhost:4000", "api_key": "sk-test"}), \
             patch("services.chat_metadata_service.chat_metadata_service.set_title", new_callable=AsyncMock) as mock_set_title:
            result = await service.generate_title("chat-123", messages)

        # Should reject the prompt echo and return None
        assert result is None
        mock_set_title.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_title_with_instruction_language(self, service):
        """Test that titles containing meta-instruction language are rejected."""
        messages = self._make_messages()

        # LLM returns instruction-like text
        bad_title = "Return ONLY the title text, nothing else"
        mock_session = self._mock_llm_response(bad_title)

        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("utils.llm_factory.get_chat_llm_config", return_value={"model": "test-model"}), \
             patch("utils.llm_factory.get_litellm_config", return_value={"base_url": "http://localhost:4000", "api_key": "sk-test"}), \
             patch("services.chat_metadata_service.chat_metadata_service.set_title", new_callable=AsyncMock) as mock_set_title:
            result = await service.generate_title("chat-123", messages)

        assert result is None
        mock_set_title.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_empty_title(self, service):
        """Test that empty/whitespace-only titles are rejected."""
        messages = self._make_messages()

        mock_session = self._mock_llm_response("   ")

        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("utils.llm_factory.get_chat_llm_config", return_value={"model": "test-model"}), \
             patch("utils.llm_factory.get_litellm_config", return_value={"base_url": "http://localhost:4000", "api_key": "sk-test"}), \
             patch("services.chat_metadata_service.chat_metadata_service.set_title", new_callable=AsyncMock) as mock_set_title:
            result = await service.generate_title("chat-123", messages)

        assert result is None
        mock_set_title.assert_not_called()

    @pytest.mark.asyncio
    async def test_accepts_valid_short_title(self, service):
        """Test that valid short titles are accepted."""
        messages = self._make_messages()

        mock_session = self._mock_llm_response("Kubernetes Deployment Guide")

        with patch("aiohttp.ClientSession", return_value=mock_session), \
             patch("utils.llm_factory.get_chat_llm_config", return_value={"model": "test-model"}), \
             patch("utils.llm_factory.get_litellm_config", return_value={"base_url": "http://localhost:4000", "api_key": "sk-test"}), \
             patch("services.chat_metadata_service.chat_metadata_service.set_title", new_callable=AsyncMock) as mock_set_title:
            result = await service.generate_title("chat-123", messages)

        assert result == "Kubernetes Deployment Guide"
        mock_set_title.assert_called_once_with("chat-123", "Kubernetes Deployment Guide")


class TestGetTitleErrorHandling:
    """Test that get_title handles metadata service errors gracefully."""

    @pytest.mark.asyncio
    async def test_get_title_falls_back_on_metadata_error(self, service):
        """Bug NOV-114: If chat_metadata_service.get_title() throws, get_title should
        not crash -- it should fall back to the first user message."""
        from backend.models.chat import ChatMessageDetail

        messages = [
            ChatMessageDetail(
                id="1", sender="user", content="How do I fix my Docker build?",
                created_at="2025-01-08T10:00:00Z", needs_decision=False,
            ),
        ]

        with patch("services.chat_metadata_service.chat_metadata_service.get_title",
                    new_callable=AsyncMock, side_effect=Exception("DB table does not exist")):
            result = await service.get_title("chat-123", messages)

        # Should fall back to first user message, not crash
        assert result == "How do I fix my Docker build?"


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
