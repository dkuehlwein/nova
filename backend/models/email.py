"""
Email-related Pydantic models for Nova.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class EmailSettings(BaseModel):
    """Email processing configuration settings."""
    
    model_config = ConfigDict(from_attributes=True)
    
    enabled: bool = Field(
        default=True,
        description="Enable automatic email processing"
    )
    polling_interval_minutes: int = Field(
        default=5,
        ge=1,
        le=1440,  # Max 24 hours
        description="Email polling interval in minutes"
    )
    email_label_filter: str = Field(
        default="INBOX",
        description="Email label to filter emails (e.g., 'INBOX', 'UNREAD')"
    )
    max_emails_per_fetch: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of emails to fetch per polling cycle"
    )
    create_tasks_from_emails: bool = Field(
        default=True,
        description="Automatically create tasks from incoming emails"
    )


class EmailMetadata(BaseModel):
    """Metadata for a processed email."""
    
    model_config = ConfigDict(from_attributes=True)
    
    email_id: str = Field(description="Email message ID")
    thread_id: str = Field(description="Email thread ID")
    subject: str = Field(description="Email subject line")
    sender: str = Field(description="Email sender address")
    recipient: str = Field(description="Email recipient address")
    date: datetime = Field(description="Email date/time")
    has_attachments: bool = Field(default=False, description="Whether email has attachments")
    labels: List[str] = Field(default_factory=list, description="Email labels")


class EmailProcessingResult(BaseModel):
    """Result of email processing operation."""
    
    model_config = ConfigDict(from_attributes=True)
    
    success: bool = Field(description="Whether processing was successful")
    email_id: str = Field(description="Email message ID")
    task_id: Optional[str] = Field(default=None, description="Created task ID if successful")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    processing_time_seconds: float = Field(description="Time taken to process email")


class EmailProcessingStats(BaseModel):
    """Statistics for email processing batch."""
    
    model_config = ConfigDict(from_attributes=True)
    
    emails_fetched: int = Field(description="Number of emails fetched")
    emails_processed: int = Field(description="Number of emails successfully processed")
    tasks_created: int = Field(description="Number of tasks created")
    errors: int = Field(description="Number of processing errors")
    processing_time_seconds: float = Field(description="Total processing time")
    started_at: datetime = Field(description="Processing start time")
    completed_at: Optional[datetime] = Field(default=None, description="Processing completion time")


class EmailTaskRequest(BaseModel):
    """Request to manually process an email."""
    
    model_config = ConfigDict(from_attributes=True)
    
    email_id: str = Field(description="Email message ID to process")
    force_reprocess: bool = Field(
        default=False,
        description="Force reprocessing even if already processed"
    )


class EmailTaskResponse(BaseModel):
    """Response from manual email processing."""
    
    model_config = ConfigDict(from_attributes=True)
    
    task_id: str = Field(description="Celery task ID")
    email_id: str = Field(description="Email message ID")
    status: str = Field(description="Task status (PENDING, SUCCESS, FAILURE)")
    message: str = Field(description="Status message")


class CeleryTaskStatus(BaseModel):
    """Status of a Celery task."""
    
    model_config = ConfigDict(from_attributes=True)
    
    task_id: str = Field(description="Celery task ID")
    status: str = Field(description="Task status")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Task result if completed")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    started_at: Optional[datetime] = Field(default=None, description="Task start time")
    completed_at: Optional[datetime] = Field(default=None, description="Task completion time")


class EmailHealthStatus(BaseModel):
    """Health status of email processing system."""
    
    model_config = ConfigDict(from_attributes=True)
    
    celery_worker_online: bool = Field(description="Whether Celery worker is online")
    celery_beat_online: bool = Field(description="Whether Celery beat scheduler is online")
    last_email_fetch: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last email fetch attempt"
    )
    last_successful_fetch: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last successful email fetch"
    )
    pending_tasks: int = Field(description="Number of pending email processing tasks")
    failed_tasks_24h: int = Field(description="Number of failed tasks in last 24 hours")
    email_connection_status: str = Field(description="Email API connection status")


class EmailProcessingEvent(BaseModel):
    """Event model for email processing notifications."""
    
    model_config = ConfigDict(from_attributes=True)
    
    event_type: str = Field(description="Type of event")
    data: Dict[str, Any] = Field(description="Event data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp") 