"""
Integration tests for user profile API endpoints.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

from fastapi.testclient import TestClient
from models.user_profile import UserProfile
from models.user_settings import UserSettings


# Mock the user profile functions to use temporary files
def create_mock_user_profile_functions():
    """Create mock functions that use temporary files for testing."""
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / "user_profile.yaml"
    
    def mock_load_user_profile():
        if not temp_path.exists():
            # Create default profile
            import yaml
            from datetime import datetime
            default_data = {
                "full_name": "Nova User",
                "email": "user@example.com", 
                "timezone": "UTC",
                "notes": "Add your personal context here.",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'w') as f:
                yaml.safe_dump(default_data, f)
            return UserProfile(**default_data)
        
        import yaml
        with open(temp_path, 'r') as f:
            data = yaml.safe_load(f)
        return UserProfile(**data)
    
    def mock_save_user_profile(profile):
        import yaml
        from datetime import datetime
        profile.updated_at = datetime.now()
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_path, 'w') as f:
            yaml.safe_dump(profile.dict(), f)
    
    return mock_load_user_profile, mock_save_user_profile, temp_path


class TestUserProfileAPI:
    """Test cases for user profile API endpoints."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        self.mock_load, self.mock_save, self.temp_path = create_mock_user_profile_functions()
    
    def teardown_method(self):
        """Clean up after each test."""
        if self.temp_path.exists():
            self.temp_path.unlink()
        if self.temp_path.parent.exists():
            self.temp_path.parent.rmdir()
    
    @patch('backend.api.config_endpoints.config_registry.get_manager')
    def test_get_user_profile(self, mock_get_manager):
        """Test GET /api/config/user-profile endpoint."""
        # Set up mock manager
        mock_manager = MagicMock()
        mock_manager.get_config.return_value = self.mock_load()
        mock_get_manager.return_value = mock_manager
        
        # Import and create test client
        from backend.api.config_endpoints import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Test getting user profile
        response = client.get("/api/config/user-profile")
        assert response.status_code == 200
        
        data = response.json()
        assert data["full_name"] == "Nova User"
        assert data["email"] == "user@example.com"
        assert data["timezone"] == "UTC"
        assert "created_at" in data
        assert "updated_at" in data
    
    @pytest.mark.asyncio
    @patch('backend.api.config_endpoints.publish', new_callable=AsyncMock)
    @patch('backend.api.config_endpoints.config_registry.get_manager')
    async def test_update_user_profile_partial(self, mock_get_manager, mock_publish):
        """Test PUT /api/config/user-profile with partial update."""
        # Set up mock manager
        mock_manager = MagicMock()
        mock_manager.get_config.return_value = self.mock_load()
        mock_manager.save_config.side_effect = self.mock_save
        mock_get_manager.return_value = mock_manager

        # Import and create test client
        from backend.api.config_endpoints import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Test partial update
        update_data = {
            "full_name": "Updated User",
            "timezone": "America/New_York"
        }
        
        response = client.put("/api/config/user-profile", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["full_name"] == "Updated User"
        assert data["timezone"] == "America/New_York"
        assert data["email"] == "user@example.com"  # Should remain unchanged
        
        # Verify save was called
        mock_manager.save_config.assert_called_once()
        
        # Verify Redis event was published
        await asyncio.sleep(0) # allow other tasks to run
        mock_publish.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.api.config_endpoints.publish', new_callable=AsyncMock)
    @patch('backend.api.config_endpoints.config_registry.get_manager')
    async def test_update_user_profile_full(self, mock_get_manager, mock_publish):
        """Test PUT /api/config/user-profile with full update."""
        # Set up mock manager
        mock_manager = MagicMock()
        mock_manager.get_config.return_value = self.mock_load()
        mock_manager.save_config.side_effect = self.mock_save
        mock_get_manager.return_value = mock_manager

        # Import and create test client
        from backend.api.config_endpoints import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Test full update
        update_data = {
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "timezone": "Europe/London",
            "notes": "Mathematician and first computer programmer."
        }
        
        response = client.put("/api/config/user-profile", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["full_name"] == "Ada Lovelace"
        assert data["email"] == "ada@example.com"
        assert data["timezone"] == "Europe/London"
        assert data["notes"] == "Mathematician and first computer programmer."

    @patch('backend.api.config_endpoints.config_registry.get_manager')
    def test_update_user_profile_invalid_data(self, mock_get_manager):
        """Test PUT /api/config/user-profile with invalid data."""
        # Set up mock manager
        mock_manager = MagicMock()
        mock_manager.get_config.return_value = self.mock_load()
        mock_manager.save_config.side_effect = self.mock_save
        mock_get_manager.return_value = mock_manager

        # Import and create test client
        from backend.api.config_endpoints import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Test invalid email
        response = client.put("/api/config/user-profile", json={"email": "invalid-email"})
        assert response.status_code == 422
        
        # Test invalid timezone
        response = client.put("/api/config/user-profile", json={"timezone": "Invalid/Timezone"})
        assert response.status_code == 422
        
        # Test notes too long
        response = client.put("/api/config/user-profile", json={"notes": "x" * 5001})
        assert response.status_code == 422
    
    @patch('backend.api.config_endpoints.config_registry.get_manager')
    def test_api_error_handling(self, mock_get_manager):
        """Test API error handling when operations fail."""
        # Set up mocks to raise exceptions
        mock_manager = MagicMock()
        mock_manager.get_config.side_effect = Exception("Database error")
        mock_get_manager.return_value = mock_manager

        # Import and create test client
        from backend.api.config_endpoints import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Test GET with error
        response = client.get("/api/config/user-profile")
        assert response.status_code == 500
        assert "Failed to retrieve user profile" in response.json()["detail"]
        
        # Test PUT with save error
        mock_manager.get_config.side_effect = self.mock_load  # Reset load mock
        mock_manager.save_config.side_effect = Exception("Save error")
        
        response = client.put("/api/config/user-profile", json={"full_name": "Test User"})
        assert response.status_code == 500
        assert "Failed to update user profile" in response.json()["detail"]


class TestUserProfileEventSystem:
    """Test cases for user profile event system integration."""
    
    def test_event_publishing_on_update(self):
        """Test that events are published when user profile is updated."""
        from backend.models.events import create_user_profile_updated_event
        
        event = create_user_profile_updated_event(
            full_name="Test User",
            email="test@example.com",
            timezone="UTC",
            notes="Test notes",
            source="test"
        )
        
        assert event.type == "user_profile_updated"
        assert event.data["full_name"] == "Test User"


class TestUserProfilePromptIntegration:
    """Test cases for user profile integration with system prompt."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_load, self.mock_save, self.temp_path = create_mock_user_profile_functions()
    
    def teardown_method(self):
        """Clean up after each test."""
        if self.temp_path.exists():
            self.temp_path.unlink()
        if self.temp_path.parent.exists():
            self.temp_path.parent.rmdir()
    
    @pytest.mark.asyncio
    @patch('backend.utils.prompt_loader.db_manager.get_session')
    @patch('backend.utils.prompt_loader.config_registry.get_manager')
    async def test_prompt_rendering_with_user_context(self, mock_get_manager, mock_get_session):
        """Test that system prompt includes user context."""
        # Set up mock profile
        profile_data = self.mock_load()
        test_profile = UserSettings(
            id=1,
            full_name=profile_data.full_name,
            email=profile_data.email,
            timezone=profile_data.timezone,
            notes="Test context notes"
        )

        # Mock DB session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_profile
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_get_session.return_value.__aenter__.return_value = mock_session

        # Mock prompt manager
        mock_prompt_manager = MagicMock()
        def process_config_side_effect(**kwargs):
            return f"Prompt with {kwargs['user_full_name']} and {kwargs['user_notes_section']}"
        mock_prompt_manager.get_processed_config.side_effect = process_config_side_effect
        mock_get_manager.return_value = mock_prompt_manager
        
        from backend.utils.prompt_loader import load_nova_system_prompt
        
        prompt = await load_nova_system_prompt()
        
        assert "Nova User" in prompt
        assert "Test context notes" in prompt
    
    @pytest.mark.asyncio
    @patch('backend.utils.prompt_loader.db_manager.get_session')
    @patch('backend.utils.prompt_loader.config_registry.get_manager')
    async def test_prompt_rendering_without_notes(self, mock_get_manager, mock_get_session):
        """Test prompt rendering when user has no notes."""
        profile_data = self.mock_load()
        test_profile = UserSettings(
            id=1,
            full_name=profile_data.full_name,
            email=profile_data.email,
            timezone=profile_data.timezone,
            notes=None
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_profile
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_get_session.return_value.__aenter__.return_value = mock_session

        mock_prompt_manager = MagicMock()
        def process_config_side_effect(**kwargs):
            if kwargs.get('user_notes_section'):
                return f"Prompt with notes: {kwargs['user_notes_section']}"
            return f"Prompt for {kwargs['user_full_name']}"
        mock_prompt_manager.get_processed_config.side_effect = process_config_side_effect
        mock_get_manager.return_value = mock_prompt_manager
        
        from backend.utils.prompt_loader import load_nova_system_prompt
        
        prompt = await load_nova_system_prompt()
        
        assert "Prompt for Nova User" in prompt
        assert "with notes" not in prompt
    
    @pytest.mark.asyncio
    @patch('backend.utils.prompt_loader.db_manager.get_session')
    @patch('backend.utils.prompt_loader.config_registry.get_manager')
    async def test_prompt_rendering_with_invalid_timezone(self, mock_get_manager, mock_get_session):
        """Test prompt rendering gracefully handles invalid timezone."""
        profile_data = self.mock_load()
        test_profile = UserSettings(
            id=1,
            full_name=profile_data.full_name,
            email=profile_data.email,
            timezone="Invalid/Timezone",
            notes="Test notes"
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_profile
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_get_session.return_value.__aenter__.return_value = mock_session

        mock_prompt_manager = MagicMock()
        def process_config_side_effect(**kwargs):
            return f"Timezone: {kwargs['user_timezone']}, Time: {kwargs['current_time_user_tz']}"
        mock_prompt_manager.get_processed_config.side_effect = process_config_side_effect
        mock_get_manager.return_value = mock_prompt_manager
        
        from backend.utils.prompt_loader import load_nova_system_prompt
        
        prompt = await load_nova_system_prompt()
        
        assert "Timezone: Invalid/Timezone" in prompt
        assert "UTC" in prompt
