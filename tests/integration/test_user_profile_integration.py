"""
Integration tests for user profile API endpoints.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

from fastapi.testclient import TestClient
from models.user_profile import UserProfile


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
    
    @patch('backend.utils.redis_manager.publish')
    @patch('backend.utils.config_loader.load_user_profile')
    @patch('backend.utils.config_loader.save_user_profile')
    def test_get_user_profile(self, mock_save, mock_load, mock_publish):
        """Test GET /api/config/user-profile endpoint."""
        # Set up mocks
        mock_load.side_effect = self.mock_load
        mock_publish.return_value = AsyncMock()
        
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
    
    @patch('backend.utils.redis_manager.publish')
    @patch('backend.utils.config_loader.load_user_profile')
    @patch('backend.utils.config_loader.save_user_profile')
    def test_update_user_profile_partial(self, mock_save, mock_load, mock_publish):
        """Test PUT /api/config/user-profile with partial update."""
        # Set up mocks
        mock_load.side_effect = self.mock_load
        mock_save.side_effect = self.mock_save
        mock_publish.return_value = AsyncMock()
        
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
        mock_save.assert_called_once()
        
        # Verify Redis event was published
        mock_publish.assert_called_once()
    
    @patch('backend.utils.redis_manager.publish')
    @patch('backend.utils.config_loader.load_user_profile')
    @patch('backend.utils.config_loader.save_user_profile')
    def test_update_user_profile_full(self, mock_save, mock_load, mock_publish):
        """Test PUT /api/config/user-profile with full update."""
        # Set up mocks
        mock_load.side_effect = self.mock_load
        mock_save.side_effect = self.mock_save
        mock_publish.return_value = AsyncMock()
        
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
    
    @patch('backend.utils.redis_manager.publish')
    @patch('backend.utils.config_loader.load_user_profile')
    @patch('backend.utils.config_loader.save_user_profile')
    def test_update_user_profile_invalid_data(self, mock_save, mock_load, mock_publish):
        """Test PUT /api/config/user-profile with invalid data."""
        # Set up mocks
        mock_load.side_effect = self.mock_load
        mock_save.side_effect = self.mock_save
        mock_publish.return_value = AsyncMock()
        
        # Import and create test client
        from backend.api.config_endpoints import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Test invalid email
        response = client.put("/api/config/user-profile", json={
            "email": "invalid-email"
        })
        assert response.status_code == 422  # Validation error
        
        # Test invalid timezone
        response = client.put("/api/config/user-profile", json={
            "timezone": "Invalid/Timezone"
        })
        assert response.status_code == 422  # Validation error
        
        # Test notes too long
        response = client.put("/api/config/user-profile", json={
            "notes": "x" * 5001
        })
        assert response.status_code == 422  # Validation error
    
    @patch('backend.utils.redis_manager.publish')
    @patch('backend.utils.config_loader.load_user_profile')
    @patch('backend.utils.config_loader.save_user_profile')
    def test_api_error_handling(self, mock_save, mock_load, mock_publish):
        """Test API error handling when operations fail."""
        # Set up mocks to raise exceptions
        mock_load.side_effect = Exception("Database error")
        mock_publish.return_value = AsyncMock()
        
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
        mock_load.side_effect = self.mock_load  # Reset load mock
        mock_save.side_effect = Exception("Save error")
        
        response = client.put("/api/config/user-profile", json={
            "full_name": "Test User"
        })
        assert response.status_code == 500
        assert "Failed to update user profile" in response.json()["detail"]


class TestUserProfileEventSystem:
    """Test cases for user profile event system integration."""
    
    @patch('backend.utils.redis_manager.publish')
    def test_event_publishing_on_update(self, mock_publish):
        """Test that events are published when user profile is updated."""
        # Set up mock
        mock_publish.return_value = AsyncMock()
        
        # Import event creation function
        from backend.models.events import create_user_profile_updated_event
        
        # Test event creation
        event = create_user_profile_updated_event(
            full_name="Test User",
            email="test@example.com",
            timezone="UTC",
            notes="Test notes",
            source="test"
        )
        
        assert event.type == "user_profile_updated"
        assert event.data["full_name"] == "Test User"
        assert event.data["email"] == "test@example.com"
        assert event.data["timezone"] == "UTC"
        assert event.data["notes"] == "Test notes"
        assert event.source == "test"


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
    
    @patch('backend.utils.config_loader.load_user_profile')
    def test_prompt_rendering_with_user_context(self, mock_load):
        """Test that system prompt includes user context."""
        # Set up mock profile
        test_profile = UserProfile(
            full_name="Test User",
            email="test@example.com",
            timezone="UTC",
            notes="Test context notes"
        )
        mock_load.return_value = test_profile
        
        # Import prompt loader
        from backend.utils.prompt_loader import load_nova_system_prompt
        
        # Test prompt rendering
        prompt = load_nova_system_prompt()
        
        assert "Test User" in prompt
        assert "test@example.com" in prompt
        assert "UTC" in prompt
        assert "Test context notes" in prompt
    
    @patch('backend.utils.config_loader.load_user_profile')
    def test_prompt_rendering_without_notes(self, mock_load):
        """Test prompt rendering when user has no notes."""
        # Set up mock profile without notes
        test_profile = UserProfile(
            full_name="Test User",
            email="test@example.com",
            timezone="UTC"
        )
        mock_load.return_value = test_profile
        
        # Import prompt loader
        from backend.utils.prompt_loader import load_nova_system_prompt
        
        # Test prompt rendering
        prompt = load_nova_system_prompt()
        
        assert "Test User" in prompt
        assert "test@example.com" in prompt
        assert "UTC" in prompt
        # Should not have additional user context section
        assert "Additional User Context" not in prompt
    
    @patch('backend.utils.config_loader.load_user_profile')
    def test_prompt_rendering_with_invalid_timezone(self, mock_load):
        """Test prompt rendering gracefully handles invalid timezone."""
        # Set up mock profile with invalid timezone
        test_profile = UserProfile(
            full_name="Test User",
            email="test@example.com",
            timezone="Invalid/Timezone",  # This will cause pytz error
            notes="Test notes"
        )
        # Override validation for this test
        test_profile.__dict__['timezone'] = "Invalid/Timezone"
        mock_load.return_value = test_profile
        
        # Import prompt loader
        from backend.utils.prompt_loader import load_nova_system_prompt
        
        # Test prompt rendering (should not crash)
        prompt = load_nova_system_prompt()
        
        assert "Test User" in prompt
        assert "test@example.com" in prompt
        # Should fallback to UTC time format
        assert "UTC" in prompt


if __name__ == "__main__":
    pytest.main([__file__]) 