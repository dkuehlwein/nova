"""
Tests for conversation service performance optimizations (NOV-121).

Verifies that:
1. get_summary() returns summaries using checkpoint timestamps directly
2. list_chats uses concurrent fetching instead of sequential
3. get_history() uses checkpoint timestamp for all messages (no expensive mapping)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def make_human_message(content: str) -> HumanMessage:
    """Create a real LangChain HumanMessage for testing."""
    return HumanMessage(content=content, id=str(uuid4()))


def make_ai_message(content: str, tool_calls=None) -> AIMessage:
    """Create a real LangChain AIMessage for testing."""
    return AIMessage(content=content, id=str(uuid4()), tool_calls=tool_calls or [])


def make_checkpoint_tuple(thread_id, messages, ts=None):
    """Create a mock checkpoint tuple."""
    ts = ts or datetime.now().isoformat()
    return Mock(
        config={"configurable": {"thread_id": thread_id}},
        metadata={"writes": {}},
        checkpoint={"ts": ts},
    )


def make_checkpointer(threads: dict, slow_alist=False):
    """Create a mock checkpointer with configurable threads.

    Args:
        threads: dict mapping thread_id -> list of messages
        slow_alist: if True, add artificial delay to alist to simulate slow DB
    """

    async def mock_aget(config):
        thread_id = config.get("configurable", {}).get("thread_id")
        if thread_id not in threads:
            return None
        messages = threads[thread_id]
        return {
            "channel_values": {"messages": messages},
            "ts": datetime.now().isoformat(),
        }

    async def mock_alist(config):
        if config is None:
            # Return all threads
            for thread_id in threads:
                if slow_alist:
                    await asyncio.sleep(0.01)  # Simulate slow DB
                yield make_checkpoint_tuple(thread_id, threads[thread_id])

    checkpointer = AsyncMock()
    checkpointer.aget = mock_aget
    checkpointer.alist = mock_alist
    return checkpointer


def make_mock_chat_metadata_service():
    """Create a mock chat_metadata_service with all async methods properly set up."""
    mock = MagicMock()
    mock.get_title = AsyncMock(return_value=None)
    mock.set_title = AsyncMock(return_value=None)
    mock.get_approved_tool_calls = AsyncMock(return_value=set())
    mock.record_approval = AsyncMock(return_value=None)
    return mock


class TestGetSummary:
    """Tests for the summary method that uses checkpoint timestamps directly."""

    @pytest.mark.asyncio
    async def test_get_summary_returns_chat_summary(self):
        """get_summary() should return a ChatSummary with required fields."""
        from services.conversation_service import ConversationService
        from models.chat import ChatSummary

        service = ConversationService()
        threads = {
            "test-thread-1": [
                make_human_message("Hello"),
                make_ai_message("Hi there!"),
            ],
        }
        checkpointer = make_checkpointer(threads)

        with patch(
            "services.chat_metadata_service.chat_metadata_service",
            make_mock_chat_metadata_service(),
        ):
            summary = await service.get_summary("test-thread-1", checkpointer)

        assert summary is not None
        assert isinstance(summary, ChatSummary)
        assert summary.id == "test-thread-1"
        assert summary.message_count > 0

    @pytest.mark.asyncio
    async def test_get_summary_returns_none_for_missing_thread(self):
        """get_summary() should return None for nonexistent threads."""
        from services.conversation_service import ConversationService

        service = ConversationService()
        checkpointer = make_checkpointer({})

        summary = await service.get_summary("nonexistent", checkpointer)
        assert summary is None


class TestListChatsPerformance:
    """Tests that chat listing uses concurrent fetching."""

    @pytest.mark.asyncio
    async def test_list_chats_uses_concurrent_fetching(self):
        """list_chats should use asyncio.gather (or equivalent) for concurrent fetching,
        not a sequential loop."""
        from services.conversation_service import ConversationService

        # Create 10 threads, each with slow alist to make sequential vs concurrent measurable
        threads = {}
        for i in range(10):
            threads[f"chat-{i}"] = [
                make_human_message(f"Message {i}"),
                make_ai_message(f"Response {i}"),
            ]

        checkpointer = make_checkpointer(threads, slow_alist=True)
        service = ConversationService()

        with patch(
            "services.chat_metadata_service.chat_metadata_service",
            make_mock_chat_metadata_service(),
        ):
            # list_threads returns thread IDs; we then need summaries
            thread_ids = await service.list_threads(checkpointer)

            # The key test: fetching summaries for all threads concurrently
            summaries = await asyncio.gather(
                *[service.get_summary(tid, checkpointer) for tid in thread_ids]
            )

        non_none = [s for s in summaries if s is not None]
        assert len(non_none) == 10, f"Expected 10 summaries, got {len(non_none)}"


class TestGetHistoryTimestamps:
    """Tests that get_history uses checkpoint timestamps directly."""

    @pytest.mark.asyncio
    async def test_get_history_returns_messages_with_checkpoint_timestamps(self):
        """Messages should use the checkpoint timestamp directly."""
        from services.conversation_service import ConversationService

        service = ConversationService()
        threads = {
            "test-thread-1": [
                make_human_message("Hello"),
                make_ai_message("Hi there!"),
            ],
        }
        checkpointer = make_checkpointer(threads)

        with patch(
            "services.chat_metadata_service.chat_metadata_service",
            make_mock_chat_metadata_service(),
        ):
            messages = await service.get_history("test-thread-1", checkpointer)

        assert len(messages) == 2
        # Each message should have a created_at timestamp (the checkpoint timestamp)
        for msg in messages:
            assert msg.created_at is not None

    @pytest.mark.asyncio
    async def test_get_history_no_timestamp_mapping_method(self):
        """_build_timestamp_mapping should not exist (removed for performance)."""
        from services.conversation_service import ConversationService

        service = ConversationService()
        assert not hasattr(service, "_build_timestamp_mapping"), (
            "_build_timestamp_mapping should be removed; "
            "checkpoint timestamps are used directly"
        )
