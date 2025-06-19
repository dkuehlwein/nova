"""
REST API endpoints for Nova frontend.

Provides REST API endpoints that match the UI requirements:
- Overview dashboard data
- Kanban board operations  
- Chat functionality
- Entity management (persons, projects, artifacts)
"""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, or_, select, text, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import create_async_engine
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from database.database import db_manager
from models.models import (
    Task, TaskComment, Person, Project, Artifact,
    TaskStatus
)
from utils.redis_manager import publish
from models.events import create_task_updated_event


# === Import Domain-Specific Pydantic Models ===
from models.tasks import TaskCreate, TaskUpdate, TaskCommentCreate, TaskResponse
from models.entities import PersonCreate, PersonResponse, ProjectCreate, ProjectResponse, ArtifactCreate, ArtifactResponse
from models.admin import ActivityItem, OverviewStats
from models.chat import TaskChatMessageCreate


# === API Router ===

router = APIRouter()


# === Overview Dashboard Endpoints ===

@router.get("/api/overview", response_model=OverviewStats)
async def get_overview():
    """Get dashboard overview with task counts, pending decisions, and recent activity."""
    async with db_manager.get_session() as session:
        # Get task counts by status
        task_count_query = select(Task.status, func.count(Task.id)).group_by(Task.status)
        result = await session.execute(task_count_query)
        status_counts = dict(result.all())
        
        # Convert enum keys to strings for frontend
        task_counts = {status.value: count for status, count in status_counts.items()}
        total_tasks = sum(task_counts.values())
        
        # Get pending decisions count
        pending_decisions = task_counts.get("USER_INPUT_RECEIVED", 0) + task_counts.get("NEEDS_REVIEW", 0)
        
        # Get recent activity
        recent_activity = await get_recent_activity_items(session)
        
        return OverviewStats(
            task_counts=task_counts,
            total_tasks=total_tasks,
            pending_decisions=pending_decisions,
            recent_activity=recent_activity,
            system_status="operational"
        )


@router.get("/api/recent-activity", response_model=List[ActivityItem])
async def get_recent_activity():
    """Get recent system activity feed."""
    async with db_manager.get_session() as session:
        return await get_recent_activity_items(session)


async def get_recent_activity_items(session, limit: int = 10) -> List[ActivityItem]:
    """Get recent activity items."""
    activities = []
    
    # Get recent tasks (created or updated in the last 24 hours)
    recent_tasks_query = (
        select(Task)
        .where(Task.updated_at >= func.now() - text("INTERVAL '24 hours'"))
        .order_by(Task.updated_at.desc())
        .limit(limit)
    )
    result = await session.execute(recent_tasks_query)
    recent_tasks = result.scalars().all()
    
    for task in recent_tasks:
        # Calculate time difference using timezone-aware datetime
        time_diff = datetime.now(timezone.utc) - task.updated_at
        if time_diff.seconds < 60:
            time_str = "Just now"
        elif time_diff.seconds < 3600:
            minutes = time_diff.seconds // 60
            time_str = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif time_diff.days == 0:
            hours = time_diff.seconds // 3600
            time_str = f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            time_str = f"{time_diff.days} day{'s' if time_diff.days != 1 else ''} ago"
        
        # Determine activity type and description based on stored changes
        changes = task.task_metadata.get('last_changes', []) if task.task_metadata else []
        
        if task.status == TaskStatus.DONE and 'status' in str(changes):
            activity_type = "task_completed"
            description = f"Moved to DONE lane"
        elif task.status == TaskStatus.NEW and not changes:
            activity_type = "task_created" 
            description = f"Created in {task.status.value} lane"
        elif changes:
            activity_type = "task_updated"
            # Create a more descriptive message based on what changed
            if len(changes) == 1:
                change = changes[0]
                if 'title' in change:
                    description = f"Updated {change}"
                elif change == 'description':
                    description = "Updated description"
                elif 'status' in change:
                    description = f"Updated {change}"
                elif change == 'tags':
                    description = "Updated tags"
                else:
                    description = f"Updated {change}"
            else:
                description = f"Updated {', '.join(changes)}"
        else:
            activity_type = "task_updated"
            description = f"Updated task"
        
        activities.append(ActivityItem(
            type=activity_type,
            title=f"Task: {task.title}",
            description=description,
            time=time_str,
            timestamp=task.updated_at,
            related_task_id=task.id
        ))
    
    # Sort by timestamp and return most recent
    activities.sort(key=lambda x: x.timestamp, reverse=True)
    return activities[:limit]


