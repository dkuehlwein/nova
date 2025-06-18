"""
Test System Prompt Management Endpoints in Chat API

Tests for system prompt CRUD operations, backup management,
and integration with agent reloading.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch, mock_open, Mock
from pathlib import Path
import datetime

# Import the router directly instead of the full app
from backend.api.chat_endpoints import router


@pytest.fixture
def app():
    """Create test FastAPI app with chat router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestSystemPromptEndpoints:
    """Test system prompt management in chat API."""

    @patch("builtins.open", new_callable=mock_open, read_data="Test prompt content")
    @patch("backend.api.chat_endpoints.Path")
    def test_get_system_prompt_success(self, mock_path_class, mock_file, client):
        """Test successful retrieval of system prompt."""
        # Setup mock for the prompt file
        mock_prompt_file = Mock()
        mock_prompt_file.exists.return_value = True
        mock_stat_obj = Mock()
        mock_stat_obj.st_mtime = 1234567890.0
        mock_stat_obj.st_size = 100
        mock_prompt_file.stat.return_value = mock_stat_obj
        
        # Mock Path constructor to return the correct object based on path
        def path_constructor(path_str):
            if "NOVA_SYSTEM_PROMPT.md" in str(path_str):
                # Return the actual mock, but set up __str__ to return the path
                mock_prompt_file.__str__ = lambda self: str(path_str)
                return mock_prompt_file
            return Mock()
        
        mock_path_class.side_effect = path_constructor
        
        response = client.get("/chat/system-prompt")
        
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test prompt content"
        assert data["file_path"] == "backend/agent/prompts/NOVA_SYSTEM_PROMPT.md"
        assert "last_modified" in data
        assert data["size_bytes"] == 100

    @patch("backend.api.chat_endpoints.Path")
    def test_get_system_prompt_file_not_found(self, mock_path_class, client):
        """Test 404 when prompt file doesn't exist."""
        mock_prompt_file = Mock()
        mock_prompt_file.exists.return_value = False
        
        def path_constructor(path_str):
            if "NOVA_SYSTEM_PROMPT.md" in str(path_str):
                mock_prompt_file.__str__ = lambda self: str(path_str)
                return mock_prompt_file
            return Mock()
        
        mock_path_class.side_effect = path_constructor
        
        response = client.get("/chat/system-prompt")
        
        assert response.status_code == 404
        assert "System prompt file not found" in response.json()["detail"]

    @patch("builtins.open", side_effect=IOError("Read error"))
    @patch("backend.api.chat_endpoints.Path")
    def test_get_system_prompt_read_error(self, mock_path_class, mock_file, client):
        """Test 500 when file read fails."""
        mock_prompt_file = Mock()
        mock_prompt_file.exists.return_value = True
        
        def path_constructor(path_str):
            if "NOVA_SYSTEM_PROMPT.md" in str(path_str):
                return mock_prompt_file
            return Mock()
        
        mock_path_class.side_effect = path_constructor
        
        response = client.get("/chat/system-prompt")
        
        assert response.status_code == 500
        assert "Failed to read system prompt" in response.json()["detail"]

    @patch("backend.api.chat_endpoints.publish")
    @patch("backend.api.chat_endpoints.clear_chat_agent_cache")
    @patch("builtins.open", new_callable=mock_open)
    @patch("backend.api.chat_endpoints.Path")
    def test_update_system_prompt_success(self, mock_path_class, mock_file, mock_clear_cache, mock_publish, client):
        """Test successful system prompt update."""
        # Setup mocks for different paths
        mock_prompt_file = Mock()
        mock_prompt_file.exists.return_value = True
        mock_stat_obj = Mock()
        mock_stat_obj.st_mtime = 1234567890.0
        mock_stat_obj.st_size = 150
        mock_prompt_file.stat.return_value = mock_stat_obj
        
        mock_backup_dir = Mock()
        mock_backup_dir.mkdir.return_value = None
        # Support path operations like backup_dir / "filename"
        mock_backup_dir.__truediv__ = lambda self, other: Mock(name=f"backup_path_{other}", spec=Path)
        
        def path_constructor(path_str):
            if "NOVA_SYSTEM_PROMPT.md" in str(path_str):
                mock_prompt_file.__str__ = lambda self: str(path_str)
                return mock_prompt_file
            elif str(path_str) == "backups":
                mock_backup_dir.__str__ = lambda self: str(path_str)
                return mock_backup_dir
            else:
                mock_path = Mock()  # For backup files
                mock_path.__str__ = lambda self: str(path_str)
                return mock_path
        
        mock_path_class.side_effect = path_constructor
        
        new_content = "Updated prompt content"
        
        response = client.put(
            "/chat/system-prompt",
            json={"content": new_content}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == new_content
        assert data["size_bytes"] == 150
        
        # Verify agent cache was cleared
        mock_clear_cache.assert_called_once()
        
        # Verify event was published
        mock_publish.assert_called_once()
        published_event = mock_publish.call_args[0][0]
        assert published_event.type == "prompt_updated"
        assert published_event.data["change_type"] == "manual_update"

    @patch("builtins.open", side_effect=IOError("Write error"))
    @patch("backend.api.chat_endpoints.Path")
    def test_update_system_prompt_write_error(self, mock_path_class, mock_file, client):
        """Test 500 when file write fails."""
        mock_prompt_file = Mock()
        mock_prompt_file.exists.return_value = False  # No existing file to backup
        
        mock_backup_dir = Mock()
        mock_backup_dir.mkdir.return_value = None
        
        def path_constructor(path_str):
            if "NOVA_SYSTEM_PROMPT.md" in str(path_str):
                return mock_prompt_file
            elif str(path_str) == "backups":
                return mock_backup_dir
            else:
                return Mock()
        
        mock_path_class.side_effect = path_constructor
        
        response = client.put(
            "/chat/system-prompt",
            json={"content": "New content"}
        )
        
        assert response.status_code == 500
        assert "Failed to update system prompt" in response.json()["detail"]

    @patch("backend.api.chat_endpoints.Path")
    def test_list_prompt_backups_success(self, mock_path_class, client):
        """Test successful backup listing."""
        mock_backup_dir = Mock()
        mock_backup_dir.exists.return_value = True
        
        # Mock backup files
        mock_backup1 = Mock()
        mock_backup1.name = "prompt_20250101_120000.bak"
        mock_backup1.stat.return_value.st_mtime = 1704110400.0
        mock_backup1.stat.return_value.st_size = 200
        
        mock_backup2 = Mock()
        mock_backup2.name = "prompt_20250102_120000.bak"
        mock_backup2.stat.return_value.st_mtime = 1704196800.0
        mock_backup2.stat.return_value.st_size = 180
        
        mock_backup_dir.glob.return_value = [mock_backup1, mock_backup2]
        
        def path_constructor(path_str):
            if str(path_str) == "backups":
                return mock_backup_dir
            return Mock()
        
        mock_path_class.side_effect = path_constructor
        
        response = client.get("/chat/system-prompt/backups")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["backups"]) == 2
        # Should be sorted by creation time, newest first
        assert data["backups"][0]["filename"] == "prompt_20250102_120000.bak"
        assert data["backups"][1]["filename"] == "prompt_20250101_120000.bak"

    @patch("backend.api.chat_endpoints.Path")
    def test_list_prompt_backups_no_directory(self, mock_path_class, client):
        """Test backup listing when directory doesn't exist."""
        mock_backup_dir = Mock()
        mock_backup_dir.exists.return_value = False
        
        def path_constructor(path_str):
            if str(path_str) == "backups":
                return mock_backup_dir
            return Mock()
        
        mock_path_class.side_effect = path_constructor
        
        response = client.get("/chat/system-prompt/backups")
        
        assert response.status_code == 200
        data = response.json()
        assert data["backups"] == []

    @patch("backend.api.chat_endpoints.publish")
    @patch("backend.api.chat_endpoints.clear_chat_agent_cache")
    @patch("builtins.open", new_callable=mock_open, read_data="Backup content")
    @patch("backend.api.chat_endpoints.Path")
    def test_restore_prompt_backup_success(self, mock_path_class, mock_file, mock_clear_cache, mock_publish, client):
        """Test successful backup restoration."""
        backup_filename = "prompt_20250101_120000.bak"
        
        # Setup mocks for different paths
        mock_backup_file = Mock()
        mock_backup_file.exists.return_value = True
        
        mock_backup_dir = Mock()
        # Support path operations like backup_dir / filename - return the backup_file mock
        mock_backup_dir.__truediv__ = lambda self, other: mock_backup_file
        
        mock_prompt_file = Mock()
        mock_prompt_file.exists.return_value = True
        mock_stat_obj = Mock()
        mock_stat_obj.st_mtime = 1234567890.0
        mock_stat_obj.st_size = 120
        mock_prompt_file.stat.return_value = mock_stat_obj
        
        def path_constructor(path_str):
            if str(path_str) == "backups":
                mock_backup_dir.__str__ = lambda self: str(path_str)
                return mock_backup_dir
            elif backup_filename in str(path_str):
                mock_backup_file.__str__ = lambda self: str(path_str)
                return mock_backup_file
            elif "NOVA_SYSTEM_PROMPT.md" in str(path_str):
                mock_prompt_file.__str__ = lambda self: str(path_str)
                return mock_prompt_file
            else:
                mock_path = Mock()
                mock_path.__str__ = lambda self: str(path_str)
                return mock_path
        
        mock_path_class.side_effect = path_constructor
        
        response = client.post(f"/chat/system-prompt/restore/{backup_filename}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Backup content"
        assert data["size_bytes"] == 120
        
        # Verify agent cache was cleared
        mock_clear_cache.assert_called_once()
        
        # Verify event was published
        mock_publish.assert_called_once()
        published_event = mock_publish.call_args[0][0]
        assert published_event.type == "prompt_updated"
        assert published_event.data["change_type"] == "restore_backup"

    @patch("backend.api.chat_endpoints.Path")
    def test_restore_prompt_backup_not_found(self, mock_path_class, client):
        """Test 404 when backup file doesn't exist."""
        backup_filename = "prompt_20250101_120000.bak"  # Valid format but nonexistent file
        
        mock_backup_file = Mock()
        mock_backup_file.exists.return_value = False
        
        mock_backup_dir = Mock()
        # Support path operations like backup_dir / filename - return the backup_file mock
        mock_backup_dir.__truediv__ = lambda self, other: mock_backup_file
        
        def path_constructor(path_str):
            if str(path_str) == "backups":
                mock_backup_dir.__str__ = lambda self: str(path_str)
                return mock_backup_dir
            elif backup_filename in str(path_str):
                mock_backup_file.__str__ = lambda self: str(path_str)
                return mock_backup_file
            else:
                mock_path = Mock()
                mock_path.__str__ = lambda self: str(path_str)
                return mock_path
        
        mock_path_class.side_effect = path_constructor
        
        response = client.post(f"/chat/system-prompt/restore/{backup_filename}")
        
        assert response.status_code == 404
        assert "Backup file not found" in response.json()["detail"]

    def test_restore_prompt_backup_invalid_filename(self, client):
        """Test 400 for invalid backup filename format."""
        invalid_filename = "invalid_file.txt"
        
        with patch("backend.api.chat_endpoints.Path") as mock_path_class:
            mock_backup_dir = Mock()
            # Support path operations like backup_dir / filename
            mock_backup_dir.__truediv__ = lambda self, other: Mock(name=f"backup_path_{other}", spec=Path)
            
            def path_constructor(path_str):
                if str(path_str) == "backups":
                    return mock_backup_dir
                else:
                    mock_path = Mock()
                    mock_path.__str__ = lambda self: str(path_str)
                    return mock_path
            
            mock_path_class.side_effect = path_constructor
        
            response = client.post(f"/chat/system-prompt/restore/{invalid_filename}")
        
            assert response.status_code == 400
            assert "Invalid backup filename format" in response.json()["detail"]

    @patch("builtins.open", side_effect=IOError("Read error"))
    @patch("backend.api.chat_endpoints.Path")
    def test_restore_prompt_backup_read_error(self, mock_path_class, mock_file, client):
        """Test 500 when backup file read fails."""
        backup_filename = "prompt_20250101_120000.bak"
        
        mock_backup_file = Mock()
        mock_backup_file.exists.return_value = True
        
        mock_backup_dir = Mock()
        # Support path operations like backup_dir / filename - return the backup_file mock
        mock_backup_dir.__truediv__ = lambda self, other: mock_backup_file
        
        def path_constructor(path_str):
            if str(path_str) == "backups":
                return mock_backup_dir
            elif backup_filename in str(path_str):
                return mock_backup_file
            else:
                return Mock()
        
        mock_path_class.side_effect = path_constructor
        
        response = client.post(f"/chat/system-prompt/restore/{backup_filename}")
        
        assert response.status_code == 500
        assert "Failed to restore backup" in response.json()["detail"] 