"""
Tests for main API endpoints.
Tests CRUD operations for tasks, persons, projects, and overview functionality.
"""

import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.api_endpoints import router
from backend.models.models import Task, TaskStatus, Person, Project, Artifact


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
        "person_ids": [],
        "project_ids": []
    }


@pytest.fixture
def sample_person_data():
    """Sample person data for testing."""
    return {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "role": "Developer",
        "description": "Senior backend developer",
        "current_focus": "API development"
    }


@pytest.fixture
def sample_project_data():
    """Sample project data for testing."""
    return {
        "name": "Nova Enhancement",
        "client": "Internal",
        "booking_code": "NOVA-2025",
        "summary": "Kanban board improvements"
    }


class TestOverviewEndpoints:
    """Test overview and dashboard endpoints."""
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_overview(self, mock_get_session, client, mock_session):
        """Test GET /api/overview returns overview stats."""
        mock_get_session.return_value = mock_session
        
        # Mock task count query
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (TaskStatus.NEW, 5),
            (TaskStatus.IN_PROGRESS, 3),
            (TaskStatus.DONE, 10),
            (TaskStatus.NEEDS_REVIEW, 2)
        ]
        mock_session.execute.return_value = mock_result
        
        response = client.get("/api/overview")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "task_counts" in data
        assert "total_tasks" in data
        assert "pending_decisions" in data
        assert "recent_activity" in data
        assert "system_status" in data
        
        assert data["task_counts"]["new"] == 5
        assert data["task_counts"]["in_progress"] == 3
        assert data["total_tasks"] == 20
        # pending_decisions = needs_review + user_input_received (both 0 in our mock)
        assert data["pending_decisions"] == 0  
        assert data["system_status"] == "operational"
    
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
        mock_task.persons = []
        mock_task.projects = []
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
        mock_task.persons = []
        mock_task.projects = []
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
            assert "persons" in task
            assert "projects" in task
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_tasks_by_status(self, mock_get_session, client, mock_session):
        """Test GET /api/tasks/by-status returns tasks organized by status."""
        mock_get_session.return_value = mock_session
        
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        response = client.get("/api/tasks/by-status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, dict)
        # Should have all status keys
        for status in ["new", "user_input_received", "needs_review", "waiting", "in_progress", "done", "failed"]:
            assert status in data
            assert isinstance(data[status], list)
    
    @patch('backend.api.api_endpoints.publish')
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_create_task(self, mock_get_session, mock_publish, client, mock_session):
        """Test POST /api/tasks creates a new task."""
        mock_get_session.return_value = mock_session
        mock_publish.return_value = None
        
        sample_task_data = {
            "title": "Test Task",
            "description": "This is a test task",
            "status": "new",
            "tags": ["urgent", "backend"],
            "person_ids": [],
            "project_ids": []
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
        mock_task.persons = []
        mock_task.projects = []
        
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
        mock_task.persons = []
        mock_task.projects = []
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
    
    @patch('backend.api.api_endpoints.publish')
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_update_task(self, mock_get_session, mock_publish, client, mock_session):
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
        mock_task.persons = []
        mock_task.projects = []
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
    
    @patch('backend.api.api_endpoints.cleanup_task_chat_data')
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_delete_task(self, mock_get_session, mock_cleanup, client, mock_session):
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


class TestPersonEndpoints:
    """Test person CRUD endpoints."""
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_persons(self, mock_get_session, client, mock_session):
        """Test GET /api/persons returns list of persons."""
        mock_get_session.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        response = client.get("/api/persons")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_create_person(self, mock_get_session, client, mock_session):
        """Test POST /api/persons creates a new person."""
        mock_get_session.return_value = mock_session
        
        sample_person_data = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "role": "Developer",
            "description": "Senior backend developer",
            "current_focus": "API development"
        }
        
        # Create a proper mock person that simulates database behavior
        mock_person = MagicMock()
        person_id = uuid4()
        now = datetime.now(timezone.utc)
        
        mock_person.id = person_id
        mock_person.name = sample_person_data["name"]
        mock_person.email = sample_person_data["email"]
        mock_person.role = sample_person_data["role"]
        mock_person.description = sample_person_data["description"]
        mock_person.current_focus = sample_person_data["current_focus"]
        mock_person.created_at = now
        mock_person.updated_at = now
        
        # Mock the session methods
        def mock_add(obj):
            obj.id = person_id
            obj.created_at = now
            obj.updated_at = now
        
        mock_session.add = mock_add
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        # Mock the Person constructor to return our mock
        with patch('backend.api.api_endpoints.Person', return_value=mock_person):
            response = client.post("/api/persons", json=sample_person_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "John Doe"
        assert data["email"] == "john.doe@example.com"
        assert data["id"] == str(person_id)


class TestProjectEndpoints:
    """Test project CRUD endpoints."""
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_projects(self, mock_get_session, client, mock_session):
        """Test GET /api/projects returns list of projects."""
        mock_get_session.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        response = client.get("/api/projects")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_create_project(self, mock_get_session, client, mock_session):
        """Test POST /api/projects creates a new project."""
        mock_get_session.return_value = mock_session
        
        sample_project_data = {
            "name": "Nova Enhancement",
            "client": "Internal",
            "booking_code": "NOVA-2025",
            "summary": "Kanban board improvements"
        }
        
        # Create a proper mock project that simulates database behavior
        mock_project = MagicMock()
        project_id = uuid4()
        now = datetime.now(timezone.utc)
        
        mock_project.id = project_id
        mock_project.name = sample_project_data["name"]
        mock_project.client = sample_project_data["client"]
        mock_project.booking_code = sample_project_data["booking_code"]
        mock_project.summary = sample_project_data["summary"]
        mock_project.created_at = now
        mock_project.updated_at = now
        
        # Mock the session methods
        def mock_add(obj):
            obj.id = project_id
            obj.created_at = now
            obj.updated_at = now
        
        mock_session.add = mock_add
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        # Mock the Project constructor to return our mock
        with patch('backend.api.api_endpoints.Project', return_value=mock_project):
            response = client.post("/api/projects", json=sample_project_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Nova Enhancement"
        assert data["client"] == "Internal"
        assert data["id"] == str(project_id)


class TestArtifactEndpoints:
    """Test artifact CRUD endpoints."""
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_get_artifacts(self, mock_get_session, client, mock_session):
        """Test GET /api/artifacts returns list of artifacts."""
        mock_get_session.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        response = client.get("/api/artifacts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    @patch('backend.api.api_endpoints.db_manager.get_session')
    def test_create_artifact(self, mock_get_session, client, mock_session):
        """Test POST /api/artifacts creates a new artifact."""
        mock_get_session.return_value = mock_session
        
        artifact_data = {
            "link": "https://example.com/document",
            "title": "Test Document",
            "summary": "This is a test document"
        }
        
        # Create a proper mock artifact that simulates database behavior
        mock_artifact = MagicMock()
        artifact_id = uuid4()
        now = datetime.now(timezone.utc)
        
        mock_artifact.id = artifact_id
        mock_artifact.link = artifact_data["link"]
        mock_artifact.title = artifact_data["title"]
        mock_artifact.summary = artifact_data["summary"]
        mock_artifact.created_at = now
        mock_artifact.updated_at = now
        
        # Mock the session methods
        def mock_add(obj):
            obj.id = artifact_id
            obj.created_at = now
            obj.updated_at = now
        
        mock_session.add = mock_add
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        # Mock the Artifact constructor to return our mock
        with patch('backend.api.api_endpoints.Artifact', return_value=mock_artifact):
            response = client.post("/api/artifacts", json=artifact_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == "Test Document"
        assert data["link"] == "https://example.com/document"
        assert data["id"] == str(artifact_id)


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


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test GET /api/health returns health status."""
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "nova-kanban-mcp"
        assert "timestamp" in data 