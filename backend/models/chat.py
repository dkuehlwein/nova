"""
Nova Chat Domain Models

Modern Pydantic V2 models for chat-related API endpoints.
All models follow latest Pydantic V2 patterns with proper validation and serialization.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message model for API responses."""
    role: str = Field(..., description="Message role (user or assistant)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")
    id: Optional[str] = Field(None, description="Message ID")


class ChatRequest(BaseModel):
    """Chat request model for streaming and non-streaming endpoints."""
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    thread_id: Optional[str] = Field(None, description="Thread identifier for conversation continuity")
    stream: bool = Field(True, description="Whether to stream the response")


class ChatResponse(BaseModel):
    """Non-streaming chat response model."""
    message: ChatMessage = Field(..., description="Assistant response message")
    thread_id: str = Field(..., description="Thread identifier")


class ChatSummary(BaseModel):
    """Chat summary for listing chats."""
    id: str = Field(..., description="Chat thread ID")
    title: str = Field(..., description="Chat title")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    last_message: Optional[str] = Field(None, description="Last message preview")
    last_activity: Optional[str] = Field(None, description="Last activity timestamp")
    has_decision: bool = Field(False, description="Whether chat needs user decision")
    message_count: int = Field(0, description="Number of messages in chat")


class ChatMessageDetail(BaseModel):
    """Detailed chat message for message history."""
    id: str = Field(..., description="Message ID")
    sender: str = Field(..., description="Message sender (user or assistant)")
    content: str = Field(..., description="Message content")
    created_at: str = Field(..., description="Message creation timestamp")
    needs_decision: bool = Field(False, description="Whether message needs user decision")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Message metadata")


class TaskChatResponse(BaseModel):
    """Response model for task chat data including escalation info."""
    messages: List[ChatMessageDetail] = Field(..., description="Chat messages")
    pending_escalation: Optional[Dict[str, Any]] = Field(None, description="Pending escalation info")


class TaskChatMessageCreate(BaseModel):
    """Request model for creating task chat messages."""
    content: str = Field(..., description="Message content")


# System Prompt Management Models
class SystemPromptResponse(BaseModel):
    """Response model for system prompt operations."""
    content: str = Field(..., description="Current system prompt content")
    file_path: str = Field(..., description="Path to the system prompt file")
    last_modified: str = Field(..., description="Last modification timestamp")
    size_bytes: int = Field(..., description="File size in bytes")


class SystemPromptUpdateRequest(BaseModel):
    """Request model for updating system prompt."""
    content: str = Field(..., description="New system prompt content")


class HealthResponse(BaseModel):
    """Health check response for chat service."""
    status: str = Field(..., description="Health status")
    agent_ready: bool = Field(..., description="Whether the agent is ready")
    timestamp: str = Field(..., description="Health check timestamp")


class BackupFile(BaseModel):
    """Model for backup file information."""
    filename: str = Field(..., description="Backup filename")
    created_at: str = Field(..., description="Backup creation timestamp")
    size_bytes: int = Field(..., description="Backup file size in bytes")


class BackupListResponse(BaseModel):
    """Response model for listing backup files."""
    backups: List[BackupFile] = Field(..., description="List of available backup files")
    total_count: int = Field(..., description="Total number of backup files") 