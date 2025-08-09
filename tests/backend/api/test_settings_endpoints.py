"""
Test settings endpoints functionality, specifically email settings event publishing.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

# Import the models and API dependencies
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "backend"))

from models.user_settings import UserSettings, UserSettingsUpdateModel
from models.events import NovaEvent, EmailSettingsUpdatedEventData


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture 
def mock_user_settings():
    """Mock user settings object."""
    from uuid import uuid4
    settings = UserSettings()
    settings.id = uuid4()
    settings.onboarding_complete = True
    settings.timezone = "UTC"
    settings.notification_preferences = {}
    settings.task_defaults = {}
    settings.agent_polling_interval = 30
    settings.agent_error_retry_interval = 300
    settings.mcp_server_preferences = {}
    settings.email_polling_enabled = True
    settings.email_polling_interval = 300
    settings.email_label_filter = "INBOX"
    settings.email_max_per_fetch = 50
    settings.email_create_tasks = True
    # Add missing required fields for UserSettingsModel validation
    settings.memory_search_limit = 10
    settings.memory_token_limit = 32000
    settings.chat_llm_model = "phi-4-Q4_K_M"
    settings.chat_llm_temperature = 0.1
    settings.chat_llm_max_tokens = 2048
    return settings


@pytest.mark.asyncio
async def test_update_email_settings_publishes_redis_event(mock_db_session, mock_user_settings):
    """Test that updating email settings publishes the correct Redis event."""
    
    # Import the update function
    from api.settings_endpoints import update_user_settings
    
    # Setup mocks - create mock result that returns our settings object
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = mock_user_settings
    mock_db_session.execute.return_value = mock_result
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock(return_value=None)  # refresh returns None
    mock_db_session.add = Mock()  # Mock add as regular method
    
    # Mock Redis event publishing
    mock_publish = AsyncMock()
    mock_publish_patch = patch('utils.redis_manager.publish', mock_publish)
    
    # Mock Celery task
    mock_celery_task = MagicMock()
    mock_celery_patch = patch('celery_app.update_beat_schedule_task', mock_celery_task)
    
    # Create update data with email settings
    update_data = UserSettingsUpdateModel(
        email_polling_interval=120,  # Changed from 300 to 120
        email_polling_enabled=True,
        email_max_per_fetch=25  # Changed from 50 to 25
    )
    
    with mock_publish_patch, mock_celery_patch:
        # Call the function
        result = await update_user_settings(update_data, mock_db_session)
        
        # Verify Redis event was published
        mock_publish.assert_called_once()
        
        # Get the published event
        published_event_call = mock_publish.call_args[0][0]
        assert isinstance(published_event_call, NovaEvent)
        assert published_event_call.type == "email_settings_updated"
        assert published_event_call.source == "settings-api"
        
        # Verify event data
        event_data = EmailSettingsUpdatedEventData.model_validate(published_event_call.data)
        assert event_data.enabled == True
        assert event_data.polling_interval_minutes == 120
        assert event_data.max_emails_per_fetch == 25
        assert event_data.email_label_filter == "INBOX"
        assert event_data.create_tasks_from_emails == True
        
        # Verify Celery task was also triggered as fallback
        mock_celery_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_update_non_email_settings_no_redis_event(mock_db_session, mock_user_settings):
    """Test that updating non-email settings doesn't publish Redis events."""
    
    from api.settings_endpoints import update_user_settings
    
    # Setup mocks - create mock result that returns our settings object
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = mock_user_settings
    mock_db_session.execute.return_value = mock_result
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock(return_value=None)  # refresh returns None
    mock_db_session.add = Mock()  # Mock add as regular method
    
    # Mock Redis event publishing
    mock_publish = AsyncMock()
    mock_publish_patch = patch('utils.redis_manager.publish', mock_publish)
    
    # Create update data with non-email settings only
    update_data = UserSettingsUpdateModel(
        full_name="Test User",
        timezone="UTC"
    )
    
    with mock_publish_patch:
        # Call the function
        result = await update_user_settings(update_data, mock_db_session)
        
        # Verify NO Redis event was published
        mock_publish.assert_not_called()


@pytest.mark.asyncio 
async def test_email_settings_event_creation():
    """Test the email settings event creation helper function."""
    
    from models.events import create_email_settings_updated_event
    
    # Create an event
    event = create_email_settings_updated_event(
        enabled=True,
        polling_interval_minutes=180,
        email_label_filter="UNREAD",
        max_emails_per_fetch=75,
        create_tasks_from_emails=False,
        source="test-service"
    )
    
    # Verify event structure
    assert event.type == "email_settings_updated"
    assert event.source == "test-service"
    assert isinstance(event.data, dict)
    
    # Verify event data
    event_data = EmailSettingsUpdatedEventData.model_validate(event.data)
    assert event_data.enabled == True
    assert event_data.polling_interval_minutes == 180
    assert event_data.email_label_filter == "UNREAD"
    assert event_data.max_emails_per_fetch == 75
    assert event_data.create_tasks_from_emails == False


@pytest.mark.asyncio
async def test_redis_event_publishing_error_handling(mock_db_session, mock_user_settings):
    """Test that Redis event publishing errors don't break the settings update."""
    
    from api.settings_endpoints import update_user_settings
    
    # Setup mocks - create mock result that returns our settings object
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = mock_user_settings
    mock_db_session.execute.return_value = mock_result
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock(return_value=None)  # refresh returns None
    mock_db_session.add = Mock()  # Mock add as regular method
    
    # Mock Redis event publishing to raise an error
    mock_publish = AsyncMock()
    mock_publish.side_effect = Exception("Redis connection failed")
    mock_publish_patch = patch('utils.redis_manager.publish', mock_publish)
    
    # Mock Celery task
    mock_celery_task = MagicMock()
    mock_celery_patch = patch('celery_app.update_beat_schedule_task', mock_celery_task)
    
    # Create update data with email settings
    update_data = UserSettingsUpdateModel(
        email_polling_interval=60
    )
    
    with mock_publish_patch, mock_celery_patch:
        # Call the function - should not raise an exception
        result = await update_user_settings(update_data, mock_db_session)
        
        # Verify the settings update still succeeded
        assert result is not None
        assert result.email_polling_interval == 60
        
        # Verify Redis publish was attempted but failed
        mock_publish.assert_called_once()