"""
Integration test for email processing functionality.

Tests the complete flow: email fetching -> task creation -> deduplication
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, Mock
from datetime import datetime

from tasks.email_processor import EmailProcessor
from tasks.email_tasks import fetch_emails, process_single_email
from database.database import db_manager
from models.models import Task, ProcessedEmail
from models.email import EmailMetadata
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


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client for email operations."""
    mock_client = AsyncMock()
    
    # Mock successful connection
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    
    # Mock email API responses
    mock_client.call_tool = AsyncMock()
    
    return mock_client


@pytest.fixture
def mock_config():
    """Mock configuration with email settings enabled."""
    mock_config = Mock()
    mock_config.email = Mock()
    mock_config.email.enabled = True
    mock_config.email.create_tasks_from_emails = True
    mock_config.email.max_emails_per_fetch = 50
    mock_config.email.email_label_filter = "INBOX"
    mock_config.email.polling_interval_minutes = 5
    
    return mock_config


class TestEmailIntegration:
    """Integration tests for email processing."""
    
    @pytest.mark.asyncio
    async def test_email_to_task_creation_flow(
        self, 
        sample_email_data, 
        mock_mcp_client, 
        mock_config
    ):
        """Test complete flow from email fetch to task creation."""
        
        # Setup mocks
        with patch('tasks.email_processor.mcp_manager') as mock_mcp_manager, \
             patch('tasks.email_processor.settings') as mock_settings:
            
            # Configure mock settings
            mock_settings.EMAIL_ENABLED = True
            mock_settings.EMAIL_CREATE_TASKS = True
            mock_settings.EMAIL_MAX_PER_FETCH = 50
            mock_settings.EMAIL_LABEL_FILTER = "INBOX"
            
            # Create mock tools for the email processor
            mock_list_labels_tool = AsyncMock()
            mock_list_labels_tool.name = "list_labels"
            mock_list_labels_tool.arun.return_value = '{"labels": ["INBOX", "SENT"]}'
            
            mock_list_messages_tool = AsyncMock()
            mock_list_messages_tool.name = "list_messages"
            email_id = sample_email_data["id"]
            mock_list_messages_tool.arun.return_value = f'{{"messages": [{{"id": "{email_id}"}}]}}'
            
            mock_get_message_tool = AsyncMock()
            mock_get_message_tool.name = "get_message"
            # Return email data as direct dict (will be returned as-is)
            mock_get_message_tool.arun.return_value = sample_email_data
            
            # Mock the MCP manager to return our mock tools
            async def mock_get_tools():
                return [
                    mock_list_labels_tool,
                    mock_list_messages_tool,
                    mock_get_message_tool
                ]
            mock_mcp_manager.get_tools = mock_get_tools
            
            # Create email processor
            processor = EmailProcessor()
            
            # Test email fetching
            emails = await processor.fetch_new_emails()
            
            assert len(emails) == 1
            assert emails[0]["id"] == email_id
            
            # Test email processing
            task_created = await processor.process_email(sample_email_data)
            
            assert task_created is True
            
            # Verify task was created in database
            async with db_manager.get_session() as session:
                # Check task creation
                task_stmt = select(Task).where(Task.title.like("Read Email: Test Email Subject"))
                task_result = await session.execute(task_stmt)
                task = task_result.scalar_one_or_none()
                
                assert task is not None
                assert task.title == "Read Email: Test Email Subject"
                assert "sender@example.com" in task.description
                assert "Test email body content" in task.description
                assert task.status.value == "new"
                
                # Check processed email tracking
                processed_stmt = select(ProcessedEmail).where(
                    ProcessedEmail.email_id == email_id
                )
                processed_result = await session.execute(processed_stmt)
                processed_email = processed_result.scalar_one_or_none()
                
                assert processed_email is not None
                assert processed_email.email_id == email_id
                assert processed_email.thread_id == sample_email_data["threadId"]
                assert processed_email.subject == "Test Email Subject"
                assert processed_email.sender == "sender@example.com"
                assert processed_email.task_id == task.id
            
            await processor.close()
    
    @pytest.mark.asyncio
    async def test_email_deduplication(
        self, 
        sample_email_data, 
        mock_mcp_client, 
        mock_config
    ):
        """Test that duplicate emails don't create multiple tasks."""
        
        with patch('tasks.email_processor.mcp_manager') as mock_mcp_manager, \
             patch('tasks.email_processor.settings') as mock_settings:
            
            # Configure mock settings
            mock_settings.EMAIL_ENABLED = True
            mock_settings.EMAIL_CREATE_TASKS = True
            mock_settings.EMAIL_MAX_PER_FETCH = 50
            mock_settings.EMAIL_LABEL_FILTER = "INBOX"
            
            # Create mock tools for the email processor
            mock_list_labels_tool = AsyncMock()
            mock_list_labels_tool.name = "list_labels"
            mock_list_labels_tool.arun.return_value = '{"labels": ["INBOX"]}'
            
            mock_list_messages_tool = AsyncMock()
            mock_list_messages_tool.name = "list_messages"
            # First call returns the email, second call returns same email
            email_id = sample_email_data["id"]
            mock_list_messages_tool.arun.return_value = f'{{"messages": [{{"id": "{email_id}"}}]}}'
            
            mock_get_message_tool = AsyncMock()
            mock_get_message_tool.name = "get_message"
            mock_get_message_tool.arun.return_value = sample_email_data
            
            # Mock the MCP manager to return our mock tools
            async def mock_get_tools():
                return [
                    mock_list_labels_tool,
                    mock_list_messages_tool,
                    mock_get_message_tool
                ]
            mock_mcp_manager.get_tools = mock_get_tools
            
            processor = EmailProcessor()
            
            # Process email first time
            emails_first = await processor.fetch_new_emails()
            assert len(emails_first) == 1
            
            task_created_first = await processor.process_email(sample_email_data)
            assert task_created_first is True
            
            # Create new processor instance to test database-based deduplication
            processor_second = EmailProcessor()
            
            # Process same email second time
            emails_second = await processor_second.fetch_new_emails()
            # Should be empty due to deduplication
            assert len(emails_second) == 0
            
            # Verify only one task exists
            async with db_manager.get_session() as session:
                task_stmt = select(Task).where(Task.title.like("Read Email: Test Email Subject"))
                task_result = await session.execute(task_stmt)
                tasks = task_result.scalars().all()
                
                assert len(tasks) == 1
            
            await processor.close()
            await processor_second.close()
    
    @pytest.mark.asyncio
    async def test_email_processing_with_disabled_config(
        self, 
        sample_email_data, 
        mock_mcp_client
    ):
        """Test that emails are not processed when configuration is disabled."""
        
        # Mock disabled configuration
        mock_disabled_config = Mock()
        mock_disabled_config.email = Mock()
        mock_disabled_config.email.enabled = False
        
        with patch('tasks.email_processor.mcp_manager') as mock_mcp_manager, \
             patch('tasks.email_processor.settings') as mock_settings:
            
            # Configure mock settings for disabled state
            mock_settings.EMAIL_ENABLED = False
            
            processor = EmailProcessor()
            
            # Should return empty list when disabled
            emails = await processor.fetch_new_emails()
            assert len(emails) == 0
            
            # MCP manager should not be called when email processing is disabled
            # (Note: can't easily assert on async function mock, but we verify emails is empty)
            
            await processor.close()
    
    def test_celery_task_integration(
        self, 
        sample_email_data, 
        mock_mcp_client, 
        mock_config
    ):
        """Test Celery task integration with mocked dependencies."""
        
        with patch('tasks.email_tasks.EmailProcessor') as mock_processor_class, \
             patch('tasks.email_tasks.publish') as mock_publish:
            
            # Setup mock processor instance
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            
            # Mock processor methods
            mock_processor.fetch_new_emails.return_value = [sample_email_data]
            mock_processor.process_email.return_value = True
            
            # Call Celery task directly (not through Celery worker)
            result = fetch_emails()
            
            # Verify result
            assert result["emails_processed"] == 1
            assert result["tasks_created"] == 1
            assert "task_id" in result
            
            # Verify processor was used
            mock_processor.fetch_new_emails.assert_called_once()
            mock_processor.process_email.assert_called_once_with(sample_email_data)
            mock_processor.close.assert_called_once()
            
            # Verify events were published
            assert mock_publish.call_count >= 2  # start and completion events
    
    def test_single_email_processing_task(
        self, 
        sample_email_data, 
        mock_mcp_client, 
        mock_config
    ):
        """Test processing a single email via Celery task."""
        
        with patch('tasks.email_tasks.EmailProcessor') as mock_processor_class:
            
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_email.return_value = True
            
            # Call single email processing task
            result = process_single_email(sample_email_data)
            
            # Verify result
            assert result["task_created"] is True
            assert result["email_id"] == sample_email_data["id"]
            assert "task_id" in result
            
            # Verify processor was used correctly
            mock_processor.process_email.assert_called_once_with(sample_email_data)
            mock_processor.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_email_processing(
        self, 
        sample_email_data, 
        mock_mcp_client, 
        mock_config
    ):
        """Test error handling during email processing."""
        
        with patch('tasks.email_processor.mcp_manager') as mock_mcp_manager, \
             patch('tasks.email_processor.settings') as mock_settings:
            
            # Configure mock settings
            mock_settings.EMAIL_ENABLED = True
            mock_settings.EMAIL_CREATE_TASKS = True
            mock_settings.EMAIL_MAX_PER_FETCH = 50
            mock_settings.EMAIL_LABEL_FILTER = "INBOX"
            
            # Mock MCP manager to raise an error when getting tools
            async def mock_get_tools_error():
                raise Exception("Email API error")
            mock_mcp_manager.get_tools = mock_get_tools_error
            
            processor = EmailProcessor()
            
            # Should raise exception
            with pytest.raises(Exception, match="Email API error"):
                await processor.fetch_new_emails()
            
            await processor.close()
    
    @pytest.mark.asyncio
    async def test_metadata_extraction(self, sample_email_data):
        """Test email metadata extraction."""
        
        processor = EmailProcessor()
        
        metadata = processor._extract_email_metadata(sample_email_data)
        
        assert isinstance(metadata, EmailMetadata)
        assert metadata.email_id == sample_email_data["id"]
        assert metadata.thread_id == sample_email_data["threadId"]
        assert metadata.subject == "Test Email Subject"
        assert metadata.sender == "sender@example.com"
        assert metadata.recipient == "recipient@nova.dev"
        assert metadata.has_attachments is False
        assert "INBOX" in metadata.labels
        
        await processor.close()
    
    @pytest.mark.asyncio
    async def test_email_body_extraction(self, sample_email_data):
        """Test email body text extraction."""
        
        processor = EmailProcessor()
        
        body = processor._extract_email_body(sample_email_data)
        
        assert body == "Test email body content"
        
        await processor.close()
    
    @pytest.mark.asyncio
    async def test_task_description_formatting(self, sample_email_data):
        """Test task description formatting with email metadata."""
        
        processor = EmailProcessor()
        
        metadata = processor._extract_email_metadata(sample_email_data)
        body = processor._extract_email_body(sample_email_data)
        description = processor._format_task_description(metadata, body)
        
        # Check that all important information is included
        assert "**From:** sender@example.com" in description
        assert "**To:** recipient@nova.dev" in description
        assert f"**Email ID:** {sample_email_data['id']}" in description
        assert "**Email Content:**" in description
        assert "Test email body content" in description
        
        await processor.close() 