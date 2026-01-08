"""
Tests for main API endpoints.
Tests CRUD operations for tasks, artifacts, and overview functionality.
"""

import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.api_endpoints import router
from backend.models.models import Task, TaskStatus, Artifact


@pytest.fixture
def app():
    """Create test FastAPI app with API router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_task_data():
    """Sample task data for testing."""
    return {
        "title": "Test Task",
        "description": "This is a test task",
        "status": "new",
        "tags": ["urgent", "backend"],
        "person_emails": [],
        "project_names": []
    }


class TestOverviewEndpoints:
    """Test overview and dashboard endpoints."""
    
    @patch('backend.api.api_endpoints.get_cached_dashboard_data')
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_task_dashboard(self, mock_get_session, mock_get_cached_dashboard_data, client, mock_session):
        """Test GET /api/task-dashboard returns dashboard data."""
        mock_get_session.return_value = mock_session
        mock_get_cached_dashboard_data.return_value = None  # No cached data
        
        # Mock task count query and recent activity query
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (TaskStatus.NEW, 5),
            (TaskStatus.IN_PROGRESS, 3),
            (TaskStatus.DONE, 10),
            (TaskStatus.NEEDS_REVIEW, 2)
        ]
        
        # Mock recent activity query
        mock_recent_result = MagicMock()
        mock_recent_result.scalars.return_value.all.return_value = []
        
        # Configure the session to return different results for different queries
        mock_session.execute.side_effect = [mock_result, mock_recent_result]
        
        response = client.get("/api/task-dashboard")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "task_counts" in data
        assert "total_tasks" in data
        assert "pending_decisions" in data
        assert "recent_activity" in data
        assert "system_status" in data
        assert "tasks_by_status" in data
        assert "cache_info" in data
        
        assert data["task_counts"]["new"] == 5
        assert data["task_counts"]["in_progress"] == 3
        assert data["total_tasks"] == 20
        # pending_decisions = needs_review + user_input_received (both 0 in our mock)
        assert data["pending_decisions"] == 2  # Only needs_review in our mock
        assert data["system_status"] == "operational"
        assert data["tasks_by_status"] is None  # Default doesn't include tasks
        assert data["cache_info"]["cached"] is False
        assert data["cache_info"]["use_cache"] is True
        assert data["cache_info"]["includes_tasks"] is False
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_recent_activity(self, mock_get_session, client, mock_session):
        """Test GET /api/recent-activity returns recent activity."""
        mock_get_session.return_value = mock_session
        
        # Mock recent tasks query
        now = datetime.now(timezone.utc)
        mock_task = MagicMock()
        mock_task.id = uuid4()
        mock_task.title = "Test Task"
        mock_task.status = TaskStatus.DONE
        mock_task.updated_at = now - timedelta(minutes=30)
        mock_task.task_metadata = {"last_changes": ["status"]}
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_task]
        mock_session.execute.return_value = mock_result
        
        response = client.get("/api/recent-activity")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        if data:  # If there are activities
            activity = data[0]
            assert "type" in activity
            assert "title" in activity
            assert "description" in activity
            assert "time" in activity
            assert "timestamp" in activity
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_pending_decisions(self, mock_get_session, client, mock_session):
        """Test GET /api/pending-decisions returns tasks needing review."""
        mock_get_session.return_value = mock_session
        
        # Mock pending tasks
        mock_task = MagicMock()
        mock_task.id = uuid4()
        mock_task.title = "Needs Review"
        mock_task.description = "Task description"
        mock_task.summary = None
        mock_task.status = TaskStatus.NEEDS_REVIEW
        mock_task.created_at = datetime.now(timezone.utc)
        mock_task.updated_at = datetime.now(timezone.utc)
        mock_task.due_date = None
        mock_task.completed_at = None
        mock_task.tags = ["urgent"]
        mock_task.person_emails = []
        mock_task.project_names = []
        mock_task.thread_id = None
        mock_task.comments = []
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_task]
        mock_session.execute.return_value = mock_result
        
        response = client.get("/api/pending-decisions")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        if data:
            task = data[0]
            assert task["needs_decision"] is True
            assert task["decision_type"] == "task_review"
            assert task["status"] == "needs_review"


class TestTaskEndpoints:
    """Test task CRUD endpoints."""
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_tasks(self, mock_get_session, client, mock_session):
        """Test GET /api/tasks returns list of tasks."""
        mock_get_session.return_value = mock_session
        
        # Mock tasks
        mock_task = MagicMock()
        mock_task.id = uuid4()
        mock_task.title = "Test Task"
        mock_task.description = "Description"
        mock_task.summary = None
        mock_task.status = TaskStatus.NEW
        mock_task.created_at = datetime.now(timezone.utc)
        mock_task.updated_at = datetime.now(timezone.utc)
        mock_task.due_date = None
        mock_task.completed_at = None
        mock_task.tags = ["test"]
        mock_task.person_emails = []
        mock_task.project_names = []
        mock_task.thread_id = None
        mock_task.comments = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_task]
        mock_session.execute.return_value = mock_result

        response = client.get("/api/tasks")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        if data:
            task = data[0]
            assert "id" in task
            assert "title" in task
            assert "status" in task
            assert "persons" in task  # API still returns this key for backward compatibility
            assert "projects" in task  # API still returns this key for backward compatibility
    
    @patch('backend.api.api_endpoints.get_cached_dashboard_data')
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_task_dashboard_with_tasks(self, mock_get_session, mock_get_cached_dashboard_data, client, mock_session):
        """Test GET /api/task-dashboard?include_tasks=true returns tasks organized by status."""
        mock_get_session.return_value = mock_session
        mock_get_cached_dashboard_data.return_value = None  # No cached data
        
        # Mock task count query
        mock_result_counts = MagicMock()
        mock_result_counts.all.return_value = [
            (TaskStatus.NEW, 0),
            (TaskStatus.IN_PROGRESS, 0),
            (TaskStatus.DONE, 0),
            (TaskStatus.NEEDS_REVIEW, 0)
        ]
        
        # Mock empty tasks result
        mock_result_tasks = MagicMock()
        mock_result_tasks.scalars.return_value.all.return_value = []
        
        # Configure the session to return different results for different queries
        mock_session.execute.side_effect = [mock_result_counts, mock_result_tasks, mock_result_tasks]
        
        response = client.get("/api/task-dashboard?include_tasks=true")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, dict)
        assert "tasks_by_status" in data
        assert data["tasks_by_status"] is not None
        
        # Should have all status keys
        for status in ["new", "user_input_received", "needs_review", "waiting", "in_progress", "done", "failed"]:
            assert status in data["tasks_by_status"]
            assert isinstance(data["tasks_by_status"][status], list)
    
    @patch('backend.api.api_endpoints.invalidate_task_cache')
    @patch('backend.api.api_endpoints.publish')
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_create_task(self, mock_get_session, mock_publish, mock_invalidate_cache, client, mock_session):
        """Test POST /api/tasks creates a new task."""
        mock_get_session.return_value = mock_session
        mock_publish.return_value = None
        
        sample_task_data = {
            "title": "Test Task",
            "description": "This is a test task",
            "status": "new",
            "tags": ["urgent", "backend"],
            "person_emails": [],
            "project_names": []
        }
        
        # Create a proper mock task that simulates database flush behavior
        mock_task = MagicMock()
        task_id = uuid4()
        now = datetime.now(timezone.utc)
        
        mock_task.id = task_id
        mock_task.title = sample_task_data["title"]
        mock_task.description = sample_task_data["description"]
        mock_task.summary = None
        mock_task.status = TaskStatus.NEW
        mock_task.created_at = now
        mock_task.updated_at = now
        mock_task.due_date = None
        mock_task.completed_at = None
        mock_task.tags = sample_task_data["tags"]
        mock_task.person_emails = []
        mock_task.project_names = []
        mock_task.thread_id = None
        
        # Mock the session methods to simulate proper database behavior
        def mock_add(obj):
            # Simulate flush setting the ID and timestamps
            obj.id = task_id
            obj.created_at = now
            obj.updated_at = now
        
        mock_session.add = mock_add
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        
        # Mock the Task constructor to return our mock
        with patch('backend.api.api_endpoints.Task', return_value=mock_task):
            response = client.post("/api/tasks", json=sample_task_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == "Test Task"
        assert data["status"] == "new"
        assert data["id"] == str(task_id)
        assert "created_at" in data
        assert "updated_at" in data
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_task_by_id(self, mock_get_session, client, mock_session):
        """Test GET /api/tasks/{id} returns specific task."""
        mock_get_session.return_value = mock_session
        
        task_id = uuid4()
        mock_task = MagicMock()
        mock_task.id = task_id
        mock_task.title = "Test Task"
        mock_task.description = "Description"
        mock_task.summary = None
        mock_task.status = TaskStatus.NEW
        mock_task.created_at = datetime.now(timezone.utc)
        mock_task.updated_at = datetime.now(timezone.utc)
        mock_task.due_date = None
        mock_task.completed_at = None
        mock_task.tags = []
        mock_task.person_emails = []
        mock_task.project_names = []
        mock_task.thread_id = None
        mock_task.comments = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result

        response = client.get(f"/api/tasks/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(task_id)
        assert data["title"] == "Test Task"
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_task_not_found(self, mock_get_session, client, mock_session):
        """Test GET /api/tasks/{id} with non-existent task returns 404."""
        mock_get_session.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        task_id = uuid4()
        response = client.get(f"/api/tasks/{task_id}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('backend.api.api_endpoints.invalidate_task_cache')
    @patch('backend.api.api_endpoints.publish')
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_update_task(self, mock_get_session, mock_publish, mock_invalidate_cache, client, mock_session):
        """Test PUT /api/tasks/{id} updates a task."""
        mock_get_session.return_value = mock_session
        mock_publish.return_value = None
        
        task_id = uuid4()
        mock_task = MagicMock()
        mock_task.id = task_id
        mock_task.title = "Original Title"
        mock_task.description = "Original Description"
        mock_task.summary = "Original Summary"  # Add this
        mock_task.status = TaskStatus.NEW
        mock_task.tags = []
        mock_task.task_metadata = {}
        mock_task.completed_at = None
        mock_task.person_emails = []
        mock_task.project_names = []
        mock_task.thread_id = None
        mock_task.comments = []
        mock_task.created_at = datetime.now(timezone.utc)
        mock_task.updated_at = datetime.now(timezone.utc)
        mock_task.due_date = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result
        mock_session.refresh = AsyncMock()
        
        update_data = {
            "title": "Updated Title",
            "status": "in_progress"
        }
        
        response = client.put(f"/api/tasks/{task_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Task should have been updated (mocked)
        assert "id" in data
    
    @patch('backend.api.api_endpoints.invalidate_task_cache')
    @patch('backend.api.api_endpoints.publish')
    @patch('backend.api.api_endpoints.cleanup_task_chat_data')
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_delete_task(self, mock_get_session, mock_cleanup, mock_publish, mock_invalidate_cache, client, mock_session):
        """Test DELETE /api/tasks/{id} deletes a task."""
        mock_get_session.return_value = mock_session
        mock_cleanup.return_value = None
        
        task_id = uuid4()
        mock_task = MagicMock()
        mock_task.id = task_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result
        
        response = client.delete(f"/api/tasks/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "deleted successfully" in data["message"]
        mock_cleanup.assert_called_once_with(str(task_id))


class TestTaskCommentsEndpoints:
    """Test task comment endpoints."""
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_task_comments(self, mock_get_session, client, mock_session):
        """Test GET /api/tasks/{id}/comments returns task comments."""
        mock_get_session.return_value = mock_session
        
        task_id = uuid4()
        mock_comment = MagicMock()
        mock_comment.id = uuid4()
        mock_comment.content = "Test comment"
        mock_comment.author = "user"
        mock_comment.created_at = datetime.now(timezone.utc)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_comment]
        mock_session.execute.return_value = mock_result
        
        response = client.get(f"/api/tasks/{task_id}/comments")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_add_task_comment(self, mock_get_session, client, mock_session):
        """Test POST /api/tasks/{id}/comments adds a comment."""
        mock_get_session.return_value = mock_session
        
        task_id = uuid4()
        mock_task = MagicMock()
        mock_task.status = TaskStatus.NEW
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()
        
        comment_data = {
            "content": "This is a test comment",
            "author": "user"
        }
        
        response = client.post(f"/api/tasks/{task_id}/comments", json=comment_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "added successfully" in data["message"]
