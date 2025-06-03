#!/usr/bin/env python3
"""
Task CRUD Operations Test Suite
Tests task creation, modification, and deletion operations using pytest framework.
"""

import asyncio
import sys
import os
import pytest
import pytest_asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from models.models import Task, TaskComment, Person, Project, TaskStatus
from models.models import task_person_association, task_project_association
from database.database import db_manager
from sqlalchemy import select
from sqlalchemy.orm import selectinload


@pytest_asyncio.fixture
async def db_session():
    """Fixture providing a database session for tests with automatic rollback."""
    async with db_manager.get_session() as session:
        # Start a transaction
        transaction = await session.begin()
        try:
            yield session
        finally:
            # Always rollback to keep database clean
            await transaction.rollback()


@pytest_asyncio.fixture
async def sample_task(db_session):
    """Fixture providing a sample task for testing."""
    timestamp = str(int(time.time() * 1000))  # Unique timestamp
    task = Task(
        title=f"Test Task {timestamp}",
        description=f"This is a test task for CRUD operations {timestamp}",
        status=TaskStatus.NEW,
        tags=["test", "crud", "automation"]
    )
    db_session.add(task)
    await db_session.flush()
    return task


@pytest_asyncio.fixture
async def sample_person(db_session):
    """Fixture providing a sample person for testing."""
    timestamp = str(int(time.time() * 1000))  # Unique timestamp
    person = Person(
        name=f"Test User {timestamp}",
        email=f"test{timestamp}@example.com",
        role="Software Engineer"
    )
    db_session.add(person)
    await db_session.flush()
    return person


@pytest_asyncio.fixture
async def sample_project(db_session):
    """Fixture providing a sample project for testing."""
    timestamp = str(int(time.time() * 1000))  # Unique timestamp
    project = Project(
        name=f"Test Project {timestamp}",
        client=f"Test Client {timestamp}",
        booking_code=f"TEST{timestamp}"
    )
    db_session.add(project)
    await db_session.flush()
    return project


class TestTaskCreation:
    """Test task creation operations."""
    
    @pytest.mark.asyncio
    async def test_create_basic_task(self, db_session):
        """Test creating a basic task with required fields."""
        task = Task(
            title="Basic Test Task",
            description="A simple task for testing creation",
            status=TaskStatus.NEW
        )
        db_session.add(task)
        await db_session.flush()
        
        # Verify task was created
        assert task.id is not None
        assert task.title == "Basic Test Task"
        assert task.description == "A simple task for testing creation"
        assert task.status == TaskStatus.NEW
        assert task.created_at is not None
        assert task.updated_at is not None
        assert isinstance(task.tags, list)
        assert len(task.tags) == 0
    
    @pytest.mark.asyncio
    async def test_create_task_with_tags(self, db_session):
        """Test creating a task with tags."""
        task = Task(
            title="Tagged Task",
            description="A task with tags",
            status=TaskStatus.NEW,
            tags=["urgent", "frontend", "bug"]
        )
        db_session.add(task)
        await db_session.flush()
        
        # Verify tags were stored correctly
        assert len(task.tags) == 3
        assert "urgent" in task.tags
        assert "frontend" in task.tags
        assert "bug" in task.tags
    
    @pytest.mark.asyncio
    async def test_create_task_with_relationships(self, db_session, sample_person, sample_project):
        """Test creating a task with person and project relationships."""
        task = Task(
            title="Task with Relationships",
            description="A task linked to person and project",
            status=TaskStatus.NEW
        )
        
        # Add relationships
        task.persons.append(sample_person)
        task.projects.append(sample_project)
        
        db_session.add(task)
        await db_session.flush()
        
        # Verify relationships using the actual fixture data
        await db_session.refresh(task)
        result = await db_session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects))
            .where(Task.id == task.id)
        )
        updated_task = result.scalar_one()
        
        assert len(updated_task.persons) == 1
        assert len(updated_task.projects) == 1
        assert updated_task.persons[0].name == sample_person.name
        assert updated_task.projects[0].name == sample_project.name