@router.get("/api/pending-decisions", response_model=List[TaskResponse])
async def get_pending_decisions():
    """Get tasks that need user decisions."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
            .where(Task.status == TaskStatus.NEEDS_REVIEW)
            .order_by(Task.updated_at.desc())
        )
        tasks = result.scalars().all()
        
        response_tasks = []
        for task in tasks:
            response_tasks.append(TaskResponse(
                id=task.id,
                title=task.title,
                description=task.description,
                summary=task.summary,
                status=task.status,
                created_at=task.created_at,
                updated_at=task.updated_at,
                due_date=task.due_date,
                completed_at=task.completed_at,
                tags=task.tags or [],
                needs_decision=True,
                decision_type="task_review",
                persons=[p.name for p in task.persons],
                projects=[p.name for p in task.projects],
                comments_count=len(task.comments)
            ))
        
        return response_tasks


# === Task Management Endpoints ===

@router.get("/api/tasks", response_model=List[TaskResponse])
async def get_tasks(
    status: Optional[TaskStatus] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0)
):
    """Get tasks with optional filtering."""
    async with db_manager.get_session() as session:
        query = select(Task).options(
            selectinload(Task.persons),
            selectinload(Task.projects),
            selectinload(Task.comments)
        )
        
        if status:
            query = query.where(Task.status == status)
        
        query = query.order_by(Task.updated_at.desc()).limit(limit).offset(offset)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        
        response_tasks = []
        for task in tasks:
            # Check if task has decisions pending (simplified logic)
            needs_decision = task.status == TaskStatus.NEEDS_REVIEW
            
            response_tasks.append(TaskResponse(
                id=task.id,
                title=task.title,
                description=task.description,
                summary=task.summary,
                status=task.status,
                created_at=task.created_at,
                updated_at=task.updated_at,
                due_date=task.due_date,
                completed_at=task.completed_at,
                tags=task.tags or [],
                needs_decision=needs_decision,
                decision_type="task_review" if needs_decision else None,
                persons=[p.name for p in task.persons],
                projects=[p.name for p in task.projects],
                comments_count=len(task.comments)
            ))
        
        return response_tasks


@router.get("/api/tasks/by-status", response_model=Dict[str, List[TaskResponse]])
async def get_tasks_by_status():
    """Get tasks organized by status for kanban board."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
            .order_by(Task.updated_at.desc())
        )
        tasks = result.scalars().all()
        
        tasks_by_status = {}
        for status in TaskStatus:
            tasks_by_status[status.value] = []
        
        for task in tasks:
            needs_decision = task.status == TaskStatus.NEEDS_REVIEW
            
            task_response = TaskResponse(
                id=task.id,
                title=task.title,
                description=task.description,
                summary=task.summary,
                status=task.status,
                created_at=task.created_at,
                updated_at=task.updated_at,
                due_date=task.due_date,
                completed_at=task.completed_at,
                tags=task.tags or [],
                needs_decision=needs_decision,
                decision_type="task_review" if needs_decision else None,
                persons=[p.name for p in task.persons],
                projects=[p.name for p in task.projects],
                comments_count=len(task.comments)
            )
            
            tasks_by_status[task.status.value].append(task_response)
        
        return tasks_by_status


