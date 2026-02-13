"""
Test that Gmail tool parameter names match the cross-server convention.

NOV-118: The google-workspace MCP server used 'recipient_ids' and 'message'
while ms_graph and outlook-mac use 'recipients' and 'body'. The LLM naturally
sends the latter, causing validation errors.

These tests verify that GmailTools.create_draft and send_email accept
'recipients' and 'body' parameters, consistent with the other MCP servers.
"""
import pytest
import base64
from email import message_from_bytes
from unittest.mock import MagicMock, AsyncMock

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.gmail_tools import GmailTools


@pytest.fixture
def mock_gmail_service():
    """Create a mock Gmail service."""
    return MagicMock()


@pytest.fixture
def gmail_tools(mock_gmail_service):
    """Create GmailTools instance with mock service."""
    return GmailTools(mock_gmail_service, "test@example.com")


def decode_email_from_raw(raw_b64: str):
    """Decode a base64-encoded email message."""
    return message_from_bytes(base64.urlsafe_b64decode(raw_b64))


class TestCreateDraftParameterNames:
    """Verify create_draft accepts 'recipients' and 'body' parameter names."""

    @pytest.mark.asyncio
    async def test_create_draft_accepts_recipients_and_body(self, gmail_tools, mock_gmail_service):
        """create_draft must accept 'recipients' (list) and 'body' (str) parameters."""
        mock_gmail_service.users().drafts().create().execute.return_value = {'id': 'draft_123'}

        result = await gmail_tools.create_draft(
            recipients=["user@example.com"],
            subject="Test Draft",
            body="Draft body content"
        )

        assert result == {"draft_id": "draft_123"}

    @pytest.mark.asyncio
    async def test_create_draft_multiple_recipients(self, gmail_tools, mock_gmail_service):
        """create_draft with multiple recipients builds correct To header."""
        mock_gmail_service.users().drafts().create().execute.return_value = {'id': 'draft_456'}

        result = await gmail_tools.create_draft(
            recipients=["a@example.com", "b@example.com"],
            subject="Multi-recipient",
            body="Hello all"
        )

        assert result == {"draft_id": "draft_456"}

        # Verify the email was constructed with both recipients in To header
        create_call = mock_gmail_service.users().drafts().create
        call_kwargs = create_call.call_args
        raw_message = call_kwargs.kwargs['body']['message']['raw']
        email_msg = decode_email_from_raw(raw_message)
        assert "a@example.com" in email_msg['To']
        assert "b@example.com" in email_msg['To']

    @pytest.mark.asyncio
    async def test_create_draft_body_content(self, gmail_tools, mock_gmail_service):
        """create_draft 'body' parameter becomes the email message content."""
        mock_gmail_service.users().drafts().create().execute.return_value = {'id': 'draft_789'}

        await gmail_tools.create_draft(
            recipients=["user@example.com"],
            subject="Content Test",
            body="This is the email body text"
        )

        create_call = mock_gmail_service.users().drafts().create
        call_kwargs = create_call.call_args
        raw_message = call_kwargs.kwargs['body']['message']['raw']
        email_msg = decode_email_from_raw(raw_message)
        assert "This is the email body text" in email_msg.get_payload()


class TestSendEmailParameterNames:
    """Verify send_email accepts 'recipients' and 'body' parameter names."""

    @pytest.mark.asyncio
    async def test_send_email_accepts_recipients_and_body(self, gmail_tools, mock_gmail_service):
        """send_email must accept 'recipients' (list) and 'body' (str) parameters."""
        mock_gmail_service.users().messages().send().execute.return_value = {'id': 'msg_123'}

        result = await gmail_tools.send_email(
            recipients=["user@example.com"],
            subject="Test Send",
            body="Email body content"
        )

        assert result == {"message_id": "msg_123"}

    @pytest.mark.asyncio
    async def test_send_email_multiple_recipients(self, gmail_tools, mock_gmail_service):
        """send_email with multiple recipients builds correct To header."""
        mock_gmail_service.users().messages().send().execute.return_value = {'id': 'msg_456'}

        result = await gmail_tools.send_email(
            recipients=["a@example.com", "b@example.com"],
            subject="Multi-recipient",
            body="Hello all"
        )

        assert result == {"message_id": "msg_456"}

        send_call = mock_gmail_service.users().messages().send
        call_kwargs = send_call.call_args
        raw_message = call_kwargs.kwargs['body']['raw']
        email_msg = decode_email_from_raw(raw_message)
        assert "a@example.com" in email_msg['To']
        assert "b@example.com" in email_msg['To']