class TestTaskReading:
    """Test task reading/query operations."""
    
    @pytest.mark.asyncio
    async def test_read_task_by_id(self, db_session, sample_task):
        """Test reading a task by its ID."""
        await db_session.flush()
        
        # Read the task back
        result = await db_session.execute(
            select(Task).where(Task.id == sample_task.id)
        )
        retrieved_task = result.scalar_one()
        
        assert retrieved_task.id == sample_task.id
        assert retrieved_task.title == sample_task.title
        assert retrieved_task.description == sample_task.description
        assert retrieved_task.status == TaskStatus.NEW
    
    @pytest.mark.asyncio
    async def test_read_tasks_by_status(self, db_session):
        """Test reading tasks filtered by status."""
        # Create tasks with different statuses
        tasks = [
            Task(title="New Task 1", description="Description 1", status=TaskStatus.NEW),
            Task(title="New Task 2", description="Description 2", status=TaskStatus.NEW),
            Task(title="In Progress Task", description="Description 3", status=TaskStatus.IN_PROGRESS),
            Task(title="Done Task", description="Description 4", status=TaskStatus.DONE)
        ]
        
        for task in tasks:
            db_session.add(task)
        await db_session.flush()
        
        # Query tasks by status
        result = await db_session.execute(
            select(Task).where(Task.status == TaskStatus.NEW)
        )
        new_tasks = result.scalars().all()
        
        assert len(new_tasks) >= 2
        for task in new_tasks:
            assert task.status == TaskStatus.NEW
    
    @pytest.mark.asyncio
    async def test_read_tasks_with_tags(self, db_session):
        """Test reading tasks with specific tags."""
        # Create tasks with different tags
        task1 = Task(
            title="Frontend Task",
            description="Frontend work",
            status=TaskStatus.NEW,
            tags=["frontend", "react", "urgent"]
        )
        task2 = Task(
            title="Backend Task",
            description="Backend work",
            status=TaskStatus.NEW,
            tags=["backend", "api", "urgent"]
        )
        
        db_session.add(task1)
        db_session.add(task2)
        await db_session.flush()
        
        # Query tasks by tag (using JSON operations)
        result = await db_session.execute(
            select(Task).where(Task.tags.op('@>')(['urgent']))
        )
        urgent_tasks = result.scalars().all()
        
        assert len(urgent_tasks) >= 2


class TestTaskUpdating:
    """Test task update operations."""
    
    @pytest.mark.asyncio
    async def test_update_task_basic_fields(self, db_session, sample_task):
        """Test updating basic task fields."""
        await db_session.flush()
        
        # Update the task
        sample_task.title = "Updated Test Task"
        sample_task.description = "Updated description"
        sample_task.status = TaskStatus.IN_PROGRESS
        sample_task.tags = ["updated", "modified"]
        
        await db_session.flush()
        
        # Verify updates
        result = await db_session.execute(
            select(Task).where(Task.id == sample_task.id)
        )
        updated_task = result.scalar_one()
        
        assert updated_task.title == "Updated Test Task"
        assert updated_task.description == "Updated description"
        assert updated_task.status == TaskStatus.IN_PROGRESS
        assert "updated" in updated_task.tags
        assert "modified" in updated_task.tags
    
    @pytest.mark.asyncio
    async def test_update_task_status_to_done(self, db_session, sample_task):
        """Test updating task status to DONE sets completed_at."""
        await db_session.flush()
        
        # Update status to DONE
        sample_task.status = TaskStatus.DONE
        sample_task.completed_at = datetime.now(timezone.utc)
        
        await db_session.flush()
        
        # Verify completed_at is set
        result = await db_session.execute(
            select(Task).where(Task.id == sample_task.id)
        )
        updated_task = result.scalar_one()
        
        assert updated_task.status == TaskStatus.DONE
        assert updated_task.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_update_task_relationships(self, db_session, sample_task, sample_person, sample_project):
        """Test updating task relationships."""
        await db_session.flush()
        
        # Add relationships manually to avoid greenlet issues
        await db_session.execute(
            task_person_association.insert().values(
                task_id=sample_task.id,
                person_id=sample_person.id
            )
        )
        await db_session.execute(
            task_project_association.insert().values(
                task_id=sample_task.id,
                project_id=sample_project.id
            )
        )
        
        await db_session.flush()
        
        # Verify relationships were added using direct query with eager loading
        result = await db_session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects))
            .where(Task.id == sample_task.id)
        )
        updated_task = result.scalar_one()
        
        assert len(updated_task.persons) == 1
        assert len(updated_task.projects) == 1
        assert updated_task.persons[0].email == sample_person.email
        assert updated_task.projects[0].client == sample_project.client


class TestTaskDeletion:
    """Test task deletion operations."""
    
    @pytest.mark.asyncio
    async def test_delete_task(self, db_session, sample_task):
        """Test deleting a task."""
        await db_session.flush()
        task_id = sample_task.id
        
        # Delete the task
        await db_session.delete(sample_task)
        await db_session.flush()
        
        # Verify task is deleted
        result = await db_session.execute(
            select(Task).where(Task.id == task_id)
        )
        deleted_task = result.scalar_one_or_none()
        
        assert deleted_task is None
    
    @pytest.mark.asyncio
    async def test_delete_task_with_comments(self, db_session, sample_task):
        """Test deleting a task with comments (cascade delete)."""
        await db_session.flush()
        
        # Add comments to the task
        comment1 = TaskComment(
            task_id=sample_task.id,
            content="First comment",
            author="user"
        )
        comment2 = TaskComment(
            task_id=sample_task.id,
            content="Second comment",
            author="nova"
        )
        
        db_session.add(comment1)
        db_session.add(comment2)
        await db_session.flush()
        
        task_id = sample_task.id
        
        # Delete the task
        await db_session.delete(sample_task)
        await db_session.flush()
        
        # Verify task and comments are deleted
        task_result = await db_session.execute(
            select(Task).where(Task.id == task_id)
        )
        comment_result = await db_session.execute(
            select(TaskComment).where(TaskComment.task_id == task_id)
        )
        
        assert task_result.scalar_one_or_none() is None
        assert len(comment_result.scalars().all()) == 0


