"""
Nova Admin Domain Models

Modern Pydantic V2 models for admin-related API endpoints including overview, 
statistics, and system monitoring.
All models follow latest Pydantic V2 patterns with proper validation and serialization.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class ActivityItem(BaseModel):
    """Individual activity item for the system activity feed."""
    type: str = Field(..., description="Activity type (task_created, task_completed, etc.)")
    title: str = Field(..., description="Activity title")
    description: str = Field(..., description="Activity description")
    time: str = Field(..., description="Human readable time (e.g., '5 minutes ago')")
    timestamp: datetime = Field(..., description="Activity timestamp")
    related_task_id: Optional[UUID] = Field(None, description="Related task ID if applicable")



class TaskDashboard(BaseModel):
    """Consolidated task dashboard data with optional full task details."""
    task_counts: Dict[str, int] = Field(..., description="Task counts by status")
    total_tasks: int = Field(..., description="Total number of tasks")
    pending_decisions: int = Field(..., description="Number of tasks pending decisions")
    recent_activity: List[ActivityItem] = Field(..., description="Recent system activity")
    system_status: str = Field(..., description="Overall system status")
    tasks_by_status: Optional[Dict[str, List[dict]]] = Field(None, description="Full task data by status (optional)")
    cache_info: Optional[Dict[str, Union[str, bool]]] = Field(None, description="Cache metadata") 