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
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from database.database import db_manager
from models.models import (
    Task, TaskComment, Artifact,
    TaskStatus
)
from utils.redis_manager import publish
from utils.task_cache import (
    get_task_counts_with_cache, 
    get_tasks_by_status_with_cache,
    get_cached_dashboard_data,
    set_cached_dashboard_data,
    invalidate_task_cache
)
from models.events import create_task_updated_event


# === Import Domain-Specific Pydantic Models ===
from models.tasks import TaskCreate, TaskUpdate, TaskCommentCreate, TaskResponse
from models.entities import ArtifactCreate, ArtifactResponse
from models.admin import ActivityItem, TaskDashboard
from models.chat import TaskChatMessageCreate


# === API Router ===

router = APIRouter()


# === Overview Dashboard Endpoints ===

@router.get("/api/task-dashboard", response_model=TaskDashboard)
async def get_task_dashboard(
    include_tasks: bool = Query(False, description="Include full task data for kanban board"),
    use_cache: bool = Query(True, description="Use Redis cache for performance")
):
    """
    Get consolidated task dashboard data with optional full task details.
    
    This endpoint replaces both /api/overview and /api/tasks/by-status for better performance.
    - include_tasks=false: Returns only counts and stats (for overview page)
    - include_tasks=true: Returns full task data (for kanban board)
    """
    try:
        # Try to get cached dashboard data first
        cached_data = None
        if use_cache and not include_tasks:
            cached_data = await get_cached_dashboard_data()
        
        if cached_data:
            return TaskDashboard(**cached_data)
        
        # Get task counts with caching
        task_counts = await get_task_counts_with_cache() if use_cache else {}
        if not task_counts:
            # Fallback to direct database query
            async with db_manager.get_session() as session:
                task_count_query = select(Task.status, func.count(Task.id)).group_by(Task.status)
                result = await session.execute(task_count_query)
                status_counts = dict(result.all())
                task_counts = {status.value: count for status, count in status_counts.items()}
                
                # Ensure all status types are represented
                for status in TaskStatus:
                    if status.value not in task_counts:
                        task_counts[status.value] = 0
        
        total_tasks = sum(task_counts.values())
        pending_decisions = task_counts.get("user_input_received", 0) + task_counts.get("needs_review", 0)
        
        # Get recent activity
        async with db_manager.get_session() as session:
            recent_activity = await get_recent_activity_items(session)
        
        # Get full task data if requested
        tasks_by_status = None
        if include_tasks:
            tasks_by_status = await get_tasks_by_status_with_cache(use_cache)
        
        # Build response
        dashboard_data = {
            "task_counts": task_counts,
            "total_tasks": total_tasks,
            "pending_decisions": pending_decisions,
            "recent_activity": recent_activity,
            "system_status": "operational",
            "tasks_by_status": tasks_by_status,
            "cache_info": {
                "cached": cached_data is not None,
                "use_cache": use_cache,
                "includes_tasks": include_tasks
            }
        }
        
        # Cache the result if appropriate
        if use_cache and not include_tasks:
            await set_cached_dashboard_data(dashboard_data)
        
        return TaskDashboard(**dashboard_data)
        
    except Exception as e:
        logging.error(f"Error getting task dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task dashboard")




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
            .options(selectinload(Task.comments))
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
                persons=task.person_emails or [],
                projects=task.project_names or [],
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
                persons=task.person_emails or [],
                projects=task.project_names or [],
                comments_count=len(task.comments)
            ))
        
        return response_tasks




@router.post("/api/tasks", response_model=TaskResponse)
async def create_task(task_data: TaskCreate):
    """Create a new task."""
    async with db_manager.get_session() as session:
        # Create task with memory-based relationships
        task = Task(
            title=task_data.title,
            description=task_data.description,
            status=task_data.status,
            due_date=task_data.due_date,
            tags=task_data.tags,
            person_emails=task_data.person_emails,
            project_names=task_data.project_names,
            thread_id=task_data.thread_id
        )
        
        session.add(task)
        await session.commit()
        
        # Invalidate cache and publish WebSocket event for real-time updates
        try:
            await invalidate_task_cache()
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
            thread_id=task.thread_id,
            persons=task.person_emails or [],
            projects=task.project_names or [],
            comments_count=0
        )


