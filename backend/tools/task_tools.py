"""
Task management LangChain tools.

Refactored to use API endpoint functions to avoid code duplication.
"""

import json
from datetime import datetime
from typing import List
from uuid import UUID

from langchain.tools import StructuredTool
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from database.database import db_manager
from models.models import Task, TaskComment, Person, Project
from models.models import TaskStatus
from utils.redis_manager import publish
from models.events import create_task_updated_event
from .helpers import find_person_by_email, find_project_by_name, format_task_for_agent
from api.api_endpoints import create_task as api_create_task, update_task as api_update_task, TaskCreate, TaskUpdate


async def create_task_tool(
    title: str,
    description: str,
    due_date: str = None,
    tags: List[str] = None,
    person_emails: List[str] = None,
    project_names: List[str] = None
) -> str:
    """Create a new task with optional relationships."""
    try:
        # Parse due date
        due_date_obj = None
        if due_date:
            try:
                due_date_obj = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        # Get person and project IDs (keep this logic since it's specific to email/name lookup)
        person_ids = []
        project_ids = []
        
        if person_emails:
            async with db_manager.get_session() as session:
                for email in person_emails:
                    person = await find_person_by_email(session, email)
                    if person:
                        person_ids.append(person.id)
        
        if project_names:
            async with db_manager.get_session() as session:
                for name in project_names:
                    project = await find_project_by_name(session, name)
                    if project:
                        project_ids.append(project.id)
        
        # Use the API endpoint function
        task_data = TaskCreate(
            title=title,
            description=description,
            due_date=due_date_obj,
            tags=tags or [],
            person_ids=person_ids,
            project_ids=project_ids
        )
        
        result = await api_create_task(task_data)
        
        # Fetch the actual Task object to use format_task_for_agent
        async with db_manager.get_session() as session:
            task_result = await session.execute(
                select(Task)
                .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
                .where(Task.id == result.id)
            )
            task = task_result.scalar_one()
            
            # Get comments count
            comments_count = await session.scalar(
                select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
            )
            
            formatted_task = await format_task_for_agent(task, comments_count or 0)
        
        return f"Task created successfully: {json.dumps(formatted_task, indent=2)}"
        
    except Exception as e:
        return f"Error creating task: {str(e)}"


async def update_task_tool(
    task_id: str,
    title: str = None,
    description: str = None,
    summary: str = None,
    status: str = None,
    due_date: str = None,
    tags: List[str] = None
) -> str:
    """Update an existing task."""
    try:
        task_id_uuid = UUID(task_id)
    except ValueError:
        return f"Error: Invalid task ID format: {task_id}"
    
    try:
        # Prepare update data
        update_data = {}
        
        if title is not None:
            update_data["title"] = title
        if description is not None:
            update_data["description"] = description
        if summary is not None:
            update_data["summary"] = summary
        if tags is not None:
            update_data["tags"] = tags
            
        # Handle status conversion
        if status:
            try:
                update_data["status"] = TaskStatus(status.lower())
            except ValueError:
                return f"Error: Invalid status '{status}'. Valid options: {[s.value for s in TaskStatus]}"
        
        # Handle due date
        if due_date:
            try:
                update_data["due_date"] = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except ValueError:
                return f"Error: Invalid due_date format. Use ISO format."
        
        # Store old status for event publishing
        old_status = None
        async with db_manager.get_session() as session:
            old_task_result = await session.execute(select(Task).where(Task.id == task_id_uuid))
            old_task = old_task_result.scalar_one_or_none()
            if old_task:
                old_status = old_task.status

        # Use the API endpoint function
        task_update = TaskUpdate(**update_data)
        result = await api_update_task(task_id_uuid, task_update)
        
        # Publish WebSocket event for real-time updates
        try:
            status_changed = "status" in update_data and old_status and old_status != result.status
            await publish(create_task_updated_event(
                task_id=str(result.id),
                status=result.status.value,
                action="status_changed" if status_changed else "updated",
                source="task-tool"
            ))
        except Exception as e:
            # Don't fail the operation if event publishing fails
            print(f"Warning: Failed to publish task update event: {e}")
        
        # Fetch the actual Task object to use format_task_for_agent
        async with db_manager.get_session() as session:
            task_result = await session.execute(
                select(Task)
                .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
                .where(Task.id == result.id)
            )
            task = task_result.scalar_one()
            
            # Get comments count
            comments_count = await session.scalar(
                select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
            )
            
            formatted_task = await format_task_for_agent(task, comments_count or 0)
        
        return f"Task updated successfully: {json.dumps(formatted_task, indent=2)}"
        
    except Exception as e:
        return f"Error updating task: {str(e)}"


