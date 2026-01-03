"""
Unit tests for configuration management endpoints.
Tests endpoint behavior with mocked dependencies.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.config_endpoints import router
from models.config import ConfigValidationResult, ConfigBackupInfo


@pytest.fixture
def app():
    """Create test FastAPI app with config router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestConfigEndpoints:
    """Unit tests for configuration management endpoints with mocked dependencies."""

    @patch('api.config_endpoints.config_registry.get_manager')
    def test_validate_current_configuration(self, mock_get_manager, client):
        """Test GET /api/config/validate for current configuration."""
        mock_loader = MagicMock()
        mock_validation_result = MagicMock()
        mock_validation_result.valid = True
        mock_validation_result.errors = []
        mock_validation_result.warnings = ["No servers enabled"]
        mock_validation_result.details = {"server_count": 2, "enabled_count": 0}
        mock_loader.validate_config.return_value = mock_validation_result
        mock_get_manager.return_value = mock_loader

        response = client.get("/api/config/validate")

        assert response.status_code == 200
        data = response.json()

        assert data["validation_result"]["valid"] is True
        assert data["validation_result"]["server_count"] == 2
        assert "warnings" in data["message"]

        mock_loader.validate_config.assert_called_once_with()

    @patch('api.config_endpoints.config_registry.get_manager')
    def test_list_configuration_backups(self, mock_get_manager, client):
        """Test GET /api/config/backups."""
        mock_loader = MagicMock()
        mock_backups = [
            ConfigBackupInfo(
                backup_id="20250606_143022_mcp_config",
                timestamp="2025-06-06T14:30:22Z",
                server_count=3,
                description="Manual backup"
            ),
            ConfigBackupInfo(
                backup_id="20250606_120000_mcp_config",
                timestamp="2025-06-06T12:00:00Z",
                server_count=2
            )
        ]
        mock_loader.list_backups.return_value = mock_backups
        mock_get_manager.return_value = mock_loader

        response = client.get("/api/config/backups")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 2
        assert data[0]["backup_id"] == "20250606_143022_mcp_config"
        assert data[0]["server_count"] == 3
        assert data[1]["backup_id"] == "20250606_120000_mcp_config"

        mock_loader.list_backups.assert_called_once()

    @patch('api.config_endpoints.config_registry.get_manager')
    def test_create_configuration_backup(self, mock_get_manager, client):
        """Test POST /api/config/backups."""
        mock_loader = MagicMock()
        mock_backup_info = ConfigBackupInfo(
            backup_id="20250606_143022_mcp_config",
            timestamp="2025-06-06T14:30:22Z",
            server_count=3,
            description="Test backup"
        )
        mock_loader.create_backup.return_value = mock_backup_info
        mock_get_manager.return_value = mock_loader

        response = client.post("/api/config/backups?description=Test backup")

        assert response.status_code == 200
        data = response.json()

        assert data["backup_id"] == "20250606_143022_mcp_config"
        assert data["description"] == "Test backup"
        assert data["server_count"] == 3

        mock_loader.create_backup.assert_called_once_with("Test backup")

    @patch('api.config_endpoints.publish')
    @patch('api.config_endpoints.config_registry.get_manager')
    def test_restore_configuration_backup_success(self, mock_get_manager, mock_publish, client):
        """Test POST /api/config/restore/{backup_id} successful restoration."""
        mock_loader = MagicMock()
        mock_loader.restore_backup.return_value = True
        mock_get_manager.return_value = mock_loader
        mock_publish.return_value = None

        backup_id = "20250606_143022_mcp_config"
        response = client.post(f"/api/config/restore/{backup_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["backup_id"] == backup_id
        assert data["status"] == "success"
        assert "restored" in data["message"]

        mock_loader.restore_backup.assert_called_once_with(backup_id)

    @patch('api.config_endpoints.config_registry.get_manager')
    def test_restore_configuration_backup_not_found(self, mock_get_manager, client):
        """Test POST /api/config/restore/{backup_id} with non-existent backup."""
        mock_loader = MagicMock()
        mock_loader.restore_backup.return_value = False
        mock_get_manager.return_value = mock_loader

        backup_id = "nonexistent_backup"
        response = client.post(f"/api/config/restore/{backup_id}")

        assert response.status_code == 404
        data = response.json()

        assert "not found" in data["detail"]
        assert backup_id in data["detail"]

        mock_loader.restore_backup.assert_called_once_with(backup_id)

    @patch('api.config_endpoints.publish')
    @patch('api.config_endpoints.config_registry.get_manager')
    def test_validate_configuration_with_warnings(self, mock_get_manager, mock_publish, client):
        """Test validation with warnings but no errors."""
        valid_config = {
            "server1": {"url": "http://localhost:8001/mcp", "health_url": "http://localhost:8001/health", "description": "Server 1", "enabled": False},
        }

        mock_loader = MagicMock()
        mock_validation_result = ConfigValidationResult(
            valid=True,
            errors=[],
            warnings=["No MCP servers are enabled"],
            server_count=1,
            enabled_count=0
        )
        mock_loader.validate_config.return_value = mock_validation_result
        mock_get_manager.return_value = mock_loader
        mock_publish.return_value = None

        response = client.post("/api/config/validate", json={"config": valid_config})

        assert response.status_code == 200
        data = response.json()

        assert data["validation_result"]["valid"] is True
        assert len(data["validation_result"]["warnings"]) > 0
        assert "No MCP servers are enabled" in data["validation_result"]["warnings"]
        assert "warnings" in data["message"]

    def test_validate_configuration_malformed_request(self, client):
        """Test POST /api/config/validate with malformed request."""
        response = client.post("/api/config/validate", json={"invalid": "structure"})

        assert response.status_code == 422  # Pydantic validation error

    @patch('api.config_endpoints.publish')
    @patch('api.config_endpoints.config_registry.get_manager')
    def test_validate_configuration_internal_error(self, mock_get_manager, mock_publish, client):
        """Test validation with internal server error."""
        mock_loader = MagicMock()
        mock_loader.validate_config.side_effect = Exception("Internal error")
        mock_get_manager.return_value = mock_loader
        mock_publish.return_value = None

        valid_config = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health",
                "description": "Gmail MCP Server",
                "enabled": True
            }
        }

        response = client.post("/api/config/validate", json={"config": valid_config})

        assert response.status_code == 500
        data = response.json()
        assert "validation failed" in data["detail"]
