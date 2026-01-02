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


class TestConfigManager:
    """Test cases for user profile configuration management."""
    
    def test_load_default_profile(self):
        """Test loading default profile when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            from utils.yaml_config_manager import YamlConfigManager
            
            temp_path = Path(temp_dir) / "user_profile.yaml"
            
            default_profile = UserProfile(
                full_name="Nova User",
                email="user@example.com",
                timezone="UTC",
                notes="Add your personal context here."
            )
            
            config_manager = YamlConfigManager(
                config_path=temp_path,
                config_name="test_user_profile",
                config_model=UserProfile,
                default_config=default_profile
            )
            
            profile = config_manager.get_config()
            
            assert profile.full_name == "Nova User"
            assert profile.email == "user@example.com"
            assert profile.timezone == "UTC"
            assert "Add your personal context here" in profile.notes
            assert temp_path.exists()
    
    def test_save_and_load_profile(self):
        """Test saving and loading user profile."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "user_profile.yaml"
            
            original_profile = UserProfile(
                full_name="Ada Lovelace",
                email="ada@example.com",
                timezone="Europe/London",
                notes="Test notes for Ada"
            )
            
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as file:
                yaml.safe_dump(original_profile.model_dump(), file, default_flow_style=False, sort_keys=False)
            
            with open(temp_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
            loaded_profile = UserProfile(**data)
            
            assert loaded_profile.full_name == original_profile.full_name
            assert loaded_profile.email == original_profile.email
            assert loaded_profile.timezone == original_profile.timezone
            assert loaded_profile.notes == original_profile.notes
