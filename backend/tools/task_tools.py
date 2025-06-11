"""
Task management LangChain tools.
"""

import json
from datetime import datetime
from typing import List
from uuid import UUID

from langchain.tools import StructuredTool
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from database.database import db_manager
from models.models import Task, TaskComment, TaskStatus, Person, Project
from .helpers import find_person_by_email, find_project_by_name, format_task_for_agent


async def create_task_tool(
    title: str,
    description: str,
    due_date: str = None,
    tags: List[str] = None,
    person_emails: List[str] = None,
    project_names: List[str] = None
) -> str:
    """Create a new task with optional relationships."""
    async with db_manager.get_session() as session:
        # Parse due date
        due_date_obj = None
        if due_date:
            try:
                due_date_obj = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        # Create task
        task = Task(
            title=title,
            description=description,
            due_date=due_date_obj,
            tags=tags or []
        )
        
        session.add(task)
        await session.flush()
        
        # Add person relationships
        if person_emails:
            for email in person_emails:
                person = await find_person_by_email(session, email)
                if person:
                    task.persons.append(person)
        
        # Add project relationships
        if project_names:
            for name in project_names:
                project = await find_project_by_name(session, name)
                if project:
                    task.projects.append(project)
        
        await session.commit()
        await session.refresh(task, ['persons', 'projects'])
        
        # Get comments count
        comments_count = await session.scalar(
            select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
        )
        
        formatted_task = await format_task_for_agent(task, comments_count or 0)
        return f"Task created successfully: {json.dumps(formatted_task, indent=2)}"


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
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔧 update_task_tool CALLED: task_id={task_id}, status={status}")
    print(f"[STDOUT] 🔧 update_task_tool CALLED: task_id={task_id}, status={status}", flush=True)
    
    async with db_manager.get_session() as session:
        try:
            task_id_uuid = UUID(task_id)
        except ValueError:
            return f"Error: Invalid task ID format: {task_id}"
        
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
            .where(Task.id == task_id_uuid)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            return f"Error: Task not found with ID: {task_id}"
        
        # Update fields
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if summary is not None:
            task.summary = summary
        if tags is not None:
            task.tags = tags
            
        # Update status
        if status:
            try:
                task.status = TaskStatus(status.lower())
                if task.status == TaskStatus.DONE and not task.completed_at:
                    task.completed_at = datetime.utcnow()
                elif task.status != TaskStatus.DONE:
                    task.completed_at = None
            except ValueError:
                return f"Error: Invalid status '{status}'. Valid options: {[s.value for s in TaskStatus]}"
        
        # Update due date
        if due_date:
            try:
                task.due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except ValueError:
                return f"Error: Invalid due_date format. Use ISO format."
        
        await session.commit()
        await session.refresh(task)
        
        logger.info(f"🔧 update_task_tool COMMITTED: task_id={task_id}, new_status={task.status.value}")
        print(f"[STDOUT] 🔧 update_task_tool COMMITTED: task_id={task_id}, new_status={task.status.value}", flush=True)
        
        # Get comments count
        comments_count = await session.scalar(
            select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
        )
        
        formatted_task = await format_task_for_agent(task, comments_count or 0)
        result_msg = f"Task updated successfully: {json.dumps(formatted_task, indent=2)}"
        logger.info(f"🔧 update_task_tool RETURNING: {result_msg[:100]}...")
        print(f"[STDOUT] 🔧 update_task_tool RETURNING: SUCCESS", flush=True)
        return result_msg


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