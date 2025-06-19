"""
Nova Kanban Database Models

Based on the high-level outline data structures:
- Task, Person, Project, Chat, Artifact
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import (
    Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, Table,
    Column, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB


class Base(DeclarativeBase):
    pass


class TaskStatus(str, Enum):
    """Task status enumeration based on high-level outline."""
    NEW = "new"
    USER_INPUT_RECEIVED = "user_input_received"
    NEEDS_REVIEW = "needs_review"
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


# Association tables for many-to-many relationships
task_person_association = Table(
    'task_person',
    Base.metadata,
    Column('task_id', PGUUID(as_uuid=True), ForeignKey('tasks.id')),
    Column('person_id', PGUUID(as_uuid=True), ForeignKey('persons.id'))
)

task_project_association = Table(
    'task_project',
    Base.metadata,
    Column('task_id', PGUUID(as_uuid=True), ForeignKey('tasks.id')),
    Column('project_id', PGUUID(as_uuid=True), ForeignKey('projects.id'))
)

task_artifact_association = Table(
    'task_artifact',
    Base.metadata,
    Column('task_id', PGUUID(as_uuid=True), ForeignKey('tasks.id')),
    Column('artifact_id', PGUUID(as_uuid=True), ForeignKey('artifacts.id'))
)

person_project_association = Table(
    'person_project',
    Base.metadata,
    Column('person_id', PGUUID(as_uuid=True), ForeignKey('persons.id')),
    Column('project_id', PGUUID(as_uuid=True), ForeignKey('projects.id')),
    Column('role', String(100))  # Role in the project
)

chat_person_association = Table(
    'chat_person',
    Base.metadata,
    Column('chat_id', PGUUID(as_uuid=True), ForeignKey('chats.id')),
    Column('person_id', PGUUID(as_uuid=True), ForeignKey('persons.id'))
)


class Task(Base):
    """Task model based on high-level outline."""
    __tablename__ = 'tasks'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.NEW)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # JSON fields for flexibility
    tags: Mapped[List[str]] = mapped_column(JSONB, default=list)
    task_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    comments: Mapped[List["TaskComment"]] = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
    persons: Mapped[List["Person"]] = relationship("Person", secondary=task_person_association, back_populates="tasks")
    projects: Mapped[List["Project"]] = relationship("Project", secondary=task_project_association, back_populates="tasks")
    artifacts: Mapped[List["Artifact"]] = relationship("Artifact", secondary=task_artifact_association, back_populates="tasks")
    
    # Optional chat relationship
    chat_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('chats.id'))
    chat: Mapped[Optional["Chat"]] = relationship("Chat", back_populates="tasks")


class TaskComment(Base):
    """Task comments for follow-up notes."""
    __tablename__ = 'task_comments'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('tasks.id'), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(100), nullable=False)  # "user" or "nova"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    task: Mapped["Task"] = relationship("Task", back_populates="comments")


class Person(Base):
    """Person model based on high-level outline."""
    __tablename__ = 'persons'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(255))  # e.g., "Sales lead for public sector"
    description: Mapped[Optional[str]] = mapped_column(Text)
    current_focus: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tasks: Mapped[List["Task"]] = relationship("Task", secondary=task_person_association, back_populates="persons")
    projects: Mapped[List["Project"]] = relationship("Project", secondary=person_project_association, back_populates="persons")
    chats: Mapped[List["Chat"]] = relationship("Chat", secondary=chat_person_association, back_populates="persons")


class Project(Base):
    """Project model based on high-level outline."""
    __tablename__ = 'projects'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client: Mapped[str] = mapped_column(String(255), nullable=False)
    booking_code: Mapped[Optional[str]] = mapped_column(String(100))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tasks: Mapped[List["Task"]] = relationship("Task", secondary=task_project_association, back_populates="projects")
    persons: Mapped[List["Person"]] = relationship("Person", secondary=person_project_association, back_populates="projects")
    chats: Mapped[List["Chat"]] = relationship("Chat", back_populates="project")


class Chat(Base):
    """Chat model based on high-level outline."""
    __tablename__ = 'chats'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")
    persons: Mapped[List["Person"]] = relationship("Person", secondary=chat_person_association, back_populates="chats")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="chat")
    
    # Optional project relationship (should be one, but may be multiple)
    project_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('projects.id'))
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="chats")


class ChatMessage(Base):
    """
    Chat messages within conversations.
    
    Note: We should review LangGraph patterns from agent-chat-ui:
    https://github.com/langchain-ai/agent-chat-ui
    
    This model may need updates to align with LangGraph message structure.
    """
    __tablename__ = 'chat_messages'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    chat_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('chats.id'), nullable=False)
    sender: Mapped[str] = mapped_column(String(50), nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Decision support
    needs_decision: Mapped[bool] = mapped_column(Boolean, default=False)
    decision_type: Mapped[Optional[str]] = mapped_column(String(100))
    decision_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")


class Artifact(Base):
    """Artifact model - simplified to just handle links to resources."""
    __tablename__ = 'artifacts'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    link: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tasks: Mapped[List["Task"]] = relationship("Task", secondary=task_artifact_association, back_populates="artifacts")


class AgentStatusEnum(str, Enum):
    """Core agent status enumeration."""
    IDLE = "idle"
    PROCESSING = "processing"
    PAUSED = "paused"
    ERROR = "error"


class AgentStatus(Base):
    """
    Model to track the core agent's current status and state.
    
    This ensures only one agent instance processes tasks at a time
    and provides visibility into agent activity.
    """
    __tablename__ = 'agent_status'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Agent state
    status: Mapped[AgentStatusEnum] = mapped_column(SQLEnum(AgentStatusEnum), nullable=False, default=AgentStatusEnum.IDLE)
    current_task_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True))
    
    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Metrics
    total_tasks_processed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Error information
    last_error: Mapped[Optional[str]] = mapped_column(String(1000))
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) 