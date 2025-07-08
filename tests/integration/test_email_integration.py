"""
Integration test for email processing functionality.

Tests the complete flow: email fetching -> task creation -> deduplication
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, Mock
from datetime import datetime

from backend.email_processing.processor import EmailProcessor
from backend.email_processing.normalizer import EmailNormalizer
from backend.email_processing.task_creator import EmailTaskCreator
from backend.tasks.email_tasks import fetch_emails, process_single_email
from backend.database.database import db_manager
from backend.models.models import Task, ProcessedEmail
from backend.models.email import EmailMetadata
from sqlalchemy import select


@pytest.fixture
def sample_email_data():
    """Sample email API data for testing."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for uniqueness
    return {
        "id": f"test_email_{unique_id}",
        "threadId": f"test_thread_{unique_id}",
        "labelIds": ["INBOX", "UNREAD"],
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test Email Subject"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@nova.dev"},
                {"name": "Date", "value": "Wed, 06 Jun 2025 10:00:00 +0000"}
            ],
            "mimeType": "text/plain",
            "body": {
                "data": "VGVzdCBlbWFpbCBib2R5IGNvbnRlbnQ="  # Base64 encoded "Test email body content"
            }
        }
    }


class TestEmailIntegration:
    """Integration tests for email processing."""
    
    @pytest.mark.asyncio
    @patch('backend.email_processing.processor.EmailProcessor._get_user_settings')
    @patch('backend.email_processing.fetcher.mcp_manager')
    async def test_email_to_task_creation_flow(
        self, 
        mock_mcp_manager, 
        mock_get_user_settings, 
        sample_email_data
    ):
        """Test complete flow from email fetch to task creation."""
        # Mock user settings
        mock_user_settings = Mock()
        mock_user_settings.email_polling_enabled = True
        mock_user_settings.email_create_tasks = True
        mock_user_settings.email_max_per_fetch = 50
        mock_user_settings.email_label_filter = "INBOX"
        mock_get_user_settings.return_value = mock_user_settings

        # Mock MCP manager
        mock_list_messages_tool = AsyncMock()
        mock_list_messages_tool.name = "list_messages"
        email_id = sample_email_data["id"]
        mock_list_messages_tool.arun.return_value = f'{{"messages": [{{"id": "{email_id}"}}]}}'
        mock_get_message_tool = AsyncMock()
        mock_get_message_tool.name = "get_message"
        mock_get_message_tool.arun.return_value = sample_email_data
        async def get_tools_side_effect(*args, **kwargs):
            return [mock_list_messages_tool, mock_get_message_tool]
        mock_mcp_manager.get_tools.side_effect = get_tools_side_effect

        processor = EmailProcessor()
        emails = await processor.fetch_new_emails()
        assert len(emails) == 1
        assert emails[0]["id"] == email_id

        task_created = await processor.process_email(emails[0])
        assert task_created is True

        async with db_manager.get_session() as session:
            task_stmt = select(Task).where(Task.title.like("Read Email: Test Email Subject"))
            task_result = await session.execute(task_stmt)
            task = task_result.scalar_one_or_none()
            assert task is not None
            assert "Test email body content" in task.description

            processed_stmt = select(ProcessedEmail).where(ProcessedEmail.email_id == email_id)
            processed_result = await session.execute(processed_stmt)
            processed_email = processed_result.scalar_one_or_none()
            assert processed_email is not None

        await processor.close()

    @pytest.mark.asyncio
    @patch('backend.email_processing.processor.EmailProcessor._get_user_settings')
    @patch('backend.email_processing.fetcher.mcp_manager')
    async def test_email_deduplication(
        self, 
        mock_mcp_manager, 
        mock_get_user_settings, 
        sample_email_data
    ):
        """Test that duplicate emails don't create multiple tasks."""
        mock_user_settings = Mock()
        mock_user_settings.email_polling_enabled = True
        mock_user_settings.email_create_tasks = True
        mock_user_settings.email_max_per_fetch = 50
        mock_user_settings.email_label_filter = "INBOX"
        mock_get_user_settings.return_value = mock_user_settings

        mock_list_messages_tool = AsyncMock()
        mock_list_messages_tool.name = "list_messages"
        email_id = sample_email_data["id"]
        mock_list_messages_tool.arun.return_value = f'{{"messages": [{{"id": "{email_id}"}}]}}'
        mock_get_message_tool = AsyncMock()
        mock_get_message_tool.name = "get_message"
        mock_get_message_tool.arun.return_value = sample_email_data
        async def get_tools_side_effect(*args, **kwargs):
            return [mock_list_messages_tool, mock_get_message_tool]
        mock_mcp_manager.get_tools.side_effect = get_tools_side_effect

        processor = EmailProcessor()
        emails_first = await processor.fetch_new_emails()
        await processor.process_email(emails_first[0])

        processor_second = EmailProcessor()
        emails_second = await processor_second.fetch_new_emails()
        assert len(emails_second) == 0

        await processor.close()
        await processor_second.close()

    @pytest.mark.asyncio
    @patch('backend.email_processing.processor.EmailProcessor._get_user_settings')
    async def test_email_processing_with_disabled_config(self, mock_get_user_settings):
        """Test that emails are not processed when configuration is disabled."""
        mock_user_settings = Mock()
        mock_user_settings.email_polling_enabled = False
        mock_get_user_settings.return_value = mock_user_settings

        processor = EmailProcessor()
        emails = await processor.fetch_new_emails()
        assert len(emails) == 0
        await processor.close()

    @patch('backend.tasks.email_tasks.EmailProcessor')
    def test_celery_task_integration(self, mock_processor_class):
        """Test Celery task integration with mocked dependencies."""
        mock_processor = AsyncMock()
        mock_processor_class.return_value = mock_processor
        mock_processor.fetch_new_emails.return_value = [{"id": "test"}]
        mock_processor.process_email.return_value = True

        fetch_emails()

        mock_processor.fetch_new_emails.assert_called_once()
        mock_processor.process_email.assert_called_once_with({"id": "test"})

    @patch('backend.tasks.email_tasks.EmailProcessor')
    def test_single_email_processing_task(self, mock_processor_class):
        """Test processing a single email via Celery task."""
        mock_processor = AsyncMock()
        mock_processor_class.return_value = mock_processor
        mock_processor.process_email.return_value = True

        process_single_email({"id": "test"})

        mock_processor.process_email.assert_called_once_with({"id": "test"})

    @pytest.mark.asyncio
    @patch('backend.email_processing.processor.EmailProcessor._get_user_settings')
    @patch('backend.email_processing.fetcher.mcp_manager')
    async def test_error_handling_in_email_processing(self, mock_mcp_manager, mock_get_user_settings):
        """Test error handling during email processing."""
        mock_user_settings = Mock()
        mock_user_settings.email_polling_enabled = True
        mock_get_user_settings.return_value = mock_user_settings

        mock_mcp_manager.get_tools.side_effect = Exception("Email API error")

        processor = EmailProcessor()
        with pytest.raises(Exception, match="Email API error"):
            await processor.fetch_new_emails()
        await processor.close()

    def test_metadata_extraction(self, sample_email_data):
        """Test email metadata extraction."""
        normalizer = EmailNormalizer()
        normalized_data = normalizer.normalize(sample_email_data)
        metadata = EmailMetadata(
            email_id=normalized_data["id"],
            thread_id=normalized_data["thread_id"],
            subject=normalized_data["subject"],
            sender=normalized_data["from"],
            recipient=normalized_data["to"],
            date=datetime.now(), # a real datetime object
            has_attachments=normalized_data["has_attachments"],
            labels=normalized_data["labels"]
        )

        assert metadata.email_id == sample_email_data["id"]
        assert metadata.subject == "Test Email Subject"

    def test_email_body_extraction(self, sample_email_data):
        """Test email body text extraction."""
        normalizer = EmailNormalizer()
        normalized_data = normalizer.normalize(sample_email_data)
        assert normalized_data["content"] == "Test email body content"

    def test_task_description_formatting(self, sample_email_data):
        """Test task description formatting with email metadata."""
        task_creator = EmailTaskCreator()
        normalizer = EmailNormalizer()
        normalized_data = normalizer.normalize(sample_email_data)
        metadata = EmailMetadata(
            email_id=normalized_data["id"],
            thread_id=normalized_data["thread_id"],
            subject=normalized_data["subject"],
            sender=normalized_data["from"],
            recipient=normalized_data["to"],
            date=datetime.now(), # a real datetime object
            has_attachments=normalized_data["has_attachments"],
            labels=normalized_data["labels"]
        )
        mock_user_settings = Mock()
        mock_user_settings.timezone = "UTC"
        description = task_creator._format_task_description(metadata, mock_user_settings, normalized_data)

        assert "**From:** sender@example.com" in description
        assert "Test email body content" in description
