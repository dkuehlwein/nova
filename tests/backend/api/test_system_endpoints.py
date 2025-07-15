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

    @patch('backend.api.system_endpoints.health_monitor')
    def test_get_unified_system_status(self, mock_health_monitor, client):
        """Test GET /api/system/system-health."""
        # Mock the health monitor's calculate_overall_status method
        from unittest.mock import AsyncMock
        mock_health_monitor.calculate_overall_status = AsyncMock(return_value={
            "overall_status": "operational",
            "overall_health_percentage": 100.0,
            "last_updated": "2024-01-01T00:00:00Z",
            "summary": {
                "total_services": 5,
                "healthy_services": 5,
                "degraded_services": 0,
                "critical_services": 0,
                "top_issues": []
            },
            "all_statuses": {
                "database": {
                    "status": "healthy",
                    "checked_at": "2024-01-01T00:00:00Z",
                    "response_time_ms": 10,
                    "error_message": None,
                    "metadata": {"type": "internal"}
                },
                "redis": {
                    "status": "healthy", 
                    "checked_at": "2024-01-01T00:00:00Z",
                    "response_time_ms": 5,
                    "error_message": None,
                    "metadata": {"type": "internal"}
                }
            }
        })
        
        # Mock the SERVICES configuration
        mock_health_monitor.SERVICES = {
            "database": {"type": "infrastructure", "essential": True},
            "redis": {"type": "infrastructure", "essential": True},
            "core_agent": {"type": "core", "essential": True},
            "google_api": {"type": "external", "essential": False},
            "mcp_servers": {"type": "external", "essential": False}
        }
        
        response = client.get("/api/system/system-health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["overall_status"] == "operational"
        assert data["overall_health_percentage"] == 100.0
        assert "last_updated" in data
        assert data["cached"] is True  # Default behavior
        assert "core_services" in data
        assert "infrastructure_services" in data
        assert "external_services" in data
        assert "summary" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert summary["total_services"] == 5
        assert summary["healthy_services"] == 5
        assert summary["degraded_services"] == 0
        assert summary["critical_services"] == 0
        assert summary["top_issues"] == []

    @patch('backend.api.system_endpoints.health_monitor')
    def test_get_unified_system_status_with_force_refresh(self, mock_health_monitor, client):
        """Test GET /api/system/system-health with force_refresh=true."""
        from unittest.mock import AsyncMock
        mock_health_monitor.monitor_all_services = AsyncMock(return_value=None)
        mock_health_monitor.calculate_overall_status = AsyncMock(return_value={
            "overall_status": "degraded",
            "overall_health_percentage": 75.0,
            "last_updated": "2024-01-01T00:00:00Z",
            "summary": {
                "total_services": 4,
                "healthy_services": 3,
                "degraded_services": 1,
                "critical_services": 0,
                "top_issues": ["mcp_servers"]
            },
            "all_statuses": {}
        })
        
        mock_health_monitor.SERVICES = {
            "database": {"type": "infrastructure", "essential": True},
            "redis": {"type": "infrastructure", "essential": True},
            "core_agent": {"type": "core", "essential": True},
            "mcp_servers": {"type": "external", "essential": False}
        }
        
        response = client.get("/api/system/system-health?force_refresh=true")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify force refresh triggered monitoring
        mock_health_monitor.monitor_all_services.assert_called_once()
        
        # Verify response indicates fresh data
        assert data["cached"] is False
        assert data["overall_status"] == "degraded"
        assert data["overall_health_percentage"] == 75.0

    @patch('backend.api.system_endpoints.health_monitor')
    def test_get_service_status(self, mock_health_monitor, client):
        """Test GET /api/system/system-health/{service_name}."""
        # Mock the health monitor's get_cached_status method
        from unittest.mock import AsyncMock
        mock_health_monitor.get_cached_status = AsyncMock(return_value={
            "service_name": "database",
            "status": "healthy",
            "response_time_ms": 15,
            "checked_at": "2024-01-01T00:00:00Z",
            "error_message": None,
            "metadata": {"type": "internal"}
        })
        
        # Mock the SERVICES configuration
        mock_health_monitor.SERVICES = {
            "database": {
                "type": "infrastructure", 
                "essential": True,
                "endpoint": "internal"
            }
        }
        
        response = client.get("/api/system/system-health/database")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["service_name"] == "database"
        assert data["status"] == "healthy"
        assert data["response_time_ms"] == 15
        assert data["service_type"] == "infrastructure"
        assert data["essential"] is True
        assert data["endpoint"] == "internal"

    @patch('backend.api.system_endpoints.health_monitor')
    def test_get_service_status_not_found(self, mock_health_monitor, client):
        """Test GET /api/system/system-health/{service_name} for non-existent service."""
        mock_health_monitor.SERVICES = {
            "database": {"type": "infrastructure", "essential": True}
        }
        
        response = client.get("/api/system/system-health/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]

    @patch('backend.api.system_endpoints.health_monitor')
    def test_refresh_all_services(self, mock_health_monitor, client):
        """Test POST /api/system/system-health/refresh."""
        # Mock async methods with AsyncMock
        from unittest.mock import AsyncMock
        mock_health_monitor.monitor_all_services = AsyncMock(return_value=None)
        mock_health_monitor.calculate_overall_status = AsyncMock(return_value={
            "overall_status": "operational",
            "overall_health_percentage": 100.0,
            "last_updated": "2024-01-01T00:00:00Z",
            "summary": {
                "total_services": 3,
                "healthy_services": 3,
                "degraded_services": 0,
                "critical_services": 0,
                "top_issues": []
            }
        })
        
        response = client.post("/api/system/system-health/refresh")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify monitoring was triggered
        mock_health_monitor.monitor_all_services.assert_called_once()
        
        # Verify response structure
        assert data["message"] == "All services refreshed successfully"
        assert data["overall_status"] == "operational"
        assert "refreshed_at" in data
        assert "summary" in data 