"""
Tests for Nova System Prompt API Endpoints

Tests for system prompt management functionality including reading, updating,
backup creation, and restoration.
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.prompt_endpoints import router


@pytest.fixture
def test_app():
    """Create a test FastAPI app with prompt endpoints."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


class TestSystemPromptEndpoints:
    """Test system prompt management endpoints."""
    
    def test_get_system_prompt(self, client):
        """Test getting current system prompt."""
        content = "# Test System Prompt\nYou are Nova."
        
        with patch('api.prompt_endpoints.Path') as mock_path_class, \
             patch('builtins.open', mock_open(read_data=content)) as mock_file:
            
            # Mock the Path object
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.stat.return_value = Mock(st_mtime=datetime.now().timestamp(), st_size=len(content))
            mock_path_class.return_value = mock_path
            
            response = client.get("/system-prompt")
            assert response.status_code == 200
            
            data = response.json()
            assert "content" in data
            assert "file_path" in data
            assert "last_modified" in data
            assert "size_bytes" in data
            assert data["content"] == content
    
    def test_update_system_prompt(self, client):
        """Test updating system prompt."""
        new_content = "# Updated System Prompt\nYou are Nova, updated version."
        
        with patch('api.prompt_endpoints.Path') as mock_path_class, \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('api.prompt_endpoints.clear_chat_agent_cache') as mock_clear_cache, \
             patch('api.prompt_endpoints.publish') as mock_publish, \
             patch('api.prompt_endpoints.should_create_backup', return_value=False):
            
            # Mock the Path object
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.stat.return_value = Mock(st_mtime=datetime.now().timestamp(), st_size=len(new_content))
            mock_path.parent = Mock()
            mock_backup_dir = Mock() 
            mock_backup_dir.mkdir = Mock()
            mock_path.parent.__truediv__ = Mock(return_value=mock_backup_dir)
            mock_path_class.return_value = mock_path
            
            update_request = {"content": new_content}
            response = client.put("/system-prompt", json=update_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["content"] == new_content
            assert "file_path" in data
            assert "last_modified" in data
            assert "size_bytes" in data
            
            # Verify cache was cleared
            mock_clear_cache.assert_called_once()
            
            # Verify Redis event was published
            mock_publish.assert_called_once()
    
    def test_list_prompt_backups(self, client):
        """Test listing prompt backups."""
        with patch('api.prompt_endpoints.Path') as mock_path_class:
            # Mock the Path object
            mock_path = Mock()
            mock_backup_dir = Mock()
            mock_backup_dir.exists.return_value = True
            mock_path.parent = Mock()
            mock_path.parent.__truediv__ = Mock(return_value=mock_backup_dir)
            mock_path_class.return_value = mock_path
            
            # Mock backup files
            mock_backup1 = Mock()
            mock_backup1.name = "prompt_20250106_120000.bak"
            mock_backup1.stat.return_value = Mock(st_mtime=datetime.now().timestamp(), st_size=512)

            mock_backup2 = Mock()
            mock_backup2.name = "prompt_20250106_110000.bak"
            mock_backup2.stat.return_value = Mock(st_mtime=datetime.now().timestamp(), st_size=256)

            mock_backup_dir.glob.return_value = [mock_backup1, mock_backup2]

            response = client.get("/system-prompt/backups")
            assert response.status_code == 200

            data = response.json()
            assert "backups" in data
            assert len(data["backups"]) == 2
            
            # Verify structure of first backup
            backup = data["backups"][0]
            assert "filename" in backup
            assert "created" in backup
            assert "size_bytes" in backup
            assert backup["filename"] in ["prompt_20250106_120000.bak", "prompt_20250106_110000.bak"]
    
    def test_restore_prompt_backup(self, client):
        """Test restoring from backup."""
        backup_filename = "prompt_20250106_120000.bak"
        restored_content = "# Restored System Prompt\nYou are Nova, restored."
        
        with patch('api.prompt_endpoints.Path') as mock_path_class, \
             patch('builtins.open', mock_open(read_data=restored_content)) as mock_file, \
             patch('api.prompt_endpoints.clear_chat_agent_cache') as mock_clear_cache, \
             patch('api.prompt_endpoints.publish') as mock_publish, \
             patch('api.prompt_endpoints.should_create_backup', return_value=False):
            
            # Mock the Path objects
            mock_path = Mock()
            mock_backup_dir = Mock()
            mock_backup_file = Mock()
            mock_backup_file.exists.return_value = True
            
            mock_backup_dir.__truediv__ = Mock(return_value=mock_backup_file)
            mock_path.parent = Mock()
            mock_path.parent.__truediv__ = Mock(return_value=mock_backup_dir)
            mock_path.exists.return_value = True
            mock_path.stat.return_value = Mock(st_mtime=datetime.now().timestamp(), st_size=len(restored_content))
            mock_path_class.return_value = mock_path
            
            response = client.post(f"/system-prompt/restore/{backup_filename}")
            assert response.status_code == 200
            
            data = response.json()
            assert "content" in data
            assert "file_path" in data
            assert data["content"] == restored_content
            
            # Verify cache was cleared
            mock_clear_cache.assert_called_once()
            
            # Verify Redis event was published
            mock_publish.assert_called_once()
    
    def test_restore_invalid_backup(self, client):
        """Test restoring from invalid backup filename."""
        invalid_filename = "invalid_backup.txt"
        
        with patch('api.prompt_endpoints.Path') as mock_path_class:
            # Mock the Path objects
            mock_path = Mock()
            mock_backup_dir = Mock()
            mock_backup_file = Mock()
            mock_backup_file.exists.return_value = True  # File exists so we can test validation
            
            mock_backup_dir.__truediv__ = Mock(return_value=mock_backup_file)
            mock_path.parent = Mock()
            mock_path.parent.__truediv__ = Mock(return_value=mock_backup_dir)
            mock_path_class.return_value = mock_path
        
            response = client.post(f"/system-prompt/restore/{invalid_filename}")
            assert response.status_code == 400
            
            data = response.json()
            assert "detail" in data
            assert "Invalid backup filename format" in data["detail"]
    
    def test_delete_backup(self, client):
        """Test deleting a backup file."""
        backup_filename = "prompt_20250106_120000.bak"
        
        with patch('api.prompt_endpoints.Path') as mock_path_class:
            # Mock the Path objects
            mock_path = Mock()
            mock_backup_dir = Mock()
            mock_backup_file = Mock()
            mock_backup_file.exists.return_value = True
            mock_backup_file.unlink = Mock()
            
            mock_backup_dir.__truediv__ = Mock(return_value=mock_backup_file)
            mock_path.parent = Mock()
            mock_path.parent.__truediv__ = Mock(return_value=mock_backup_dir)
            mock_path_class.return_value = mock_path
            
            response = client.delete(f"/system-prompt/backups/{backup_filename}")
            assert response.status_code == 200
            
            data = response.json()
            assert "message" in data
            assert backup_filename in data["message"]
            
            # Verify file was deleted
            mock_backup_file.unlink.assert_called_once()
    
    def test_delete_invalid_backup(self, client):
        """Test deleting backup with invalid filename."""
        invalid_filename = "invalid_backup.txt"
        
        with patch('api.prompt_endpoints.Path') as mock_path_class:
            # Mock the Path objects
            mock_path = Mock()
            mock_backup_dir = Mock()
            mock_backup_file = Mock()
            
            mock_backup_dir.__truediv__ = Mock(return_value=mock_backup_file)
            mock_path.parent = Mock()
            mock_path.parent.__truediv__ = Mock(return_value=mock_backup_dir)
            mock_path_class.return_value = mock_path
        
            response = client.delete(f"/system-prompt/backups/{invalid_filename}")
            assert response.status_code == 400
            
            data = response.json()
            assert "detail" in data
            assert "Invalid backup filename format" in data["detail"]
    
    def test_clear_prompt_cache(self, client):
        """Test clearing chat agent cache."""
        with patch('api.prompt_endpoints.clear_chat_agent_cache') as mock_clear_cache:
            response = client.post("/system-prompt/clear-cache")
            assert response.status_code == 200
            
            data = response.json()
            assert "message" in data
            assert "cleared" in data["message"].lower()
            
            # Verify cache was cleared
            mock_clear_cache.assert_called_once()


class TestErrorHandling:
    """Test error handling in prompt endpoints."""
    
    def test_system_prompt_file_not_found(self, client):
        """Test system prompt endpoints when file doesn't exist."""
        with patch('api.prompt_endpoints.Path') as mock_path_class:
            mock_prompt_file = Mock()
            mock_prompt_file.exists.return_value = False
            mock_path_class.return_value = mock_prompt_file
            
            response = client.get("/system-prompt")
            assert response.status_code == 404
            
            data = response.json()
            assert "detail" in data
            assert "System prompt file not found" in data["detail"]
    
    def test_backup_file_not_found(self, client):
        """Test restoring from non-existent backup."""
        backup_filename = "prompt_20250106_999999.bak"
        
        with patch('api.prompt_endpoints.Path') as mock_path_class:
            # Mock the Path objects
            mock_path = Mock()
            mock_backup_dir = Mock()
            mock_backup_file = Mock()
            mock_backup_file.exists.return_value = False
            
            mock_backup_dir.__truediv__ = Mock(return_value=mock_backup_file)
            mock_path.parent = Mock()
            mock_path.parent.__truediv__ = Mock(return_value=mock_backup_dir)
            mock_path_class.return_value = mock_path
        
            response = client.post(f"/system-prompt/restore/{backup_filename}")
            assert response.status_code == 404
            
            data = response.json()
            assert "detail" in data
            assert "Backup file not found" in data["detail"]
    
    def test_update_with_invalid_data(self, client):
        """Test updating prompt with invalid data."""
        # Test with missing content
        response = client.put("/system-prompt", json={})
        assert response.status_code == 422
        
        data = response.json()
        assert "detail" in data
        # Pydantic returns detailed validation errors
        assert isinstance(data["detail"], list)
        assert any("Field required" in str(error) for error in data["detail"]) 