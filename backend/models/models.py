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
    Column, func, UniqueConstraint
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


task_artifact_association = Table(
    'task_artifact',
    Base.metadata,
    Column('task_id', PGUUID(as_uuid=True), ForeignKey('tasks.id')),
    Column('artifact_id', PGUUID(as_uuid=True), ForeignKey('artifacts.id'))
)


class Task(Base):
    """Task model updated for memory-based person/project references."""
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
    
    # JSON fields for flexibility and memory-based relationships
    tags: Mapped[List[str]] = mapped_column(JSONB, default=list)
    task_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    person_emails: Mapped[List[str]] = mapped_column(JSONB, default=list)  # Email strings for memory lookup
    project_names: Mapped[List[str]] = mapped_column(JSONB, default=list)  # Project name strings for memory lookup
    
    # Relationships
    comments: Mapped[List["TaskComment"]] = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
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


class Chat(Base):
    """Chat model based on high-level outline."""
    __tablename__ = 'chats'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Optional project name for memory-based lookup
    project_name: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Relationships
    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="chat")


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


class ProcessedItem(Base):
    """
    Generalized model to track processed items from all input sources.
    
    This table supports the new hook system, providing deduplication
    and tracking for emails, calendar events, Slack messages, etc.
    """
    __tablename__ = 'processed_items'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Source identification
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 'email', 'calendar', 'slack'
    source_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)   # Original ID from source system
    
    # Flexible metadata storage for source-specific data
    source_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Processing information
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    task_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('tasks.id'))
    
    # Composite unique constraint to prevent duplicate processing
    __table_args__ = (
        UniqueConstraint('source_type', 'source_id', name='uq_processed_items_source'),
    )
    
    def __repr__(self):
        return f"<ProcessedItem(source_type='{self.source_type}', source_id='{self.source_id}', task_id='{self.task_id}')>"
    
    # Relationship to created task (optional, task might be deleted later)
    task: Mapped[Optional["Task"]] = relationship("Task")


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


class LLMModel(Base):
    """
    Model to store LLM model configurations for LiteLLM gateway.
    
    This table stores the model configurations that are used to dynamically
    configure the LiteLLM service for hybrid cloud/local model support.
    """
    __tablename__ = 'llm_models'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Model identification
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # Display name
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)  # LiteLLM model identifier
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # Provider type (ollama, openai, etc.)
    
    # Model state
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Configuration
    config: Mapped[dict] = mapped_column(JSONB, default=dict)  # Provider-specific configuration
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) 