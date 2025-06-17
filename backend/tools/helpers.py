"""
Helper functions for MCP tools.
"""

import json
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.models import Person, Project, Task
from models.models import TaskStatus


async def find_person_by_email(session, email: str) -> Optional[Person]:
    """Find a person by email."""
    result = await session.execute(select(Person).where(Person.email == email))
    return result.scalar_one_or_none()


async def find_project_by_name(session, name: str) -> Optional[Project]:
    """Find a project by name."""
    result = await session.execute(select(Project).where(Project.name == name))
    return result.scalar_one_or_none()


async def format_task_for_agent(task: Task, comments_count: int = 0) -> Dict:
    """Format a task for agent consumption."""
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "summary": task.summary,
        "status": task.status.value,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "tags": task.tags or [],
        "persons": [{"name": p.name, "email": p.email} for p in task.persons],
        "projects": [{"name": p.name, "client": p.client} for p in task.projects],
        "comments_count": comments_count,
        "needs_decision": task.status == TaskStatus.NEEDS_REVIEW
    } 