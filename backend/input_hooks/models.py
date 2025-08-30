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


class CalendarHookSettings(BaseModel):
    """Calendar-specific hook settings."""
    calendar_ids: List[str] = ["primary"]
    look_ahead_days: int = Field(default=7, gt=0)
    event_types: List[str] = ["meeting", "appointment", "reminder"]
    include_all_day_events: bool = True
    include_recurring_events: bool = True


class CalendarHookConfig(HookConfig):
    """Configuration for calendar input hooks."""
    hook_type: Literal["calendar"] = "calendar"
    hook_settings: CalendarHookSettings = Field(default_factory=CalendarHookSettings)


# Union type for all possible hook configs
AnyHookConfig = Union[EmailHookConfig, CalendarHookConfig, HookConfig]


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