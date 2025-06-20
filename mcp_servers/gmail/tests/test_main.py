import pytest
import asyncio
import base64
from email import message_from_bytes
from unittest.mock import patch, MagicMock, mock_open

from googleapiclient.errors import HttpError
import httplib2 # Required for HttpError constructor

# Import GmailService from the local main module
from main import GmailService
from google.oauth2.credentials import Credentials # For spec in mock

# Helper function to decode email from mock send() call
def get_email_message_from_send_call(mock_send_method):
    called_with_kwargs = mock_send_method.call_args.kwargs
    assert 'body' in called_with_kwargs, "Method was called without a 'body' kwarg for send"
    assert 'raw' in called_with_kwargs['body'], "Body kwarg for send does not contain 'raw' field"

    raw_body = called_with_kwargs['body']['raw']
    decoded_message_bytes = base64.urlsafe_b64decode(raw_body)
    return message_from_bytes(decoded_message_bytes)

# Helper function to decode email from mock drafts().create() call
def get_email_message_from_draft_create_call(mock_draft_create_method):
    called_with_kwargs = mock_draft_create_method.call_args.kwargs
    assert 'body' in called_with_kwargs, "Method was called without a 'body' kwarg for draft create"
    assert 'message' in called_with_kwargs['body'], "Body kwarg for draft create does not contain 'message' field"
    assert 'raw' in called_with_kwargs['body']['message'], "Body['message'] for draft create does not contain 'raw' field"

    raw_body = called_with_kwargs['body']['message']['raw']
    decoded_message_bytes = base64.urlsafe_b64decode(raw_body)
    return message_from_bytes(decoded_message_bytes)

@pytest.fixture
def mock_gmail_service_dependencies():
    """Mocks dependencies for GmailService initialization and core API interaction."""
    # Mock file system and auth flow
    mock_os_path_exists = patch('os.path.exists').start()
    mock_creds_from_file = patch('google.oauth2.credentials.Credentials.from_authorized_user_file').start()
    mock_flow_from_secrets = patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file').start()

    # Configure a mock service instance directly
    mock_service_instance = MagicMock()
    # Patch GmailService._get_service to return this mock_service_instance
    # Note: The path to GmailService must be correct for patch.object
    mock_get_service = patch('main.GmailService._get_service', return_value=mock_service_instance).start()

    mock_users_method = MagicMock()

    # For messages().send()
    mock_messages_method = MagicMock() # Also used for messages().trash()
    mock_send_method = MagicMock()
    mock_messages_method.send.return_value = mock_send_method

    # For drafts().create()
    mock_drafts_method = MagicMock()
    mock_draft_create_method = MagicMock()
    mock_drafts_method.create.return_value = mock_draft_create_method

    # For labels().create()
    mock_labels_method = MagicMock()
    mock_labels_create_method = MagicMock()
    mock_labels_method.create.return_value = mock_labels_create_method

    # For messages().trash()
    mock_messages_trash_method = MagicMock()
    mock_messages_method.trash.return_value = mock_messages_trash_method # trash is part of messages

    mock_service_instance.users.return_value = mock_users_method
    mock_users_method.messages.return_value = mock_messages_method
    mock_users_method.drafts.return_value = mock_drafts_method
    mock_users_method.labels.return_value = mock_labels_method # Add labels to users

    # mock_build is no longer needed as we patch _get_service
    # mock_build.return_value = mock_service_instance

    # Mock _get_user_email to avoid another API call during init
    # This is still needed as _get_user_email is called in __init__
    mock_get_user_email = patch.object(GmailService, '_get_user_email', return_value='testuser@example.com').start()

    # Mock token file writing
    mock_file_write = patch('builtins.open', mock_open()).start()

    yield {
        "mock_os_path_exists": mock_os_path_exists,
        "mock_creds_from_file": mock_creds_from_file,
        "mock_flow_from_secrets": mock_flow_from_secrets,
        "mock_get_service": mock_get_service, # Yield the _get_service mock
        "mock_service_instance": mock_service_instance,
        "mock_send_method": mock_send_method,
        "mock_draft_create_method": mock_draft_create_method,
        "mock_labels_create_method": mock_labels_create_method,
        "mock_messages_trash_method": mock_messages_trash_method,
        "mock_get_user_email": mock_get_user_email,
        "mock_file_write": mock_file_write
    }

    # Stop all patches
    patch.stopall()


