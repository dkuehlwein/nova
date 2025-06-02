"""
Task management MCP tools.
"""

import json
from datetime import datetime
from typing import List
from uuid import UUID

from fastmcp.tools import Tool
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import db_manager
from models import Task, TaskComment, TaskStatus
from .helpers import find_person_by_email, find_project_by_name, format_task_for_agent
from .schemas import CreateTaskParams, UpdateTaskParams, AddCommentParams, SearchTasksParams


async def create_task_tool(params: CreateTaskParams) -> str:
    """Create a new task with optional relationships."""
    async with db_manager.get_session() as session:
        # Parse due date
        due_date = None
        if params.due_date:
            try:
                due_date = datetime.fromisoformat(params.due_date.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        # Create task
        task = Task(
            title=params.title,
            description=params.description,
            due_date=due_date,
            tags=params.tags or []
        )
        
        session.add(task)
        await session.flush()
        
        # Add person relationships
        if params.person_emails:
            for email in params.person_emails:
                person = await find_person_by_email(session, email)
                if person:
                    task.persons.append(person)
        
        # Add project relationships
        if params.project_names:
            for name in params.project_names:
                project = await find_project_by_name(session, name)
                if project:
                    task.projects.append(project)
        
        await session.commit()
        await session.refresh(task, ['persons', 'projects'])
        
        formatted_task = await format_task_for_agent(task)
        return f"Task created successfully: {json.dumps(formatted_task, indent=2)}"


async def update_task_tool(params: UpdateTaskParams) -> str:
    """Update an existing task."""
    async with db_manager.get_session() as session:
        try:
            task_id = UUID(params.task_id)
        except ValueError:
            return f"Error: Invalid task ID format: {params.task_id}"
        
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
            .where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            return f"Error: Task not found with ID: {params.task_id}"
        
        # Update fields
        if params.title is not None:
            task.title = params.title
        if params.description is not None:
            task.description = params.description
        if params.summary is not None:
            task.summary = params.summary
        if params.tags is not None:
            task.tags = params.tags
            
        # Update status
        if params.status:
            try:
                task.status = TaskStatus(params.status.lower())
                if task.status == TaskStatus.DONE and not task.completed_at:
                    task.completed_at = datetime.utcnow()
                elif task.status != TaskStatus.DONE:
                    task.completed_at = None
            except ValueError:
                return f"Error: Invalid status '{params.status}'. Valid options: {[s.value for s in TaskStatus]}"
        
        # Update due date
        if params.due_date:
            try:
                task.due_date = datetime.fromisoformat(params.due_date.replace('Z', '+00:00'))
            except ValueError:
                return f"Error: Invalid due_date format. Use ISO format."
        
        await session.commit()
        await session.refresh(task)
        
        formatted_task = await format_task_for_agent(task)
        return f"Task updated successfully: {json.dumps(formatted_task, indent=2)}"


async def get_tasks_tool(params: SearchTasksParams) -> str:
    """Get tasks with optional filtering."""
    async with db_manager.get_session() as session:
        query = select(Task).options(
            selectinload(Task.persons),
            selectinload(Task.projects),
            selectinload(Task.comments)
        )
        
        # Apply filters
        if params.status:
            try:
                status = TaskStatus(params.status.lower())
                query = query.where(Task.status == status)
            except ValueError:
                return f"Error: Invalid status '{params.status}'. Valid options: {[s.value for s in TaskStatus]}"
        
        # Filter by person email
        if params.person_email:
            person = await find_person_by_email(session, params.person_email)
            if person:
                query = query.join(Task.persons).where(Person.id == person.id)
            else:
                return f"Warning: Person with email '{params.person_email}' not found. Showing all tasks."
        
        # Filter by project name
        if params.project_name:
            project = await find_project_by_name(session, params.project_name)
            if project:
                query = query.join(Task.projects).where(Project.id == project.id)
            else:
                return f"Warning: Project with name '{params.project_name}' not found. Showing all tasks."
        
        query = query.order_by(Task.updated_at.desc()).limit(params.limit)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        
        formatted_tasks = []
        for task in tasks:
            formatted_tasks.append(await format_task_for_agent(task))
        
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
        
        formatted_task = await format_task_for_agent(task)
        
        # Include comments
        comments = []
        for comment in task.comments:
            comments.append({
                "id": str(comment.id),
                "content": comment.content,
                "author": comment.author,
                "created_at": comment.created_at.isoformat()
            })
        
        formatted_task["comments"] = comments
        
        return f"Task details: {json.dumps(formatted_task, indent=2)}"


async def add_task_comment_tool(params: AddCommentParams) -> str:
    """Add a comment to a task."""
    async with db_manager.get_session() as session:
        try:
            task_id = UUID(params.task_id)
        except ValueError:
            return f"Error: Invalid task ID format: {params.task_id}"
        
        # Verify task exists
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        
        if not task:
            return f"Error: Task not found with ID: {params.task_id}"
        
        # Create comment
        comment = TaskComment(
            task_id=task_id,
            content=params.content,
            author=params.author
        )
        session.add(comment)
        
        # Update task status based on comment author
        if params.author == "user" and task.status in [TaskStatus.NEEDS_REVIEW, TaskStatus.WAITING]:
            task.status = TaskStatus.USER_INPUT_RECEIVED
        elif params.author == "nova" and task.status in [TaskStatus.NEW, TaskStatus.USER_INPUT_RECEIVED]:
            task.status = TaskStatus.IN_PROGRESS
        
        await session.commit()
        
        return f"Comment added successfully to task '{task.title}'. Comment: {params.content}"


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
            formatted_tasks.append(await format_task_for_agent(task))
        
        return f"Found {len(formatted_tasks)} tasks needing decisions: {json.dumps(formatted_tasks, indent=2)}"


def get_task_tools() -> List[Tool]:
    """Get task management MCP tools."""
    return [
        Tool(
            name="create_task",
            description="Create a new task with optional person and project relationships",
            func=create_task_tool,
            args_schema=CreateTaskParams
        ),
        Tool(
            name="update_task", 
            description="Update an existing task (status, description, etc.)",
            func=update_task_tool,
            args_schema=UpdateTaskParams
        ),
        Tool(
            name="get_tasks",
            description="Get tasks with optional filtering by status, person, or project",
            func=get_tasks_tool,
            args_schema=SearchTasksParams
        ),
        Tool(
            name="get_task_by_id",
            description="Get detailed information about a specific task by ID",
            func=get_task_by_id_tool,
            args_schema=str
        ),
        Tool(
            name="add_task_comment",
            description="Add a comment to a task and optionally update its status",
            func=add_task_comment_tool,
            args_schema=AddCommentParams
        ),
        Tool(
            name="get_pending_decisions",
            description="Get all tasks that need user review/decisions",
            func=get_pending_decisions_tool,
            args_schema=None
        ),
    ] 