async def get_tasks_tool(
    status: str = None,
    person_email: str = None,
    project_name: str = None,
    limit: int = 20
) -> str:
    """Get tasks with optional filtering."""
    async with db_manager.get_session() as session:
        query = select(Task).options(
            selectinload(Task.persons),
            selectinload(Task.projects),
            selectinload(Task.comments)
        )
        
        # Apply filters
        if status:
            try:
                status_enum = TaskStatus(status.lower())
                query = query.where(Task.status == status_enum)
            except ValueError:
                return f"Error: Invalid status '{status}'. Valid options: {[s.value for s in TaskStatus]}"
        
        # Filter by person email
        if person_email:
            person = await find_person_by_email(session, person_email)
            if person:
                query = query.join(Task.persons).where(Person.id == person.id)
            else:
                return f"Warning: Person with email '{person_email}' not found. Showing all tasks."
        
        # Filter by project name
        if project_name:
            project = await find_project_by_name(session, project_name)
            if project:
                query = query.join(Task.projects).where(Project.id == project.id)
            else:
                return f"Warning: Project with name '{project_name}' not found. Showing all tasks."
        
        query = query.order_by(Task.updated_at.desc()).limit(limit)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        
        formatted_tasks = []
        for task in tasks:
            # Get comments count for each task
            comments_count = await session.scalar(
                select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
            )
            formatted_tasks.append(await format_task_for_agent(task, comments_count or 0))
        
        return f"Found {len(formatted_tasks)} tasks: {json.dumps(formatted_tasks, indent=2)}"


async def get_task_by_id_tool(task_id: str) -> str:
    """Get a specific task by ID."""
    async with db_manager.get_session() as session:
        try:
            uuid_task_id = UUID(task_id)
        except ValueError:
            return f"Error: Invalid task ID format: {task_id}"
        
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
            .where(Task.id == uuid_task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            return f"Error: Task not found with ID: {task_id}"
        
        # Include comments
        comments = []
        for comment in task.comments:
            comments.append({
                "id": str(comment.id),
                "content": comment.content,
                "author": comment.author,
                "created_at": comment.created_at.isoformat()
            })
        
        formatted_task = await format_task_for_agent(task, len(comments))
        formatted_task["comments"] = comments
        
        return f"Task details: {json.dumps(formatted_task, indent=2)}"


async def add_task_comment_tool(
    task_id: str,
    content: str,
    author: str = "nova"
) -> str:
    """Add a comment to a task."""
    async with db_manager.get_session() as session:
        try:
            task_id_uuid = UUID(task_id)
        except ValueError:
            return f"Error: Invalid task ID format: {task_id}"
        
        # Verify task exists
        result = await session.execute(select(Task).where(Task.id == task_id_uuid))
        task = result.scalar_one_or_none()
        
        if not task:
            return f"Error: Task not found with ID: {task_id}"
        
        # Create comment
        comment = TaskComment(
            task_id=task_id_uuid,
            content=content,
            author=author
        )
        session.add(comment)
        
        await session.commit()
        
        return f"Comment added successfully to task '{task.title}'. Comment: {content}"


async def get_pending_decisions_tool() -> str:
    """Get tasks that need user decisions."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
            .where(Task.status == TaskStatus.NEEDS_REVIEW)
            .order_by(Task.updated_at.desc())
        )
        tasks = result.scalars().all()
        
        formatted_tasks = []
        for task in tasks:
            # Get comments count for each task
            comments_count = await session.scalar(
                select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
            )
            formatted_tasks.append(await format_task_for_agent(task, comments_count or 0))
        
        return f"Found {len(formatted_tasks)} tasks needing decisions: {json.dumps(formatted_tasks, indent=2)}"


def get_task_tools() -> List[StructuredTool]:
    """Get task management LangChain tools."""
    return [
        StructuredTool.from_function(
            func=create_task_tool,
            name="create_task",
            description="Create a new task with optional person and project relationships",
            coroutine=create_task_tool
        ),
        StructuredTool.from_function(
            func=update_task_tool,
            name="update_task", 
            description="Update an existing task (status, description, etc.)",
            coroutine=update_task_tool
        ),
        StructuredTool.from_function(
            func=get_tasks_tool,
            name="get_tasks",
            description="Get tasks with optional filtering by status, person, or project",
            coroutine=get_tasks_tool
        ),
        StructuredTool.from_function(
            func=get_task_by_id_tool,
            name="get_task_by_id",
            description="Get detailed information about a specific task by ID",
            coroutine=get_task_by_id_tool
        ),
        StructuredTool.from_function(
            func=add_task_comment_tool,
            name="add_task_comment",
            description="Add a comment to a task and optionally update its status",
            coroutine=add_task_comment_tool
        ),
        StructuredTool.from_function(
            func=get_pending_decisions_tool,
            name="get_pending_decisions",
            description="Get all tasks that need user review/decisions",
            coroutine=get_pending_decisions_tool
        ),
    ] 