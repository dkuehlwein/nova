"""
Pydantic schemas for MCP tool parameters.
"""

from typing import List, Optional

from pydantic import BaseModel


class CreateTaskParams(BaseModel):
    title: str
    description: str
    due_date: Optional[str] = None  # ISO format
    tags: Optional[List[str]] = []
    person_emails: Optional[List[str]] = []  # Find by email
    project_names: Optional[List[str]] = []  # Find by name


class UpdateTaskParams(BaseModel):
    task_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    due_date: Optional[str] = None
    tags: Optional[List[str]] = None


class AddCommentParams(BaseModel):
    task_id: str
    content: str
    author: str = "nova"


class CreatePersonParams(BaseModel):
    name: str
    email: str
    role: Optional[str] = None
    description: Optional[str] = None
    current_focus: Optional[str] = None


class CreateProjectParams(BaseModel):
    name: str
    client: str
    booking_code: Optional[str] = None
    summary: Optional[str] = None


class SearchTasksParams(BaseModel):
    status: Optional[str] = None
    person_email: Optional[str] = None
    project_name: Optional[str] = None
    limit: int = 10 