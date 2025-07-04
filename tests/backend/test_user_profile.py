"""
Unit tests for user profile models and configuration management.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from datetime import datetime

import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

from models.user_profile import UserProfile, UserProfileUpdate
from utils.config_registry import get_config, save_config


class TestUserProfile:
    """Test cases for UserProfile model."""
    
    def test_user_profile_creation(self):
        """Test user profile model creation with valid data."""
        profile = UserProfile(
            full_name="Test User",
            email="test@example.com",
            timezone="UTC"
        )
        assert profile.full_name == "Test User"
        assert profile.email == "test@example.com"
        assert profile.timezone == "UTC"
        assert profile.notes is None
        assert isinstance(profile.created_at, datetime)
        assert isinstance(profile.updated_at, datetime)
    
    def test_user_profile_with_notes(self):
        """Test user profile creation with notes."""
        notes = "Prefers concise updates.\nEnjoys technical discussions."
        profile = UserProfile(
            full_name="Ada Lovelace",
            email="ada@example.com",
            timezone="Europe/London",
            notes=notes
        )
        assert profile.notes == notes
    
    def test_invalid_email(self):
        """Test validation of invalid email address."""
        with pytest.raises(ValueError):
            UserProfile(
                full_name="Test User",
                email="invalid-email",
                timezone="UTC"
            )
    
    def test_invalid_timezone(self):
        """Test validation of invalid timezone."""
        with pytest.raises(ValueError):
            UserProfile(
                full_name="Test User",
                email="test@example.com",
                timezone="Invalid/Timezone"
            )
    
    def test_notes_length_validation(self):
        """Test notes length validation."""
        with pytest.raises(ValueError):
            UserProfile(
                full_name="Test User",
                email="test@example.com",
                timezone="UTC",
                notes="x" * 5001  # Exceed limit
            )
    
    def test_valid_timezones(self):
        """Test that common valid timezones are accepted."""
        valid_timezones = [
            "UTC",
            "America/New_York",
            "Europe/London",
            "Asia/Tokyo",
            "Australia/Sydney"
        ]
        
        for tz in valid_timezones:
            profile = UserProfile(
                full_name="Test User",
                email="test@example.com",
                timezone=tz
            )
            assert profile.timezone == tz


class TestUserProfileUpdate:
    """Test cases for UserProfileUpdate model."""
    
    def test_partial_update(self):
        """Test partial update with only some fields."""
        update = UserProfileUpdate(
            full_name="Updated Name",
            timezone="America/New_York"
        )
        assert update.full_name == "Updated Name"
        assert update.timezone == "America/New_York"
        assert update.email is None
        assert update.notes is None
    
    def test_empty_update(self):
        """Test empty update object."""
        update = UserProfileUpdate()
        assert update.full_name is None
        assert update.email is None
        assert update.timezone is None
        assert update.notes is None
    
    def test_timezone_validation_in_update(self):
        """Test timezone validation in update model."""
        with pytest.raises(ValueError):
            UserProfileUpdate(timezone="Invalid/Timezone")
    
    def test_notes_validation_in_update(self):
        """Test notes validation in update model."""
        with pytest.raises(ValueError):
            UserProfileUpdate(notes="x" * 5001)


class TestConfigManager:
    """Test cases for user profile configuration management using unified system."""
    
    def test_load_default_profile(self):
        """Test loading default profile when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            from utils.yaml_config_manager import YamlConfigManager
            
            temp_path = Path(temp_dir) / "user_profile.yaml"
            
            # Create a default profile
            default_profile = UserProfile(
                full_name="Nova User",
                email="user@example.com",
                timezone="UTC",
                notes="Add your personal context here."
            )
            
            # Create config manager with default
            config_manager = YamlConfigManager(
                config_path=temp_path,
                config_name="test_user_profile",
                config_model=UserProfile,
                default_config=default_profile
            )
            
            # Test loading default profile (should create file and return default)
            profile = config_manager.get_config()
            
            assert profile.full_name == "Nova User"
            assert profile.email == "user@example.com"
            assert profile.timezone == "UTC"
            assert "Add your personal context here" in profile.notes
            assert temp_path.exists()  # File should be created
    
    def test_save_and_load_profile(self):
        """Test saving and loading user profile."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "user_profile.yaml"
            
            # Create test profile
            original_profile = UserProfile(
                full_name="Ada Lovelace",
                email="ada@example.com",
                timezone="Europe/London",
                notes="Test notes for Ada"
            )
            
            # Save profile
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as file:
                yaml.safe_dump(original_profile.model_dump(), file, default_flow_style=False, sort_keys=False)
            
            # Load profile
            with open(temp_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
            loaded_profile = UserProfile(**data)
            
            assert loaded_profile.full_name == original_profile.full_name
            assert loaded_profile.email == original_profile.email
            assert loaded_profile.timezone == original_profile.timezone
            assert loaded_profile.notes == original_profile.notes
    
    def test_yaml_format(self):
        """Test that saved YAML has expected format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "user_profile.yaml"
            
            profile = UserProfile(
                full_name="Test User",
                email="test@example.com",
                timezone="UTC",
                notes="Multi-line\nnotes for testing"
            )
            
            # Save profile
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as file:
                yaml.safe_dump(profile.model_dump(), file, default_flow_style=False, sort_keys=False)
            
            # Check YAML content
            with open(temp_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            assert "full_name: Test User" in content
            assert "email: test@example.com" in content
            assert "timezone: UTC" in content
            assert "notes:" in content
            assert "Multi-line" in content


class TestUserProfileDict:
    """Test dictionary conversion for API responses."""
    
    def test_profile_dict_conversion(self):
        """Test converting profile to dictionary."""
        profile = UserProfile(
            full_name="Test User",
            email="test@example.com",
            timezone="UTC",
            notes="Test notes"
        )
        
        profile_dict = profile.model_dump()
        
        assert profile_dict["full_name"] == "Test User"
        assert profile_dict["email"] == "test@example.com"
        assert profile_dict["timezone"] == "UTC"
        assert profile_dict["notes"] == "Test notes"
        assert "created_at" in profile_dict
        assert "updated_at" in profile_dict
    
    def test_update_dict_conversion(self):
        """Test converting update to dictionary with exclude_unset."""
        update = UserProfileUpdate(
            full_name="Updated Name",
            timezone="America/New_York"
        )
        
        update_dict = update.model_dump(exclude_unset=True)
        
        assert update_dict["full_name"] == "Updated Name"
        assert update_dict["timezone"] == "America/New_York"
        assert "email" not in update_dict
        assert "notes" not in update_dict


if __name__ == "__main__":
    pytest.main([__file__]) 