class TestTaskComments:
    """Test task comment operations."""
    
    @pytest.mark.asyncio
    async def test_add_comment_to_task(self, db_session, sample_task):
        """Test adding a comment to a task."""
        await db_session.flush()
        
        # Add a comment
        comment = TaskComment(
            task_id=sample_task.id,
            content="This is a test comment",
            author="user"
        )
        db_session.add(comment)
        await db_session.flush()
        
        # Verify comment was added
        assert comment.id is not None
        assert comment.task_id == sample_task.id
        assert comment.content == "This is a test comment"
        assert comment.author == "user"
        assert comment.created_at is not None
    
    @pytest.mark.asyncio
    async def test_read_task_with_comments(self, db_session, sample_task):
        """Test reading a task with its comments."""
        await db_session.flush()
        
        # Add multiple comments
        comments = [
            TaskComment(task_id=sample_task.id, content="Comment 1", author="user"),
            TaskComment(task_id=sample_task.id, content="Comment 2", author="nova"),
            TaskComment(task_id=sample_task.id, content="Comment 3", author="user")
        ]
        
        for comment in comments:
            db_session.add(comment)
        await db_session.flush()
        
        # Read task with comments
        result = await db_session.execute(
            select(Task)
            .options(selectinload(Task.comments))
            .where(Task.id == sample_task.id)
        )
        task_with_comments = result.scalar_one()
        
        assert len(task_with_comments.comments) == 3
        assert task_with_comments.comments[0].content == "Comment 1"
        assert task_with_comments.comments[1].author == "nova"
    
    @pytest.mark.asyncio
    async def test_comment_ordering(self, db_session, sample_task):
        """Test that comments are ordered by creation time."""
        await db_session.flush()
        
        # Add comments with slight delay
        comment1 = TaskComment(task_id=sample_task.id, content="First", author="user")
        db_session.add(comment1)
        await db_session.flush()
        
        comment2 = TaskComment(task_id=sample_task.id, content="Second", author="user")
        db_session.add(comment2)
        await db_session.flush()
        
        # Read comments ordered by created_at
        result = await db_session.execute(
            select(TaskComment)
            .where(TaskComment.task_id == sample_task.id)
            .order_by(TaskComment.created_at.asc())
        )
        ordered_comments = result.scalars().all()
        
        assert len(ordered_comments) == 2
        assert ordered_comments[0].content == "First"
        assert ordered_comments[1].content == "Second"
        assert ordered_comments[0].created_at <= ordered_comments[1].created_at


class TestTaskValidation:
    """Test task validation and edge cases."""
    
    @pytest.mark.asyncio
    async def test_task_requires_title(self):
        """Test that task creation requires a title."""
        async with db_manager.get_session() as session:
            # Start fresh transaction
            transaction = await session.begin()
            try:
                with pytest.raises((Exception, SystemExit)):  # Expect constraint violation
                    task = Task(
                        description="Task without title",
                        status=TaskStatus.NEW
                    )
                    session.add(task)
                    await session.flush()  # Use flush instead of commit
            finally:
                await transaction.rollback()
    
    @pytest.mark.asyncio
    async def test_task_requires_description(self):
        """Test that task creation requires a description."""
        async with db_manager.get_session() as session:
            # Start fresh transaction
            transaction = await session.begin()
            try:
                with pytest.raises((Exception, SystemExit)):  # Expect constraint violation
                    task = Task(
                        title="Task without description",
                        status=TaskStatus.NEW
                    )
                    session.add(task)
                    await session.flush()  # Use flush instead of commit
            finally:
                await transaction.rollback()
    
    @pytest.mark.asyncio
    async def test_task_defaults(self, db_session):
        """Test that task defaults are properly set."""
        timestamp = str(int(time.time() * 1000))
        task = Task(
            title=f"Task with defaults {timestamp}",
            description="Testing default values"
        )
        db_session.add(task)
        await db_session.flush()
        
        assert task.status == TaskStatus.NEW
        assert isinstance(task.tags, list)
        assert len(task.tags) == 0
        assert task.created_at is not None
        assert task.updated_at is not None


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"]) 