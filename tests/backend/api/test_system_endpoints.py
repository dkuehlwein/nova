"""
Tests for system management API endpoints.

Tests system health monitoring, service restart functionality,
and admin operations.
"""

import pytest
import subprocess
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from backend.api.system_endpoints import router, ALLOWED_SERVICES, SystemHealthSummary


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
    
    def test_get_allowed_services(self, client):
        """Test GET /api/system/allowed-services."""
        response = client.get("/api/system/allowed-services")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "allowed_services" in data
        assert "total_count" in data
        assert data["total_count"] == len(ALLOWED_SERVICES)
        assert set(data["allowed_services"]) == ALLOWED_SERVICES
    
    def test_system_health(self, client):
        """Test GET /api/system/health."""
        response = client.get("/api/system/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "system-api"
        assert "version" in data
    
    @patch('subprocess.run')
    def test_restart_service_success(self, mock_subprocess, client):
        """Test POST /api/system/restart/{service_name} with successful restart."""
        # Mock successful subprocess result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Service restarted successfully"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        response = client.post("/api/system/restart/redis")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_name"] == "redis"
        assert data["status"] == "success"
        assert "restarted successfully" in data["message"]
        assert data["stdout"] == "Service restarted successfully"
        assert data["stderr"] == ""
        assert data["exit_code"] == 0
        
        # Verify subprocess was called correctly
        mock_subprocess.assert_called_once_with(
            ["docker-compose", "restart", "redis"],
            capture_output=True,
            text=True,
            timeout=60
        )
    
    @patch('subprocess.run')
    def test_restart_service_failure(self, mock_subprocess, client):
        """Test POST /api/system/restart/{service_name} with failed restart."""
        # Mock failed subprocess result
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Service not found"
        mock_subprocess.return_value = mock_result
        
        response = client.post("/api/system/restart/redis")
        
        assert response.status_code == 200  # Still returns 200, but with error status
        data = response.json()
        
        assert data["service_name"] == "redis"
        assert data["status"] == "error"
        assert "restart failed" in data["message"]
        assert data["stdout"] == ""
        assert data["stderr"] == "Service not found"
        assert data["exit_code"] == 1
    
    def test_restart_service_unauthorized(self, client):
        """Test POST /api/system/restart/{service_name} with unauthorized service."""
        response = client.post("/api/system/restart/unauthorized_service")
        
        assert response.status_code == 400
        data = response.json()
        
        assert "not allowed" in data["detail"]
        assert "unauthorized_service" in data["detail"]
    
    @patch('subprocess.run')
    def test_restart_service_timeout(self, mock_subprocess, client):
        """Test POST /api/admin/restart/{service_name} with timeout."""
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
        """Test POST /api/admin/restart/{service_name} when docker-compose is not found."""
        mock_subprocess.side_effect = FileNotFoundError()
        
        response = client.post("/api/system/restart/redis")
        
        assert response.status_code == 500
        data = response.json()
        
        assert "docker-compose command not found" in data["detail"]
    
    def test_restart_service_with_request_body(self, client):
        """Test POST /api/admin/restart/{service_name} with request body."""
        with patch('subprocess.run') as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Service restarted"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result
            
            response = client.post(
                "/api/system/restart/redis",
                json={"force": True}
            )
            
            assert response.status_code == 200
            # The force parameter is currently unused but should not cause errors
    
    def test_allowed_services_constant(self):
        """Test that ALLOWED_SERVICES contains expected services."""
        expected_services = {
            "mcp_gmail", "redis", "postgres", "chat-agent", "core-agent"
        }
        
        assert ALLOWED_SERVICES == expected_services 