@pytest.mark.asyncio
async def test_send_email_single_recipient_success(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds

    # mock_send_method is the object with .execute()
    mock_gmail_service_dependencies["mock_send_method"].execute.return_value = {'id': 'test_message_id'}

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    message_content = "Hello, this is a test."
    result = await service.send_email(recipient_ids=["test@example.com"], subject="Test Subject", message=message_content)

    mock_gmail_service_dependencies["mock_send_method"].execute.assert_called_once()
    # To check args passed to send(), we need to check the mock for send() itself
    mock_gmail_service_dependencies["mock_service_instance"].users().messages().send.assert_called_once()
    email_message_obj = get_email_message_from_send_call(mock_gmail_service_dependencies["mock_service_instance"].users().messages().send)
    assert email_message_obj['To'] == "test@example.com"
    assert email_message_obj.get_payload().strip() == message_content.strip() # Fixed Assertion
    assert result == {"message_id": "test_message_id"}

@pytest.mark.asyncio
async def test_send_email_multiple_recipients_success(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds
    mock_gmail_service_dependencies["mock_send_method"].execute.return_value = {'id': 'test_message_id_multi'}

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    recipients = ["test1@example.com", "test2@example.com", "test3@example.com"]
    message_content = "This is a test for multiple recipients."
    result = await service.send_email(recipient_ids=recipients, subject="Multi-Recipient Test", message=message_content)

    mock_gmail_service_dependencies["mock_send_method"].execute.assert_called_once()
    mock_gmail_service_dependencies["mock_service_instance"].users().messages().send.assert_called_once()
    email_message_obj = get_email_message_from_send_call(mock_gmail_service_dependencies["mock_service_instance"].users().messages().send)
    assert email_message_obj['To'] == "test1@example.com, test2@example.com, test3@example.com"
    assert email_message_obj.get_payload().strip() == message_content.strip() # Fixed Assertion
    assert result == {"message_id": "test_message_id_multi"}

@pytest.mark.asyncio
async def test_send_email_api_error(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds
    http_error = HttpError(resp=httplib2.Response({'status': '400'}), content=b'Bad Request Content for send')
    mock_gmail_service_dependencies["mock_send_method"].execute.side_effect = http_error

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    message_content = "This email should cause a send error."
    result = await service.send_email(recipient_ids=["error@example.com"], subject="Error Test Send", message=message_content)

    mock_gmail_service_dependencies["mock_send_method"].execute.assert_called_once()
    expected_error_message = str(http_error)
    assert result == {"status": "error", "error_message": expected_error_message}

# --- Tests for create_draft ---

@pytest.mark.asyncio
async def test_create_draft_single_recipient_success(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds
    mock_gmail_service_dependencies["mock_draft_create_method"].execute.return_value = {'id': 'test_draft_id'}

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    message_content = "Hello, this is a draft."
    result = await service.create_draft(recipient_ids=["draft@example.com"], subject="Draft Subject", message=message_content)

    mock_gmail_service_dependencies["mock_draft_create_method"].execute.assert_called_once()
    mock_gmail_service_dependencies["mock_service_instance"].users().drafts().create.assert_called_once()
    email_message_obj = get_email_message_from_draft_create_call(mock_gmail_service_dependencies["mock_service_instance"].users().drafts().create)
    assert email_message_obj['To'] == "draft@example.com"
    assert email_message_obj.get_payload().strip() == message_content.strip() # Fixed Assertion
    assert result == {"draft_id": "test_draft_id"}

@pytest.mark.asyncio
async def test_create_draft_multiple_recipients_success(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds
    mock_gmail_service_dependencies["mock_draft_create_method"].execute.return_value = {'id': 'test_draft_id_multi'}

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    recipients = ["draft1@example.com", "draft2@example.com"]
    message_content = "This is a draft for multiple recipients."
    result = await service.create_draft(recipient_ids=recipients, subject="Multi-Recipient Draft", message=message_content)

    mock_gmail_service_dependencies["mock_draft_create_method"].execute.assert_called_once()
    mock_gmail_service_dependencies["mock_service_instance"].users().drafts().create.assert_called_once()
    email_message_obj = get_email_message_from_draft_create_call(mock_gmail_service_dependencies["mock_service_instance"].users().drafts().create)
    assert email_message_obj['To'] == "draft1@example.com, draft2@example.com"
    assert email_message_obj.get_payload().strip() == message_content.strip() # Fixed Assertion
    assert result == {"draft_id": "test_draft_id_multi"}

@pytest.mark.asyncio
async def test_create_draft_api_error(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds
    http_error = HttpError(resp=httplib2.Response({'status': '500'}), content=b'Internal Server Error for draft')
    mock_gmail_service_dependencies["mock_draft_create_method"].execute.side_effect = http_error

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    message_content = "This draft should cause an API error."
    result = await service.create_draft(recipient_ids=["error_draft@example.com"], subject="Error Draft Test", message=message_content)

    mock_gmail_service_dependencies["mock_draft_create_method"].execute.assert_called_once()
    expected_error_message = str(http_error)
    assert result == {"status": "error", "error_message": expected_error_message}

# --- Tests for create_label ---

@pytest.mark.asyncio
async def test_create_label_success(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds

    mock_gmail_service_dependencies["mock_labels_create_method"].execute.return_value = {'id': 'test_label_id', 'name': 'NewLabelName'}

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    label_name = "NewLabelName"
    result = await service.create_label(name=label_name)

    mock_gmail_service_dependencies["mock_labels_create_method"].execute.assert_called_once()
    # Check args of the create call itself
    mock_gmail_service_dependencies["mock_service_instance"].users().labels().create.assert_called_once_with(
        userId="me",
        body={'name': label_name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
    )
    assert result == {'label_id': 'test_label_id', 'name': 'NewLabelName'}

@pytest.mark.asyncio
async def test_create_label_api_error(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds

    http_error = HttpError(resp=httplib2.Response({'status': '403'}), content=b'Forbidden to create label')
    mock_gmail_service_dependencies["mock_labels_create_method"].execute.side_effect = http_error

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    result = await service.create_label(name="FailedLabel")

    mock_gmail_service_dependencies["mock_labels_create_method"].execute.assert_called_once()
    expected_error_message = str(http_error)
    assert result == {"status": "error", "error_message": expected_error_message}

# --- Tests for trash_email ---

@pytest.mark.asyncio
async def test_trash_email_success(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds

    # The actual return from execute() for trash doesn't matter for the success string
    mock_gmail_service_dependencies["mock_messages_trash_method"].execute.return_value = {}

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    email_id_to_trash = "email123"
    result = await service.trash_email(email_id=email_id_to_trash)

    mock_gmail_service_dependencies["mock_messages_trash_method"].execute.assert_called_once()
    # Check args of the trash call itself
    mock_gmail_service_dependencies["mock_service_instance"].users().messages().trash.assert_called_once_with(userId="me", id=email_id_to_trash)
    assert result == "Email moved to trash successfully."

@pytest.mark.asyncio
async def test_trash_email_api_error(mock_gmail_service_dependencies):
    mock_gmail_service_dependencies["mock_os_path_exists"].return_value = True
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.token = "mock_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.universe_domain = "googleapis.com"
    mock_creds.has_scopes.return_value = True
    mock_creds.refresh.return_value = None
    mock_gmail_service_dependencies["mock_creds_from_file"].return_value = mock_creds

    http_error = HttpError(resp=httplib2.Response({'status': '404'}), content=b'Email not found')
    mock_gmail_service_dependencies["mock_messages_trash_method"].execute.side_effect = http_error

    service = GmailService(creds_file_path="dummy_creds.json", token_path="dummy_token.json")
    email_id_to_trash = "nonexistent_email"
    result = await service.trash_email(email_id=email_id_to_trash)

    mock_gmail_service_dependencies["mock_messages_trash_method"].execute.assert_called_once()
    expected_error_message = f"An HttpError occurred trashing email {email_id_to_trash}: {str(http_error)}"
    assert result == {"status": "error", "error_message": expected_error_message}