@router.post("/api/tasks", response_model=TaskResponse)
async def create_task(task_data: TaskCreate):
    """Create a new task."""
    async with db_manager.get_session() as session:
        # Create task
        task = Task(
            title=task_data.title,
            description=task_data.description,
            status=task_data.status,
            due_date=task_data.due_date,
            tags=task_data.tags
        )
        
        session.add(task)
        await session.flush()  # Get the task ID
        
        # Add person relationships
        persons_list = []
        if task_data.person_ids:
            persons_result = await session.execute(
                select(Person).where(Person.id.in_(task_data.person_ids))
            )
            persons = persons_result.scalars().all()
            task.persons.extend(persons)
            persons_list = [p.name for p in persons]
        
        # Add project relationships
        projects_list = []
        if task_data.project_ids:
            projects_result = await session.execute(
                select(Project).where(Project.id.in_(task_data.project_ids))
            )
            projects = projects_result.scalars().all()
            task.projects.extend(projects)
            projects_list = [p.name for p in projects]
        
        await session.commit()
        
        # Publish WebSocket event for real-time updates
        try:
            await publish(create_task_updated_event(
                task_id=str(task.id),
                status=task.status.value,
                action="created",
                source="api-endpoint"
            ))
        except Exception as e:
            logging.warning(f"Failed to publish task creation event: {e}")
        
        return TaskResponse(
            id=task.id,
            title=task.title,
            description=task.description,
            summary=task.summary,
            status=task.status,
            created_at=task.created_at,
            updated_at=task.updated_at,
            due_date=task.due_date,
            completed_at=task.completed_at,
            tags=task.tags or [],
            needs_decision=task.status == TaskStatus.NEEDS_REVIEW,
            persons=persons_list,
            projects=projects_list,
            comments_count=0
        )


@router.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID):
    """Get a specific task."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
            .where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskResponse(
            id=task.id,
            title=task.title,
            description=task.description,
            summary=task.summary,
            status=task.status,
            created_at=task.created_at,
            updated_at=task.updated_at,
            due_date=task.due_date,
            completed_at=task.completed_at,
            tags=task.tags or [],
            needs_decision=task.status == TaskStatus.NEEDS_REVIEW,
            persons=[p.name for p in task.persons],
            projects=[p.name for p in task.projects],
            comments_count=len(task.comments)
        )


@router.put("/api/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, task_data: TaskUpdate):
    """Update a task."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
            .where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Track what changed for activity logging
        changes = []
        update_data = task_data.model_dump(exclude_unset=True)
        old_status = task.status
        
        if 'title' in update_data and update_data['title'] != task.title:
            changes.append(f"title from '{task.title}' to '{update_data['title']}'")
        if 'description' in update_data and update_data['description'] != task.description:
            changes.append("description")
        if 'status' in update_data and update_data['status'] != task.status:
            changes.append(f"status from '{task.status.value}' to '{update_data['status'].value}'")
        if 'tags' in update_data and update_data['tags'] != task.tags:
            changes.append("tags")
        
        # Update fields
        for field, value in update_data.items():
            setattr(task, field, value)
        
        # Set completed_at if status is DONE
        if task_data.status == TaskStatus.DONE and not task.completed_at:
            task.completed_at = datetime.utcnow()
        elif task_data.status != TaskStatus.DONE:
            task.completed_at = None
        
        # Store the changes in task_metadata for activity tracking
        if changes:
            if not task.task_metadata:
                task.task_metadata = {}
            task.task_metadata['last_changes'] = changes
            task.task_metadata['last_change_time'] = datetime.utcnow().isoformat()
        
        await session.commit()
        await session.refresh(task)
        
        # Publish WebSocket event for real-time updates
        try:
            status_changed = task_data.status and old_status != task.status
            await publish(create_task_updated_event(
                task_id=str(task.id),
                status=task.status.value,
                action="status_changed" if status_changed else "updated",
                source="api-endpoint"
            ))
        except Exception as e:
            logging.warning(f"Failed to publish task update event: {e}")
        
        return TaskResponse(
            id=task.id,
            title=task.title,
            description=task.description,
            summary=task.summary,
            status=task.status,
            created_at=task.created_at,
            updated_at=task.updated_at,
            due_date=task.due_date,
            completed_at=task.completed_at,
            tags=task.tags or [],
            needs_decision=task.status == TaskStatus.NEEDS_REVIEW,
            persons=[p.name for p in task.persons],
            projects=[p.name for p in task.projects],
            comments_count=len(task.comments)
        )


