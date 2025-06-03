"""
REST API endpoints for Nova frontend.

Provides REST API endpoints that match the UI requirements:
- Overview dashboard data
- Kanban board operations  
- Chat functionality
- Entity management (persons, projects, artifacts)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select, text, desc
from sqlalchemy.orm import selectinload

from database.database import db_manager
from models.models import (
    Task, TaskComment, Person, Project, Chat, ChatMessage, Artifact,
    TaskStatus
)


# === Pydantic Models for API ===

class TaskCreate(BaseModel):
    title: str
    description: str
    status: TaskStatus = TaskStatus.NEW
    due_date: Optional[datetime] = None
    tags: List[str] = []
    person_ids: List[UUID] = []
    project_ids: List[UUID] = []


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    summary: Optional[str] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    completed_at: Optional[datetime] = None


class TaskCommentCreate(BaseModel):
    content: str
    author: str = "user"


class TaskResponse(BaseModel):
    id: UUID
    title: str
    description: str
    summary: Optional[str]
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    tags: List[str]
    needs_decision: bool = False
    decision_type: Optional[str] = None
    
    # Related entities
    persons: List[str] = []  # Names for UI
    projects: List[str] = []  # Names for UI
    comments_count: int = 0

    class Config:
        from_attributes = True


class PersonCreate(BaseModel):
    name: str
    email: str
    role: Optional[str] = None
    description: Optional[str] = None
    current_focus: Optional[str] = None


class PersonResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: Optional[str]
    description: Optional[str]
    current_focus: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str
    client: str
    booking_code: Optional[str] = None
    summary: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    client: str
    booking_code: Optional[str]
    summary: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatCreate(BaseModel):
    title: str
    project_id: Optional[UUID] = None
    person_ids: List[UUID] = []


class ChatMessageCreate(BaseModel):
    sender: str  # "user" or "assistant"
    content: str
    needs_decision: bool = False
    decision_type: Optional[str] = None
    decision_metadata: Dict = {}


class ChatMessageResponse(BaseModel):
    id: UUID
    sender: str
    content: str
    needs_decision: bool
    decision_type: Optional[str]
    decision_metadata: Dict
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None
    last_activity: Optional[datetime] = None
    has_decision: bool = False
    message_count: int = 0
    
    class Config:
        from_attributes = True


class ActivityItem(BaseModel):
    type: str  # "task_created", "task_completed", "email_processed", etc.
    title: str
    description: str
    time: str  # human readable time like "5 minutes ago"
    timestamp: datetime
    related_task_id: Optional[UUID] = None
    related_chat_id: Optional[UUID] = None


class OverviewStats(BaseModel):
    task_counts: Dict[str, int]  # counts by status
    total_tasks: int
    pending_decisions: int
    recent_activity: List[ActivityItem]
    system_status: str


class ArtifactCreate(BaseModel):
    link: str
    title: Optional[str] = None
    summary: Optional[str] = None


class ArtifactResponse(BaseModel):
    id: UUID
    link: str
    title: Optional[str]
    summary: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


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
        
        # Determine activity type and description
        if task.status == TaskStatus.DONE:
            activity_type = "task_completed"
            description = f"Moved to DONE lane"
        elif task.status == TaskStatus.NEW:
            activity_type = "task_created" 
            description = f"Created in {task.status.value} lane"
        else:
            activity_type = "task_updated"
            description = f"Updated status to {task.status.value}"
        
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
        
        # Update fields
        for field, value in task_data.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        
        # Set completed_at if status is DONE
        if task_data.status == TaskStatus.DONE and not task.completed_at:
            task.completed_at = datetime.utcnow()
        elif task_data.status != TaskStatus.DONE:
            task.completed_at = None
        
        await session.commit()
        await session.refresh(task)
        
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


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: UUID):
    """Delete a task."""
    async with db_manager.get_session() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        await session.delete(task)
        await session.commit()
        
        return {"message": "Task deleted successfully"}


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


# === Chat Endpoints ===

@router.get("/api/chats", response_model=List[ChatResponse])
async def get_chats():
    """Get all chat conversations."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Chat)
            .options(selectinload(Chat.messages))
            .order_by(Chat.updated_at.desc())
        )
        chats = result.scalars().all()
        
        chat_responses = []
        for chat in chats:
            # Get last message
            last_message = None
            last_activity = chat.updated_at
            has_decision = False
            
            if chat.messages:
                sorted_messages = sorted(chat.messages, key=lambda m: m.created_at, reverse=True)
                last_message = sorted_messages[0].content[:100] + "..." if len(sorted_messages[0].content) > 100 else sorted_messages[0].content
                last_activity = sorted_messages[0].created_at
                has_decision = any(msg.needs_decision for msg in chat.messages)
            
            chat_responses.append(ChatResponse(
                id=chat.id,
                title=chat.title,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
                last_message=last_message,
                last_activity=last_activity,
                has_decision=has_decision,
                message_count=len(chat.messages)
            ))
        
        return chat_responses


@router.get("/api/chats/{chat_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(chat_id: UUID):
    """Get messages for a specific chat."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = result.scalars().all()
        
        return [
            ChatMessageResponse(
                id=message.id,
                sender=message.sender,
                content=message.content,
                needs_decision=message.needs_decision,
                decision_type=message.decision_type,
                decision_metadata=message.decision_metadata or {},
                created_at=message.created_at
            )
            for message in messages
        ]


@router.post("/api/chats", response_model=ChatResponse)
async def create_chat(chat_data: ChatCreate):
    """Create a new chat conversation."""
    async with db_manager.get_session() as session:
        chat = Chat(
            title=chat_data.title,
            project_id=chat_data.project_id
        )
        
        session.add(chat)
        await session.flush()
        
        # Add person relationships
        if chat_data.person_ids:
            persons_result = await session.execute(
                select(Person).where(Person.id.in_(chat_data.person_ids))
            )
            persons = persons_result.scalars().all()
            chat.persons.extend(persons)
        
        await session.commit()
        await session.refresh(chat)
        
        return ChatResponse(
            id=chat.id,
            title=chat.title,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            message_count=0
        )


@router.post("/api/chats/{chat_id}/messages")
async def add_chat_message(chat_id: UUID, message_data: ChatMessageCreate):
    """Add a message to a chat."""
    async with db_manager.get_session() as session:
        # Verify chat exists
        result = await session.execute(select(Chat).where(Chat.id == chat_id))
        chat = result.scalar_one_or_none()
        
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Create message
        message = ChatMessage(
            chat_id=chat_id,
            sender=message_data.sender,
            content=message_data.content,
            needs_decision=message_data.needs_decision,
            decision_type=message_data.decision_type,
            decision_metadata=message_data.decision_metadata
        )
        session.add(message)
        
        # Update chat timestamp
        chat.updated_at = datetime.utcnow()
        
        await session.commit()
        
        return {"message": "Message added successfully", "id": message.id}


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
        "timestamp": datetime.utcnow().isoformat()
    } 