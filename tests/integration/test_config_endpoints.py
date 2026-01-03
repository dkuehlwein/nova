"""
Integration tests for configuration management endpoints.
Tests validation, backup, and restore functionality with real config registry.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch

from api.config_endpoints import router
from utils.config_registry import config_registry


@pytest.fixture
async def initialized_config_registry():
    """Initialize config registry for tests."""
    if not config_registry._initialized:
        await config_registry.initialize()
    yield config_registry


@pytest.fixture
def app(initialized_config_registry):
    """Create test FastAPI app with config router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestConfigValidationIntegration:
    """Integration tests for config validation with real config registry."""

    @pytest.mark.asyncio
    async def test_validate_configuration_valid(self, client, initialized_config_registry):
        """Test POST /api/config/validate with valid configuration."""
        valid_config = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health",
                "description": "Gmail MCP Server",
                "enabled": True
            }
        }

        with patch('api.config_endpoints.publish'):
            response = client.post("/api/config/validate", json={"config": valid_config})

        assert response.status_code == 200
        data = response.json()

        assert data["validation_result"]["valid"] is True
        assert len(data["validation_result"]["errors"]) == 0
        assert data["validation_result"]["server_count"] == 1
        assert data["validation_result"]["enabled_count"] == 1
        assert "valid" in data["message"]

    @pytest.mark.asyncio
    async def test_validate_configuration_invalid_url(self, client, initialized_config_registry):
        """Test POST /api/config/validate with invalid URL."""
        invalid_config = {
            "gmail": {
                "url": "not-a-valid-url",
                "health_url": "http://localhost:8002/health",
                "description": "Gmail MCP Server",
                "enabled": True
            }
        }

        with patch('api.config_endpoints.publish'):
            response = client.post("/api/config/validate", json={"config": invalid_config})

        assert response.status_code == 200
        data = response.json()

        assert data["validation_result"]["valid"] is False
        assert len(data["validation_result"]["errors"]) > 0
        assert "validation errors" in data["message"]

    @pytest.mark.asyncio
    async def test_validate_configuration_invalid_health_url(self, client, initialized_config_registry):
        """Test POST /api/config/validate with invalid health URL."""
        invalid_config = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/invalid",
                "description": "Gmail MCP Server",
                "enabled": True
            }
        }

        with patch('api.config_endpoints.publish'):
            response = client.post("/api/config/validate", json={"config": invalid_config})

        assert response.status_code == 200
        data = response.json()

        assert data["validation_result"]["valid"] is False
        assert any("health" in error.lower() for error in data["validation_result"]["errors"])

    @pytest.mark.asyncio
    async def test_validate_configuration_empty_description(self, client, initialized_config_registry):
        """Test POST /api/config/validate with empty description."""
        invalid_config = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health",
                "description": "   ",
                "enabled": True
            }
        }

        with patch('api.config_endpoints.publish'):
            response = client.post("/api/config/validate", json={"config": invalid_config})

        assert response.status_code == 200
        data = response.json()

        assert data["validation_result"]["valid"] is False
        assert any("description" in error.lower() for error in data["validation_result"]["errors"])

    @pytest.mark.asyncio
    async def test_validate_configuration_reserved_name(self, client, initialized_config_registry):
        """Test POST /api/config/validate with reserved server name."""
        invalid_config = {
            "admin": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health",
                "description": "Admin Server",
                "enabled": True
            }
        }

        with patch('api.config_endpoints.publish'):
            response = client.post("/api/config/validate", json={"config": invalid_config})

        assert response.status_code == 200
        data = response.json()

        assert data["validation_result"]["valid"] is False
        assert any("reserved" in error.lower() for error in data["validation_result"]["errors"])

    @pytest.mark.asyncio
    async def test_validate_configuration_duplicate_urls(self, client, initialized_config_registry):
        """Test POST /api/config/validate with duplicate URLs."""
        invalid_config = {
            "gmail": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health",
                "description": "Gmail MCP Server",
                "enabled": True
            },
            "outlook": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/status",
                "description": "Outlook MCP Server",
                "enabled": True
            }
        }

        with patch('api.config_endpoints.publish'):
            response = client.post("/api/config/validate", json={"config": invalid_config})

        assert response.status_code == 200
        data = response.json()

        assert data["validation_result"]["valid"] is False
        assert any("duplicate" in error.lower() for error in data["validation_result"]["errors"])
