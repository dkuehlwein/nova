"""
Pure Unit Tests for Outlook Email Processing Components.

These tests mock all external dependencies and test business logic in isolation.
All tests run without requiring databases or external services.

Components tested:
- OutlookFetcher: Email fetching from MCP servers (mocked)
- OutlookProcessor: Email-to-task pipeline (mocked)
- OutlookEmailHook: Hook orchestration (mocked)

Run with: uv run pytest tests/unit/input_hooks/test_outlook_hook_unit.py -v
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
import json

from backend.input_hooks.outlook_processing.fetcher import OutlookFetcher
from backend.input_hooks.outlook_processing.processor import OutlookProcessor, OutlookProcessingResult
from backend.input_hooks.outlook_email_hook import OutlookEmailHook
from backend.input_hooks.models import OutlookEmailHookConfig, OutlookEmailHookSettings


class TestOutlookFetcherUnit:
    """Pure unit tests for OutlookFetcher (all MCP calls mocked)."""

    @pytest.mark.asyncio
    async def test_fetch_unprocessed_emails_success(self):
        """Test fetching unprocessed emails returns correct format."""
        with patch('backend.input_hooks.outlook_processing.fetcher.mcp_manager') as mock_mcp:
            # Mock email list from Outlook MCP
            mock_emails = [
                {
                    "id": "email_123",
                    "subject": "Test Subject",
                    "sender_name": "John Doe",
                    "sender_email": "john@example.com",
                    "date": "2025-01-07 10:30:00",
                    "is_read": False,
                    "is_nova_processed": False,
                    "categories": []
                },
                {
                    "id": "email_456",
                    "subject": "Another Email",
                    "sender_name": "Jane Doe",
                    "sender_email": "jane@example.com",
                    "date": "2025-01-07 11:00:00",
                    "is_read": True,
                    "is_nova_processed": False,
                    "categories": []
                }
            ]

            # Mock full email content
            mock_full_email = {
                "id": "email_123",
                "subject": "Test Subject",
                "sender_name": "John Doe",
                "sender_email": "john@example.com",
                "date": "2025-01-07 10:30:00",
                "body": "This is the email body content.",
                "to": ["recipient@example.com"],
                "is_read": False
            }

            # Create mock tools (LiteLLM returns tools without prefix, but with [server_name] in description)
            list_tool = Mock()
            list_tool.name = "list_emails"
            list_tool.description = "[outlook_mac] List emails from Outlook"
            list_tool.arun = AsyncMock(return_value=mock_emails)

            read_tool = Mock()
            read_tool.name = "read_email"
            read_tool.description = "[outlook_mac] Read email content"
            read_tool.arun = AsyncMock(return_value=mock_full_email)

            mock_mcp.get_tools = AsyncMock(return_value=[list_tool, read_tool])

            fetcher = OutlookFetcher()
            emails = await fetcher.fetch_unprocessed_emails(max_emails=10)

            assert len(emails) == 2
            assert emails[0]["id"] == "email_123"
            assert emails[0]["subject"] == "Test Subject"

            # Verify list_emails was called with exclude_processed=True
            list_call_args = list_tool.arun.call_args[0][0]
            assert list_call_args.get("exclude_processed") is True

    @pytest.mark.asyncio
    async def test_fetch_unprocessed_emails_no_tools(self):
        """Test graceful handling when no Outlook tools found - returns empty list."""
        with patch('backend.input_hooks.outlook_processing.fetcher.mcp_manager') as mock_mcp:
            # Mock no Outlook tools available (tool without outlook_mac in description)
            mock_tool = Mock()
            mock_tool.name = "some_other_tool"
            mock_tool.description = "[other_server] Some tool"
            mock_mcp.get_tools = AsyncMock(return_value=[mock_tool])

            fetcher = OutlookFetcher()

            # Should gracefully return empty list instead of raising
            emails = await fetcher.fetch_unprocessed_emails()
            assert emails == []

    @pytest.mark.asyncio
    async def test_fetch_unprocessed_emails_empty_inbox(self):
        """Test handling of empty inbox."""
        with patch('backend.input_hooks.outlook_processing.fetcher.mcp_manager') as mock_mcp:
            list_tool = Mock()
            list_tool.name = "list_emails"
            list_tool.description = "[outlook_mac] List emails"
            list_tool.arun = AsyncMock(return_value=[])

            mock_mcp.get_tools = AsyncMock(return_value=[list_tool])

            fetcher = OutlookFetcher()
            emails = await fetcher.fetch_unprocessed_emails()

            assert emails == []

    @pytest.mark.asyncio
    async def test_fetch_unprocessed_emails_error_response(self):
        """Test graceful handling of error response from MCP - returns empty list."""
        with patch('backend.input_hooks.outlook_processing.fetcher.mcp_manager') as mock_mcp:
            list_tool = Mock()
            list_tool.name = "list_emails"
            list_tool.description = "[outlook_mac] List emails"
            list_tool.arun = AsyncMock(return_value={"error": "Outlook not connected"})

            mock_mcp.get_tools = AsyncMock(return_value=[list_tool])

            fetcher = OutlookFetcher()

            # Should gracefully return empty list instead of raising
            emails = await fetcher.fetch_unprocessed_emails()
            assert emails == []

    @pytest.mark.asyncio
    async def test_mark_email_processed_success(self):
        """Test marking email as processed."""
        with patch('backend.input_hooks.outlook_processing.fetcher.mcp_manager') as mock_mcp:
            mark_tool = Mock()
            mark_tool.name = "mark_email_processed"
            mark_tool.description = "[outlook_mac] Mark email as processed"
            mark_tool.arun = AsyncMock(return_value={
                "status": "success",
                "email_id": "email_123",
                "message": "Email marked as processed"
            })

            mock_mcp.get_tools = AsyncMock(return_value=[mark_tool])

            fetcher = OutlookFetcher()
            result = await fetcher.mark_email_processed("email_123")

            assert result is True
            mark_tool.arun.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_email_processed_already_marked(self):
        """Test marking email that's already processed."""
        with patch('backend.input_hooks.outlook_processing.fetcher.mcp_manager') as mock_mcp:
            mark_tool = Mock()
            mark_tool.name = "mark_email_processed"
            mark_tool.description = "[outlook_mac] Mark email as processed"
            mark_tool.arun = AsyncMock(return_value={
                "status": "already_marked",
                "email_id": "email_123",
                "message": "Email was already marked as processed"
            })

            mock_mcp.get_tools = AsyncMock(return_value=[mark_tool])

            fetcher = OutlookFetcher()
            result = await fetcher.mark_email_processed("email_123")

            assert result is True  # Should still be considered success

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check with working Outlook connection."""
        with patch('backend.input_hooks.outlook_processing.fetcher.mcp_manager') as mock_mcp:
            list_tool = Mock()
            list_tool.name = "list_emails"
            list_tool.description = "[outlook_mac] List emails"
            list_tool.arun = AsyncMock(return_value=[])

            mark_tool = Mock()
            mark_tool.name = "mark_email_processed"
            mark_tool.description = "[outlook_mac] Mark email as processed"

            mock_mcp.get_tools = AsyncMock(return_value=[list_tool, mark_tool])

            fetcher = OutlookFetcher()
            health = await fetcher.health_check()

            assert health["healthy"] is True
            assert "list_emails" in health["tools_available"]


class TestOutlookProcessorUnit:
    """Pure unit tests for OutlookProcessor (all dependencies mocked)."""

    @pytest.fixture
    def mock_fetcher(self):
        """Create a mock fetcher for testing."""
        with patch('backend.input_hooks.outlook_processing.processor.OutlookFetcher') as mock_class:
            mock_instance = AsyncMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    @pytest.mark.asyncio
    async def test_process_emails_creates_tasks(self):
        """Test that emails are converted to tasks."""
        with patch('backend.input_hooks.outlook_processing.processor.OutlookFetcher') as mock_fetcher_class:
            with patch('backend.input_hooks.outlook_processing.processor.create_task_tool') as mock_create_task:
                # Setup mock fetcher
                mock_fetcher = AsyncMock()
                mock_fetcher.fetch_unprocessed_emails = AsyncMock(return_value=[
                    {
                        "id": "email_123",
                        "subject": "Important Email",
                        "sender_name": "Boss",
                        "sender_email": "boss@company.com",
                        "date": "2025-01-07 09:00:00",
                        "body": "Please review the document.",
                        "to": ["me@company.com"],
                        "is_read": False
                    }
                ])
                mock_fetcher.mark_email_processed = AsyncMock(return_value=True)
                mock_fetcher_class.return_value = mock_fetcher

                # Mock task creation
                mock_create_task.return_value = 'Task created successfully: {"id": "task_abc123"}'

                processor = OutlookProcessor()
                result = await processor.process_emails(max_emails=10)

                assert result.emails_fetched == 1
                assert result.tasks_created == 1
                assert result.emails_marked == 1
                assert len(result.errors) == 0

                # Verify task was created with correct title
                mock_create_task.assert_called_once()
                call_kwargs = mock_create_task.call_args[1]
                assert "Read Outlook Email: Important Email" in call_kwargs["title"]
                assert "outlook" in call_kwargs["tags"]

    @pytest.mark.asyncio
    async def test_process_emails_handles_empty_inbox(self):
        """Test processing with no emails."""
        with patch('backend.input_hooks.outlook_processing.processor.OutlookFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher.fetch_unprocessed_emails = AsyncMock(return_value=[])
            mock_fetcher_class.return_value = mock_fetcher

            processor = OutlookProcessor()
            result = await processor.process_emails()

            assert result.emails_fetched == 0
            assert result.tasks_created == 0
            assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_process_emails_handles_task_creation_failure(self):
        """Test handling when task creation fails."""
        with patch('backend.input_hooks.outlook_processing.processor.OutlookFetcher') as mock_fetcher_class:
            with patch('backend.input_hooks.outlook_processing.processor.create_task_tool') as mock_create_task:
                mock_fetcher = AsyncMock()
                mock_fetcher.fetch_unprocessed_emails = AsyncMock(return_value=[
                    {
                        "id": "email_123",
                        "subject": "Test",
                        "sender_name": "Test",
                        "sender_email": "test@test.com",
                        "date": "2025-01-07",
                        "body": "Test",
                        "to": [],
                        "is_read": False
                    }
                ])
                mock_fetcher_class.return_value = mock_fetcher

                # Mock task creation failure
                mock_create_task.return_value = "Error: Failed to create task"

                processor = OutlookProcessor()
                result = await processor.process_emails()

                assert result.emails_fetched == 1
                assert result.tasks_created == 0
                assert len(result.errors) == 1


class TestOutlookEmailHookUnit:
    """Pure unit tests for OutlookEmailHook."""

    @pytest.fixture
    def hook_config(self):
        """Create test hook configuration."""
        return OutlookEmailHookConfig(
            name="test_outlook",
            hook_type="outlook_email",
            enabled=True,
            polling_interval=60,
            create_tasks=True,
            hook_settings=OutlookEmailHookSettings(
                max_per_fetch=50,
                folder="inbox"
            )
        )

    @pytest.mark.asyncio
    async def test_hook_process_items(self, hook_config):
        """Test hook processes items correctly."""
        with patch('backend.input_hooks.outlook_email_hook.OutlookProcessor') as mock_processor_class:
            mock_processor = AsyncMock()
            mock_processor.process_emails = AsyncMock(return_value=OutlookProcessingResult(
                emails_fetched=3,
                tasks_created=3,
                emails_marked=3,
                errors=[]
            ))
            mock_processor_class.return_value = mock_processor

            hook = OutlookEmailHook("test_outlook", hook_config)
            result = await hook.process_items()

            assert result.items_processed == 3
            assert result.tasks_created == 3
            assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_hook_disabled(self, hook_config):
        """Test disabled hook doesn't process."""
        hook_config.enabled = False

        hook = OutlookEmailHook("test_outlook", hook_config)
        result = await hook.process_items()

        assert result.items_processed == 0
        assert result.tasks_created == 0

    @pytest.mark.asyncio
    async def test_hook_normalize_item(self, hook_config):
        """Test email normalization."""
        hook = OutlookEmailHook("test_outlook", hook_config)

        raw_email = {
            "id": "email_123",
            "subject": "Test Subject",
            "sender_name": "John",
            "sender_email": "john@example.com",
            "date": "2025-01-07",
            "body": "Test body"
        }

        normalized = await hook.normalize_item(raw_email)

        assert normalized.source_type == "outlook_email"
        assert normalized.source_id == "email_123"
        assert "Read Outlook Email: Test Subject" in normalized.title
        assert normalized.should_create_task is True
        assert normalized.should_update_existing is False

    @pytest.mark.asyncio
    async def test_hook_should_create_task(self, hook_config):
        """Test should_create_task logic."""
        hook = OutlookEmailHook("test_outlook", hook_config)

        raw_email = {"id": "123", "subject": "Test"}
        normalized = await hook.normalize_item(raw_email)

        result = await hook.should_create_task(normalized)
        assert result is True

    @pytest.mark.asyncio
    async def test_hook_should_not_update_task(self, hook_config):
        """Test that Outlook emails never update tasks."""
        hook = OutlookEmailHook("test_outlook", hook_config)

        raw_email = {"id": "123", "subject": "Test"}
        normalized = await hook.normalize_item(raw_email)

        result = await hook.should_update_task(normalized, "existing_task_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_hook_health_check(self, hook_config):
        """Test health check includes Outlook info."""
        with patch('backend.input_hooks.outlook_email_hook.OutlookProcessor') as mock_processor_class:
            mock_processor = AsyncMock()
            mock_processor.health_check = AsyncMock(return_value={
                "healthy": True,
                "tools_available": ["outlook_mac__list_emails", "outlook_mac__mark_email_processed"]
            })
            mock_processor_class.return_value = mock_processor

            hook = OutlookEmailHook("test_outlook", hook_config)
            health = await hook.health_check()

            assert health["hook_type"] == "outlook_email"
            assert health["uses_category_tracking"] is True
            assert health["category_name"] == "Nova Processed"


class TestOutlookProcessingResultUnit:
    """Test the OutlookProcessingResult dataclass."""

    def test_result_to_dict(self):
        """Test conversion to dictionary."""
        result = OutlookProcessingResult(
            emails_fetched=5,
            tasks_created=4,
            emails_marked=4,
            errors=["One email failed"]
        )

        d = result.to_dict()

        assert d["emails_fetched"] == 5
        assert d["tasks_created"] == 4
        assert d["emails_marked"] == 4
        assert len(d["errors"]) == 1
        assert d["success"] is False  # Has errors

    def test_result_success_when_no_errors(self):
        """Test success flag when no errors."""
        result = OutlookProcessingResult(
            emails_fetched=3,
            tasks_created=3,
            emails_marked=3,
            errors=[]
        )

        d = result.to_dict()
        assert d["success"] is True

    def test_result_default_errors_list(self):
        """Test that errors defaults to empty list."""
        result = OutlookProcessingResult()

        assert result.errors == []
        assert result.to_dict()["success"] is True
