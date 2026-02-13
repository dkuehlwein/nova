"""
Integration test for chat title generation against real LiteLLM.

Reproduces NOV-114: generate_title() fails to produce a valid title because
the configured LLM model (e.g. nemotron-3-nano) echoes the prompt back instead
of following instructions. This causes the title to never be persisted.

Requires: LiteLLM running at localhost:4000, PostgreSQL running.
"""

import os
import pytest
from datetime import datetime
from uuid import uuid4

# Skip if DB tests are disabled
SKIP_DB_TESTS = os.environ.get("NOVA_SKIP_DB", "0") == "1"

# Disable Phoenix for tests
os.environ["PHOENIX_ENABLED"] = "false"


def _make_messages():
    """Create realistic chat messages for title generation."""
    from backend.models.chat import ChatMessageDetail

    return [
        ChatMessageDetail(
            id="msg-1",
            sender="user",
            content="Hello, can you help me organize my tasks for this week?",
            created_at=datetime.now().isoformat(),
            needs_decision=False,
        ),
        ChatMessageDetail(
            id="msg-2",
            sender="assistant",
            content="Of course! I can help you organize your tasks. Let me know what you have planned.",
            created_at=datetime.now().isoformat(),
            needs_decision=False,
        ),
    ]


@pytest.mark.integration
class TestTitleGenerationWithLiteLLM:
    """Integration tests for generate_title() against real LiteLLM endpoint."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(SKIP_DB_TESTS, reason="Requires PostgreSQL")
    async def test_generate_title_returns_valid_title(self):
        """generate_title() should return a non-None, non-empty title string.

        This is the core regression test for NOV-114. If the LLM model can't
        produce a valid title (e.g. prompt leak), generate_title() should
        still return a usable title rather than None.
        """
        from backend.services.conversation_service import ConversationService

        service = ConversationService()
        thread_id = f"test-title-gen-{uuid4()}"
        messages = _make_messages()

        title = await service.generate_title(thread_id, messages)

        # Title MUST be returned (not None) - this is the bug
        assert title is not None, (
            "generate_title() returned None — title generation failed entirely. "
            "This means the LLM model could not produce a valid title."
        )
        assert isinstance(title, str)
        assert len(title) > 0
        assert len(title) <= 60

    @pytest.mark.asyncio
    @pytest.mark.skipif(SKIP_DB_TESTS, reason="Requires PostgreSQL")
    async def test_generate_title_persists_to_database(self):
        """generate_title() should persist the title via chat_metadata_service.

        After generate_title() succeeds, the title should be retrievable
        from the database via chat_metadata_service.get_title().
        """
        from backend.services.conversation_service import ConversationService
        from backend.services.chat_metadata_service import chat_metadata_service

        service = ConversationService()
        thread_id = f"test-title-persist-{uuid4()}"
        messages = _make_messages()

        title = await service.generate_title(thread_id, messages)

        assert title is not None, "generate_title() returned None — cannot test persistence"

        # Verify it was persisted
        stored_title = await chat_metadata_service.get_title(thread_id)
        assert stored_title == title, (
            f"Title not persisted to database. "
            f"Generated: {title!r}, Stored: {stored_title!r}"
        )

    @pytest.mark.asyncio
    @pytest.mark.skipif(SKIP_DB_TESTS, reason="Requires PostgreSQL")
    async def test_generate_title_not_prompt_leak(self):
        """The generated title should not contain prompt instruction text.

        Small models like nemotron-3-nano tend to echo instructions back.
        The title should be an actual title, not prompt content.
        """
        from backend.services.conversation_service import ConversationService

        service = ConversationService()
        thread_id = f"test-title-leak-{uuid4()}"
        messages = _make_messages()

        title = await service.generate_title(thread_id, messages)

        assert title is not None, "generate_title() returned None"

        # Should not contain instruction fragments
        lower = title.lower()
        prompt_fragments = [
            "generate a",
            "descriptive title",
            "return only",
            "nothing else",
            "max 6 words",
            "for this conversation",
            "user wants",
            "we need to",
        ]
        for fragment in prompt_fragments:
            assert fragment not in lower, (
                f"Title contains prompt fragment {fragment!r}: {title!r}"
            )
