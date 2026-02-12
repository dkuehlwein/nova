"""
Chat Metadata Service Unit Tests

Tests for the ChatMetadataService class that manages persistent chat metadata
(titles, tool approvals).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.chat_metadata_service import ChatMetadataService
from backend.models.models import ChatMetadata


@pytest.fixture
def service():
    """Create a ChatMetadataService instance for testing."""
    return ChatMetadataService()


def _make_metadata(thread_id="thread-1", title=None, approved=None):
    """Helper to create a mock ChatMetadata object."""
    meta = MagicMock(spec=ChatMetadata)
    meta.thread_id = thread_id
    meta.custom_title = title
    meta.approved_tool_calls = approved or []
    return meta


class TestGetMetadata:
    """Test metadata retrieval."""

    @pytest.mark.asyncio
    async def test_returns_metadata_when_found(self, service):
        """Test that existing metadata is returned."""
        mock_meta = _make_metadata(title="Test Chat")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_meta

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("backend.services.chat_metadata_service.db_manager") as mock_db:
            mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await service.get_metadata("thread-1")

        assert result == mock_meta
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, service):
        """Test that None is returned for non-existent thread."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("backend.services.chat_metadata_service.db_manager") as mock_db:
            mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await service.get_metadata("nonexistent")

        assert result is None


class TestGetTitle:
    """Test title retrieval."""

    @pytest.mark.asyncio
    async def test_returns_title_when_set(self, service):
        """Test that custom title is returned when metadata exists."""
        with patch.object(service, "get_metadata", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _make_metadata(title="My Chat")
            result = await service.get_title("thread-1")

        assert result == "My Chat"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_metadata(self, service):
        """Test that None is returned when no metadata exists."""
        with patch.object(service, "get_metadata", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await service.get_title("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_title_not_set(self, service):
        """Test that None is returned when metadata exists but title is None."""
        with patch.object(service, "get_metadata", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _make_metadata(title=None)
            result = await service.get_title("thread-1")

        assert result is None


class TestSetTitle:
    """Test title setting/updating."""

    @pytest.mark.asyncio
    async def test_updates_existing_metadata(self, service):
        """Test that title is updated on existing metadata."""
        mock_meta = _make_metadata(title="Old Title")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_meta

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("backend.services.chat_metadata_service.db_manager") as mock_db:
            mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            await service.set_title("thread-1", "New Title")

        assert mock_meta.custom_title == "New Title"
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new_metadata_when_not_found(self, service):
        """Test that new metadata is created when thread has no metadata."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("backend.services.chat_metadata_service.db_manager") as mock_db:
            mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            await service.set_title("thread-1", "Brand New Title")

        mock_session.add.assert_called_once()
        added_meta = mock_session.add.call_args[0][0]
        assert added_meta.thread_id == "thread-1"
        assert added_meta.custom_title == "Brand New Title"
        assert added_meta.approved_tool_calls == []


class TestRecordApproval:
    """Test tool call approval recording."""

    @pytest.mark.asyncio
    async def test_appends_to_existing_approvals(self, service):
        """Test that a new approval is appended to existing list."""
        mock_meta = _make_metadata(approved=["call-1"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_meta

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("backend.services.chat_metadata_service.db_manager") as mock_db:
            mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            await service.record_approval("thread-1", "call-2")

        assert mock_meta.approved_tool_calls == ["call-1", "call-2"]

    @pytest.mark.asyncio
    async def test_does_not_duplicate_existing_approval(self, service):
        """Test that duplicate approval IDs are not added."""
        mock_meta = _make_metadata(approved=["call-1"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_meta

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("backend.services.chat_metadata_service.db_manager") as mock_db:
            mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            await service.record_approval("thread-1", "call-1")

        assert mock_meta.approved_tool_calls == ["call-1"]

    @pytest.mark.asyncio
    async def test_creates_metadata_when_not_found(self, service):
        """Test that new metadata with approval is created for new thread."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("backend.services.chat_metadata_service.db_manager") as mock_db:
            mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            await service.record_approval("thread-1", "call-1")

        mock_session.add.assert_called_once()
        added_meta = mock_session.add.call_args[0][0]
        assert added_meta.thread_id == "thread-1"
        assert added_meta.approved_tool_calls == ["call-1"]


class TestGetApprovedToolCalls:
    """Test approved tool call retrieval."""

    @pytest.mark.asyncio
    async def test_returns_set_of_approved_ids(self, service):
        """Test that approved tool calls are returned as a set."""
        with patch.object(service, "get_metadata", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _make_metadata(approved=["call-1", "call-2"])
            result = await service.get_approved_tool_calls("thread-1")

        assert result == {"call-1", "call-2"}
        assert isinstance(result, set)

    @pytest.mark.asyncio
    async def test_returns_empty_set_when_no_metadata(self, service):
        """Test that empty set is returned when no metadata exists."""
        with patch.object(service, "get_metadata", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await service.get_approved_tool_calls("nonexistent")

        assert result == set()

    @pytest.mark.asyncio
    async def test_returns_empty_set_when_no_approvals(self, service):
        """Test that empty set is returned when metadata has no approvals."""
        with patch.object(service, "get_metadata", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _make_metadata(approved=[])
            result = await service.get_approved_tool_calls("thread-1")

        assert result == set()


class TestSingletonInstance:
    """Test module-level singleton."""

    def test_singleton_exists(self):
        """Test that the module exports a singleton instance."""
        from backend.services.chat_metadata_service import chat_metadata_service
        assert isinstance(chat_metadata_service, ChatMetadataService)
