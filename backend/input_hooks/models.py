"""
Pydantic models for the input hooks system.

Defines configuration schemas and data models for all hook types.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Literal, Union
from pydantic import BaseModel, Field


class ProcessingResult(BaseModel):
    """Result of processing items from an input hook."""
    items_processed: int = 0
    tasks_created: int = 0
    tasks_updated: int = 0
    errors: List[str] = []
    hook_name: str = ""
    processing_time_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NormalizedItem(BaseModel):
    """Standardized format for items from any input source."""
    source_type: str  # "email", "calendar", "slack", etc.
    source_id: str    # Original ID from source system
    title: str        # Human-readable title
    content: Dict[str, Any]  # Full content/metadata from source
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Nova-specific fields
    should_create_task: bool = True
    should_update_existing: bool = False
    task_template_override: Optional[str] = None


class TaskTemplate(BaseModel):
    """Template for creating tasks from input items."""
    title_format: str = "{title}"
    description_format: str = "{content}"
    tags: List[str] = []
    priority: Optional[str] = None
    status: str = "todo"


class HookConfig(BaseModel):
    """Base configuration for all input hooks."""
    name: str
    hook_type: str
    display_name: Optional[str] = None  # Human-readable name for UI display
    enabled: bool = True
    polling_interval: int = Field(default=300, gt=0)  # seconds
    queue_name: Optional[str] = None  # defaults to hook name
    
    # Task creation settings
    create_tasks: bool = True
    update_existing_tasks: bool = False
    task_template: Optional[TaskTemplate] = None
    
    # Hook-specific settings (flexible)
    hook_settings: Dict[str, Any] = {}
    
    class Config:
        extra = "allow"  # Allow additional fields


class EmailHookSettings(BaseModel):
    """Email-specific hook settings."""
    max_per_fetch: int = Field(default=50, gt=0)
    label_filter: Optional[str] = None
    create_tasks: bool = True


class EmailHookConfig(HookConfig):
    """Configuration for email input hooks."""
    hook_type: Literal["email"] = "email"
    hook_settings: EmailHookSettings = Field(default_factory=EmailHookSettings)


class OutlookEmailHookSettings(BaseModel):
    """Outlook email-specific hook settings."""
    max_per_fetch: int = Field(default=50, gt=0)
    folder: str = "inbox"
    since_date: Optional[str] = None  # Only process emails from this date onwards (YYYY-MM-DD)


class OutlookEmailHookConfig(HookConfig):
    """Configuration for Outlook email input hooks."""
    hook_type: Literal["outlook_email"] = "outlook_email"
    hook_settings: OutlookEmailHookSettings = Field(default_factory=OutlookEmailHookSettings)


class CalendarHookSettings(BaseModel):
    """Calendar-specific hook settings."""
    calendar_ids: List[str] = ["primary"]
    look_ahead_days: int = Field(default=1, gt=0)
    event_types: List[str] = ["meeting", "appointment", "reminder"]
    include_all_day_events: bool = False
    include_recurring_events: bool = True
    min_meeting_duration: int = Field(default=15, gt=0)  # Minimum minutes for prep
    prep_time_minutes: int = Field(default=15, gt=0)  # Minutes before meeting for prep


class CalendarHookConfig(HookConfig):
    """Configuration for calendar input hooks."""
    hook_type: Literal["calendar"] = "calendar"
    hook_settings: CalendarHookSettings = Field(default_factory=CalendarHookSettings)


class CalendarMeetingInfo(BaseModel):
    """Information about a calendar meeting for memo generation."""
    meeting_id: str
    title: str
    attendees: List[str] = []
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    location: str = ""
    description: str = ""
    organizer: str = ""
    calendar_id: str = "primary"
    
    @property
    def attendee_emails(self) -> List[str]:
        """Extract email addresses from attendees."""
        emails = []
        for attendee in self.attendees:
            if isinstance(attendee, dict):
                email = attendee.get('email', '')
                if email:
                    emails.append(email)
            elif isinstance(attendee, str) and '@' in attendee:
                emails.append(attendee)
        return emails


# Union type for all possible hook configs
AnyHookConfig = Union[EmailHookConfig, OutlookEmailHookConfig, CalendarHookConfig, HookConfig]


class InputHooksConfig(BaseModel):
    """Top-level configuration for all input hooks."""
    hooks: Dict[str, AnyHookConfig] = {}
    
    # Global settings
    default_polling_interval: int = 300
    default_queue_name: str = "hooks"
    enable_task_updates: bool = True
    
    class Config:
        extra = "allow"


class HookStatus(BaseModel):
    """Runtime status of a hook."""
    hook_name: str
    enabled: bool
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_result: Optional[ProcessingResult] = None
    error_count: int = 0
    last_error: Optional[str] = None


class HookStats(BaseModel):
    """Statistics for a hook over time."""
    hook_name: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_items_processed: int = 0
    total_tasks_created: int = 0
    total_tasks_updated: int = 0
    average_processing_time: float = 0.0
    last_24h_runs: int = 0
    uptime_percentage: float = 100.0