async def cleanup_task_chat_data(task_id: str):
    """Clean up chat data associated with a task."""
    logger = logging.getLogger(__name__)
    
    try:
        # Get database URL
        database_url = os.getenv(
            'DATABASE_URL', 
            'postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova_kanban'
        )
        
        # Clean up LangGraph checkpointer data
        thread_id = f"core_agent_task_{task_id}"
        
        try:
            # Create connection pool for checkpointer
            pool = AsyncConnectionPool(
                database_url.replace('+asyncpg', ''),
                open=False
            )
            await pool.open()
            
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                await checkpointer.adelete_thread(thread_id)
                logger.info(f"✅ Deleted LangGraph thread: {thread_id}")
            
            await pool.close()
            
        except Exception as e:
            logger.warning(f"Failed to delete LangGraph thread {thread_id}: {e}")
        
        # Clean up Nova database chat data
        # Look for chats with IDs that might be related to this task
        potential_chat_ids = [
            f"core_agent_task_{task_id}",
            f"chat-{task_id}",
            f"task-{task_id}",
            task_id  # Direct task ID as chat ID
        ]
        
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as conn:
                for chat_id in potential_chat_ids:
                    try:
                        # Delete chat messages first (foreign key constraint)
                        result = await conn.execute(
                            text("DELETE FROM chat_messages WHERE chat_id = :chat_id"),
                            {"chat_id": chat_id}
                        )
                        message_count = result.rowcount
                        
                        # Delete chat
                        result = await conn.execute(
                            text("DELETE FROM chats WHERE id = :chat_id"),
                            {"chat_id": chat_id}
                        )
                        chat_count = result.rowcount
                        
                        if message_count > 0 or chat_count > 0:
                            logger.info(f"✅ Deleted chat {chat_id}: {message_count} messages, {chat_count} chat record")
                            
                    except Exception as e:
                        logger.debug(f"No chat found with ID {chat_id}: {e}")
                        
        except Exception as e:
            logger.warning(f"Failed to clean database chat data for task {task_id}: {e}")
        finally:
            await engine.dispose()
            
    except Exception as e:
        logger.error(f"Error during chat cleanup for task {task_id}: {e}")


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: UUID):
    """Delete a task and its associated chat data."""
    async with db_manager.get_session() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Delete the task from database first
        await session.delete(task)
        await session.commit()
        
        # Clean up associated chat data
        await cleanup_task_chat_data(str(task_id))
        
        return {"message": "Task and associated chat data deleted successfully"}


# === Task Comments ===

