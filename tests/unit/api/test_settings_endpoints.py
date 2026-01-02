"""
Test settings endpoints functionality.
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
    # Add missing required fields for UserSettingsModel validation
    settings.memory_search_limit = 10
    settings.memory_token_limit = 32000
    settings.chat_llm_model = "phi-4-Q4_K_M"
    settings.chat_llm_temperature = 0.1
    settings.chat_llm_max_tokens = 2048
    # Add memory LLM settings
    settings.memory_llm_model = "qwen3-32b"
    settings.memory_small_llm_model = "qwen3-32b"
    settings.memory_llm_temperature = 0.1
    settings.memory_llm_max_tokens = 2048
    # Add embedding model
    settings.embedding_model = "qwen3-embedding-4b"
    # Add LiteLLM settings
    settings.litellm_base_url = "http://localhost:4000"
    # Add api key validation status
    settings.api_key_validation_status = {}
    return settings


@pytest.mark.asyncio
async def test_update_user_settings_basic(mock_db_session, mock_user_settings):
    """Test that updating user settings works correctly."""
    
    from api.settings_endpoints import update_user_settings
    
    # Setup mocks - create mock result that returns our settings object
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = mock_user_settings
    mock_db_session.execute.return_value = mock_result
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock(return_value=None)  # refresh returns None
    mock_db_session.add = Mock()  # Mock add as regular method
    
    # Create update data with basic settings
    update_data = UserSettingsUpdateModel(
        full_name="Test User",
        timezone="UTC"
    )
    
    # Call the function
    result = await update_user_settings(update_data, mock_db_session)
    
    # Verify result is returned
    assert result is not None


@pytest.mark.asyncio
async def test_llm_settings_update(mock_db_session, mock_user_settings):
    """Test that updating LLM settings works correctly."""
    
    from api.settings_endpoints import update_user_settings
    
    # Setup mocks - create mock result that returns our settings object
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = mock_user_settings
    mock_db_session.execute.return_value = mock_result
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock(return_value=None)  # refresh returns None
    mock_db_session.add = Mock()  # Mock add as regular method
    
    # Create update data with LLM settings
    update_data = UserSettingsUpdateModel(
        chat_llm_model="phi-4-Q4_K_M",
        chat_llm_temperature=0.8
    )
    
    # Call the function - should not raise an exception
    result = await update_user_settings(update_data, mock_db_session)
    
    # Verify the settings update succeeded
    assert result is not None
    assert result.chat_llm_model == "phi-4-Q4_K_M"
    assert result.chat_llm_temperature == 0.8


@pytest.mark.asyncio
async def test_memory_settings_update(mock_db_session, mock_user_settings):
    """Test that updating memory settings works correctly."""
    
    from api.settings_endpoints import update_user_settings
    
    # Setup mocks - create mock result that returns our settings object
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = mock_user_settings
    mock_db_session.execute.return_value = mock_result
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock(return_value=None)  # refresh returns None
    mock_db_session.add = Mock()  # Mock add as regular method
    
    # Create update data with memory settings
    update_data = UserSettingsUpdateModel(
        memory_search_limit=15,
        memory_token_limit=16000
    )
    
    # Call the function
    result = await update_user_settings(update_data, mock_db_session)
    
    # Verify the settings update succeeded
    assert result is not None
    assert result.memory_search_limit == 15
    assert result.memory_token_limit == 16000