"""
Task management LangChain tools.

Updated to use memory-based person/project references instead of database foreign keys.
Tasks store email/name strings and use memory for context lookup.
"""

import json
from datetime import datetime
from typing import List
from uuid import UUID

from langchain.tools import StructuredTool
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from database.database import db_manager
from models.models import Task, TaskComment
from models.models import TaskStatus
from utils.redis_manager import publish
from models.events import create_task_updated_event
from api.api_endpoints import create_task as api_create_task, update_task as api_update_task, TaskCreate, TaskUpdate


def format_task_for_agent(task: Task, comments_count: int = 0) -> dict:
    """Format task for agent consumption with person emails and project names."""
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
        "tags": task.tags,
        "person_emails": task.person_emails or [],  # List of email strings
        "project_names": task.project_names or [],  # List of project name strings
        "comments_count": comments_count,
        "task_metadata": task.task_metadata
    }


async def create_task_tool(
    title: str,
    description: str,
    due_date: str = None,
    tags: List[str] = None,
    person_emails: List[str] = None,
    project_names: List[str] = None
) -> str:
    """Create a new task with optional person/project references."""
    try:
        # Parse due date
        due_date_obj = None
        if due_date:
            try:
                due_date_obj = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        # Use the API endpoint function with string-based relationships
        task_data = TaskCreate(
            title=title,
            description=description,
            due_date=due_date_obj,
            tags=tags or [],
            person_emails=person_emails or [],
            project_names=project_names or []
        )
        
        result = await api_create_task(task_data)
        
        # Fetch the actual Task object for formatting
        async with db_manager.get_session() as session:
            task_result = await session.execute(
                select(Task).where(Task.id == result.id)
            )
            task = task_result.scalar_one()
            
            # Get comments count
            comments_count = await session.scalar(
                select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
            )
            
            formatted_task = format_task_for_agent(task, comments_count or 0)
        
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
    tags: List[str] = None,
    person_emails: List[str] = None,
    project_names: List[str] = None,
    comment: str = None
) -> str:
    """Update an existing task. Status must be one of: 'todo', 'in_progress', 'done', 'needs_review', 'error'.
    
    IMPORTANT: Always call this tool with status='done' and a comment summarizing what was achieved when you complete a task.
    
    Args:
        comment: Optional comment to add to the task. Use this to document what was accomplished, especially when marking tasks as 'done'.
    """
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
        if person_emails is not None:
            update_data["person_emails"] = person_emails
        if project_names is not None:
            update_data["project_names"] = project_names
            
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
        
        # Add comment if provided
        if comment:
            try:
                comment_obj = TaskComment(
                    task_id=task_id_uuid,
                    content=comment,
                    author="nova"
                )
                async with db_manager.get_session() as session:
                    session.add(comment_obj)
                    await session.commit()
            except Exception as e:
                # Don't fail the update if comment creation fails
                print(f"Warning: Failed to add comment to task {task_id}: {e}")
        
        # Fetch the actual Task object for formatting
        async with db_manager.get_session() as session:
            task_result = await session.execute(
                select(Task).where(Task.id == result.id)
            )
            task = task_result.scalar_one()
            
            # Get comments count
            comments_count = await session.scalar(
                select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
            )
            
            formatted_task = format_task_for_agent(task, comments_count or 0)
        
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
        query = select(Task)
        
        # Apply filters
        if status:
            try:
                status_enum = TaskStatus(status.lower())
                query = query.where(Task.status == status_enum)
            except ValueError:
                return f"Error: Invalid status '{status}'. Valid options: {[s.value for s in TaskStatus]}"
        
        # Filter by person email (using JSON contains)
        if person_email:
            query = query.where(Task.person_emails.contains([person_email]))
        
        # Filter by project name (using JSON contains)
        if project_name:
            query = query.where(Task.project_names.contains([project_name]))
        
        query = query.order_by(Task.updated_at.desc()).limit(limit)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        
        formatted_tasks = []
        for task in tasks:
            # Get comments count for each task
            comments_count = await session.scalar(
                select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
            )
            formatted_tasks.append(format_task_for_agent(task, comments_count or 0))
        
        return f"Found {len(formatted_tasks)} tasks: {json.dumps(formatted_tasks, indent=2)}"


async def get_task_by_id_tool(task_id: str) -> str:
    """Retrieve details of a specific task using its UUID. Only use when you have a valid task ID from previous operations (not for searching tasks)."""
    async with db_manager.get_session() as session:
        try:
            uuid_task_id = UUID(task_id)
        except ValueError:
            return f"Error: Invalid task ID format: {task_id}"
        
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.comments))
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
        
        formatted_task = format_task_for_agent(task, len(comments))
        formatted_task["comments"] = comments
        
        return f"Task details: {json.dumps(formatted_task, indent=2)}"




def get_task_tools() -> List[StructuredTool]:
    """Get task management LangChain tools."""
    return [
        StructuredTool.from_function(
            func=create_task_tool,
            name="create_task",
            coroutine=create_task_tool
        ),
        StructuredTool.from_function(
            func=update_task_tool,
            name="update_task", 
            coroutine=update_task_tool
        ),
        StructuredTool.from_function(
            func=get_tasks_tool,
            name="get_tasks",
            coroutine=get_tasks_tool
        ),
        StructuredTool.from_function(
            func=get_task_by_id_tool,
            name="get_task_by_id",
            coroutine=get_task_by_id_tool
        ),
    ] 