@router.get("/api/tasks/{task_id}/comments", response_model=List[Dict])
async def get_task_comments(task_id: UUID):
    """Get comments for a task."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(TaskComment)
            .where(TaskComment.task_id == task_id)
            .order_by(TaskComment.created_at.asc())
        )
        comments = result.scalars().all()
        
        return [
            {
                "id": comment.id,
                "content": comment.content,
                "author": comment.author,
                "created_at": comment.created_at
            }
            for comment in comments
        ]


@router.post("/api/tasks/{task_id}/comments")
async def add_task_comment(task_id: UUID, comment_data: TaskCommentCreate):
    """Add a comment to a task."""
    async with db_manager.get_session() as session:
        # Verify task exists
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Create comment
        comment = TaskComment(
            task_id=task_id,
            content=comment_data.content,
            author=comment_data.author
        )
        session.add(comment)
        
        # Update task status to USER_INPUT_RECEIVED if user comment
        if comment_data.author == "user" and task.status in [TaskStatus.NEEDS_REVIEW, TaskStatus.WAITING]:
            task.status = TaskStatus.USER_INPUT_RECEIVED
        
        await session.commit()
        
        return {"message": "Comment added successfully", "id": comment.id}


# === Task Chat Endpoints ===

# TaskChatMessageCreate model now imported from models.chat


# Removed - this endpoint is no longer used. Task chats now use /chat/conversations/{threadId}/messages


@router.post("/api/tasks/{task_id}/chat/message")
async def post_task_chat_message(task_id: UUID, message_data: TaskChatMessageCreate):
    """Post a human response to task escalation or regular task chat."""
    from agent.chat_agent import create_chat_agent
    from langchain_core.messages import HumanMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.types import Command
    from tools.task_tools import update_task_tool
    
    logger = logging.getLogger(__name__)
    
    async with db_manager.get_session() as session:
        # Verify task exists
        task_result = await session.execute(select(Task).where(Task.id == task_id))
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    
    thread_id = f"core_agent_task_{task_id}"
    config = RunnableConfig(configurable={"thread_id": thread_id})
    
    try:
        # Get agent and check current state
        agent = await create_chat_agent()
        state = await agent.aget_state(config)
        
        # Determine if this is an escalation response or regular message
        if state.interrupts:
            logger.info(f"Handling escalation response for task {task_id}")
            
            # Resume the graph with the human's response using Command(resume=...)
            async for chunk in agent.astream(
                Command(resume=message_data.content),
                config=config,
                stream_mode="updates"
            ):
                logger.debug(f"Resume chunk: {chunk}")
        else:
            logger.info(f"Adding regular message to task {task_id} chat")
            
            # IMPORTANT: This endpoint should NOT be used for regular task conversations!
            # Regular conversations should use /chat/stream with the thread_id: core_agent_task_{task_id}
            # This endpoint is ONLY for escalation responses to avoid duplication issues.
            
            # Return a helpful error that guides developers to the correct endpoint
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid endpoint for regular task conversations",
                    "message": "This endpoint is only for escalation responses. Use /chat/stream for regular messages.",
                    "correct_usage": {
                        "endpoint": "/chat/stream",
                        "method": "POST",
                        "body": {
                            "messages": "[array of messages]",
                            "thread_id": f"core_agent_task_{task_id}",
                            "stream": True
                        }
                    }
                }
            )
        
        # Update task status so core agent can process the response
        # But only if still in needs_review - don't override completed tasks
        async with db_manager.get_session() as session:
            task_result = await session.execute(select(Task).where(Task.id == task_id))
            current_task = task_result.scalar_one()
            
            if current_task.status == TaskStatus.NEEDS_REVIEW:
                await update_task_tool(
                    task_id=str(task_id),
                    status="user_input_received"
                )
                final_status = "user_input_received"
            else:
                # Task was completed by chat agent, preserve its status
                final_status = current_task.status.value
        
        return {
            "success": True,
            "task_status": final_status,
            "message": "Message posted successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to post message to task {task_id} chat: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to post message: {str(e)}")


# === Entity Management Endpoints ===

@router.get("/api/persons", response_model=List[PersonResponse])
async def get_persons():
    """Get all persons."""
    async with db_manager.get_session() as session:
        result = await session.execute(select(Person).order_by(Person.name))
        persons = result.scalars().all()
        return [PersonResponse.model_validate(person) for person in persons]


@router.post("/api/persons", response_model=PersonResponse)
async def create_person(person_data: PersonCreate):
    """Create a new person."""
    async with db_manager.get_session() as session:
        person = Person(**person_data.model_dump())
        session.add(person)
        await session.commit()
        await session.refresh(person)
        return PersonResponse.model_validate(person)


@router.get("/api/projects", response_model=List[ProjectResponse])
async def get_projects():
    """Get all projects."""
    async with db_manager.get_session() as session:
        result = await session.execute(select(Project).order_by(Project.name))
        projects = result.scalars().all()
        return [ProjectResponse.model_validate(project) for project in projects]


@router.post("/api/projects", response_model=ProjectResponse)
async def create_project(project_data: ProjectCreate):
    """Create a new project."""
    async with db_manager.get_session() as session:
        project = Project(**project_data.model_dump())
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return ProjectResponse.model_validate(project)


@router.get("/api/artifacts", response_model=List[ArtifactResponse])
async def get_artifacts():
    """Get all artifacts."""
    async with db_manager.get_session() as session:
        result = await session.execute(select(Artifact).order_by(Artifact.created_at.desc()))
        artifacts = result.scalars().all()
        return [ArtifactResponse.model_validate(artifact) for artifact in artifacts]


@router.post("/api/artifacts", response_model=ArtifactResponse)
async def create_artifact(artifact_data: ArtifactCreate):
    """Create a new artifact."""
    async with db_manager.get_session() as session:
        artifact = Artifact(**artifact_data.model_dump())
        session.add(artifact)
        await session.commit()
        await session.refresh(artifact)
        return ArtifactResponse.model_validate(artifact)


# === Health Check ===

@router.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "nova-kanban-mcp",
        "timestamp": datetime.now(timezone.utc).isoformat()
    } 