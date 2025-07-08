"""
Test Gmail Tools email ID preservation functionality.
Specifically tests that the read_email method preserves the original Gmail message ID.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from email import message_from_bytes
import base64

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.gmail_tools import GmailTools


@pytest.fixture
def mock_gmail_service():
    """Create a mock Gmail service for testing."""
    return MagicMock()


@pytest.fixture
def gmail_tools(mock_gmail_service):
    """Create GmailTools instance with mock service."""
    return GmailTools(mock_gmail_service, "test@example.com")


@pytest.mark.asyncio
async def test_read_email_preserves_original_id(gmail_tools, mock_gmail_service):
    """Test that read_email includes the original Gmail message ID in the response."""
    # Setup
    test_email_id = "18392b4c3844fed3"  # Example Gmail message ID
    
    # Create a mock email message
    test_email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test Email
Date: Wed, 08 Jul 2025 12:00:00 +0000

This is a test email content.
"""
    
    # Encode the email content as base64 (as Gmail API would return it)
    encoded_content = base64.urlsafe_b64encode(test_email_content.encode()).decode()
    
    # Mock the Gmail API response
    mock_response = {
        'id': test_email_id,
        'raw': encoded_content
    }
    
    # Setup the mock service to return our test data
    mock_gmail_service.users().messages().get().execute.return_value = mock_response
    
    # Mock the mark_email_as_read method to avoid actual API calls
    with patch.object(gmail_tools, 'mark_email_as_read', new_callable=AsyncMock) as mock_mark_read:
        # Call the method under test
        result = await gmail_tools.read_email(test_email_id)
        
        # Verify the original email ID is preserved in the result
        assert 'id' in result, "Result should include the original email ID"
        assert result['id'] == test_email_id, f"Expected ID {test_email_id}, got {result['id']}"
        
        # Verify other expected fields are present
        assert 'content' in result, "Result should include email content"
        assert 'subject' in result, "Result should include email subject"
        assert 'from' in result, "Result should include sender"
        assert 'to' in result, "Result should include recipient"
        assert 'date' in result, "Result should include date"
        
        # Verify the content is correctly decoded
        assert "This is a test email content." in result['content']
        assert result['subject'] == "Test Email"
        assert result['from'] == "sender@example.com"
        assert result['to'] == "recipient@example.com"
        
        # Verify mark_email_as_read was called with the correct ID
        mock_mark_read.assert_called_once_with(test_email_id)


@pytest.mark.asyncio
async def test_read_email_multipart_preserves_id(gmail_tools, mock_gmail_service):
    """Test that read_email preserves ID for multipart emails."""
    test_email_id = "multipart_test_id_123"
    
    # Create a multipart email
    multipart_email = """MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"
From: sender@example.com
To: recipient@example.com
Subject: Multipart Test
Date: Wed, 08 Jul 2025 12:00:00 +0000

--boundary123
Content-Type: text/plain; charset=utf-8

This is the plain text content.

--boundary123
Content-Type: text/html; charset=utf-8

<html><body>This is the HTML content.</body></html>

--boundary123--
"""
    
    encoded_content = base64.urlsafe_b64encode(multipart_email.encode()).decode()
    mock_response = {
        'id': test_email_id,
        'raw': encoded_content
    }
    
    mock_gmail_service.users().messages().get().execute.return_value = mock_response
    
    with patch.object(gmail_tools, 'mark_email_as_read', new_callable=AsyncMock):
        result = await gmail_tools.read_email(test_email_id)
        
        # Verify ID preservation for multipart emails
        assert result['id'] == test_email_id
        assert 'content' in result
        assert "This is the plain text content." in result['content']


@pytest.mark.asyncio
async def test_read_email_api_error_handling(gmail_tools, mock_gmail_service):
    """Test that read_email handles API errors gracefully."""
    from googleapiclient.errors import HttpError
    import httplib2
    
    test_email_id = "invalid_email_id"
    
    # Mock an HTTP error
    http_error = HttpError(
        resp=httplib2.Response({'status': '404'}), 
        content=b'Email not found'
    )
    mock_gmail_service.users().messages().get().execute.side_effect = http_error
    
    result = await gmail_tools.read_email(test_email_id)
    
    # Verify error response format
    assert isinstance(result, dict)
    assert result['status'] == 'error'
    assert 'error_message' in result
    assert test_email_id in result['error_message']