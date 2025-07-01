"""
Nova Tasks Domain Models

Modern Pydantic V2 models for task-related API endpoints.
All models follow latest Pydantic V2 patterns with proper validation and serialization.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from models.models import TaskStatus


class TaskCreate(BaseModel):
    """Request model for creating new tasks."""
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    status: TaskStatus = Field(TaskStatus.NEW, description="Initial task status")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    tags: List[str] = Field(default_factory=list, description="Task tags")
    person_emails: List[str] = Field(default_factory=list, description="Assigned person email addresses")
    project_names: List[str] = Field(default_factory=list, description="Associated project names")


class TaskUpdate(BaseModel):
    """Request model for updating existing tasks."""
    title: Optional[str] = Field(None, description="Updated task title")
    description: Optional[str] = Field(None, description="Updated task description")
    status: Optional[TaskStatus] = Field(None, description="Updated task status")
    summary: Optional[str] = Field(None, description="Task summary")
    due_date: Optional[datetime] = Field(None, description="Updated due date")
    tags: Optional[List[str]] = Field(None, description="Updated tags")
    person_emails: Optional[List[str]] = Field(None, description="Updated person email addresses")
    project_names: Optional[List[str]] = Field(None, description="Updated project names")
    completed_at: Optional[datetime] = Field(None, description="Task completion timestamp")


class TaskCommentCreate(BaseModel):
    """Request model for creating task comments."""
    content: str = Field(..., description="Comment content")
    author: str = Field("user", description="Comment author")


class TaskResponse(BaseModel):
    """Response model for task data."""
    id: UUID = Field(..., description="Task ID")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    summary: Optional[str] = Field(None, description="Task summary")
    status: TaskStatus = Field(..., description="Task status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    tags: List[str] = Field(default_factory=list, description="Task tags")
    needs_decision: bool = Field(False, description="Whether task needs user decision")
    decision_type: Optional[str] = Field(None, description="Type of decision needed")
    
    # Related entities
    persons: List[str] = Field(default_factory=list, description="Assigned person names for UI")
    projects: List[str] = Field(default_factory=list, description="Associated project names for UI")
    comments_count: int = Field(0, description="Number of comments")

    model_config = ConfigDict(from_attributes=True) 