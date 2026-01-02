"""
Tests for system management API endpoints - Security and edge cases.
"""

import pytest
import subprocess
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from backend.api.system_endpoints import router, ALLOWED_SERVICES


@pytest.fixture
def app():
    """Create test FastAPI app with admin router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestSystemEndpoints:
    """Test system management endpoints."""
    
    def test_restart_service_unauthorized(self, client):
        """Test POST /api/system/restart/{service_name} with unauthorized service."""
        response = client.post("/api/system/restart/unauthorized_service")
        
        assert response.status_code == 400
        data = response.json()
        
        assert "not allowed" in data["detail"]
        assert "unauthorized_service" in data["detail"]
    
    @patch('subprocess.run')
    def test_restart_service_timeout(self, mock_subprocess, client):
        """Test POST /api/system/restart/{service_name} with timeout."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired(
            cmd=["docker-compose", "restart", "redis"],
            timeout=60
        )
        
        response = client.post("/api/system/restart/redis")
        
        assert response.status_code == 408
        data = response.json()
        
        assert "timed out" in data["detail"]
    
    @patch('subprocess.run')
    def test_restart_service_docker_compose_not_found(self, mock_subprocess, client):
        """Test POST /api/system/restart/{service_name} when docker-compose is not found."""
        mock_subprocess.side_effect = FileNotFoundError()
        
        response = client.post("/api/system/restart/redis")
        
        assert response.status_code == 500
        data = response.json()
        
        assert "docker-compose command not found" in data["detail"]