@router.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID):
    """Get a specific task."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.comments))
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
            thread_id=task.thread_id,
            persons=task.person_emails or [],
            projects=task.project_names or [],
            comments_count=len(task.comments)
        )


@router.put("/api/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, task_data: TaskUpdate):
    """Update a task."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.comments))
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
        
        # Update memory when task is completed
        if task_data.status == TaskStatus.DONE and old_status != TaskStatus.DONE:
            await add_task_completion_to_memory(session, task.id)
        
        # Invalidate cache and publish WebSocket event for real-time updates
        try:
            await invalidate_task_cache()
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
            thread_id=task.thread_id,
            persons=task.person_emails or [],
            projects=task.project_names or [],
            comments_count=len(task.comments)
        )


async def add_task_completion_to_memory(session, task_id: UUID):
    """Add completed task information to memory with full context."""
    try:
        from memory.memory_functions import add_memory
        from sqlalchemy.orm import selectinload
        
        # Get task with all comments to include the complete work done
        full_task_result = await session.execute(
            select(Task)
            .options(selectinload(Task.comments))
            .where(Task.id == task_id)
        )
        full_task = full_task_result.scalar_one()
        
        # Create comprehensive memory entry for completed task
        memory_text = f"Completed task: {full_task.title}"
        
        # Include full description
        if full_task.description:
            memory_text += f". Description: {full_task.description}"
        
        # Include ALL comments to capture the complete work and resolution
        if full_task.comments:
            # Include all comments (both user and core_agent) for complete context
            all_comments = [
                f"{comment.author}: {comment.content}"
                for comment in full_task.comments
            ]
            if all_comments:
                comments_text = ". Complete work log: " + " | ".join(all_comments)
                memory_text += comments_text
        
        memory_result = await add_memory(memory_text, f"Completed task: {full_task.title}")
        if memory_result["success"]:
            logging.info(f"Added comprehensive memory for completed task {task_id}: {full_task.title}")
        else:
            logging.warning(f"Failed to add memory for completed task {task_id}: {memory_result.get('message', 'Unknown error')}")
            
    except Exception as memory_error:
        logging.warning(f"Failed to update memory for completed task {task_id}: {memory_error}")


async def cleanup_task_chat_data(task_id: str):
    """Clean up LangGraph checkpointer data associated with a task."""
    logger = logging.getLogger(__name__)

    try:
        # Get database URL from settings
        from config import settings
        database_url = settings.DATABASE_URL

        # Clean up LangGraph checkpointer data
        thread_id = f"core_agent_task_{task_id}"

        try:
            # Create connection pool for checkpointer
            pool = AsyncConnectionPool(
                database_url,
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
        
        # Handle foreign key references first
        try:
           
            # Set task_id to NULL in processed_items (don't delete - we don't want to reprocess items)
            await session.execute(
                text("UPDATE processed_items SET task_id = NULL WHERE task_id = :task_id"),
                {"task_id": task_id}
            )
            
            # Delete task comments (if any)
            await session.execute(
                text("DELETE FROM task_comments WHERE task_id = :task_id"), 
                {"task_id": task_id}
            )
            
            # Now delete the task
            await session.delete(task)
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")
        
        # Clean up associated chat data
        try:
            await cleanup_task_chat_data(str(task_id))
        except Exception as e:
            # Log but don't fail the deletion if chat cleanup fails
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to cleanup chat data for task {task_id}: {e}")
        
        # Invalidate cache and publish WebSocket event for real-time updates
        try:
            await invalidate_task_cache()
            await publish(create_task_updated_event(
                task_id=str(task_id),
                status="deleted",
                action="deleted",
                source="api-endpoint"
            ))
        except Exception as e:
            logging.warning(f"Failed to publish task deletion event: {e}")
        
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
        # Get the proper checkpointer from service manager (same as chat endpoints)
        from api.chat_endpoints import get_checkpointer_from_service_manager
        checkpointer = await get_checkpointer_from_service_manager()
        
        # Get agent with the proper checkpointer - same pattern as chat endpoints
        agent = await create_chat_agent(checkpointer=checkpointer, include_escalation=True)
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





