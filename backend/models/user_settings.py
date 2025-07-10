"""
User Settings Models for Nova's 3-Tier Configuration System

Tier 3: User Settings (Database)
- Runtime configurable user preferences
- Stored in database for persistence
- Can be updated via API endpoints
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Integer, String, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from models.models import Base


class UserSettings(Base):
    """
    Tier 3 user settings stored in database.
    These are runtime-configurable preferences that can be updated via API.
    """
    __tablename__ = 'user_settings'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Onboarding flag
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # User Profile Settings (migrated from user_profile.yaml)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Email Integration Settings
    email_polling_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_polling_interval: Mapped[int] = mapped_column(Integer, default=300)  # seconds
    email_create_tasks: Mapped[bool] = mapped_column(Boolean, default=True)
    email_max_per_fetch: Mapped[int] = mapped_column(Integer, default=10)
    email_label_filter: Mapped[str] = mapped_column(String(100), default="INBOX")
    
    # Notification Preferences
    notification_preferences: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Task Defaults
    task_defaults: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Agent Settings
    agent_polling_interval: Mapped[int] = mapped_column(Integer, default=30)  # seconds
    agent_error_retry_interval: Mapped[int] = mapped_column(Integer, default=60)  # seconds
    
    # Memory Settings
    memory_search_limit: Mapped[int] = mapped_column(Integer, default=10)  # max results
    memory_token_limit: Mapped[int] = mapped_column(Integer, default=32000)  # max tokens for LLM
    
    # MCP Server Preferences (which servers are enabled/disabled)
    mcp_server_preferences: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # LLM Settings
    llm_model: Mapped[str] = mapped_column(String(100), default="hf.co/unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF:Q8_K_XL")
    llm_provider: Mapped[str] = mapped_column(String(50), default="ollama")  # ollama or google
    llm_temperature: Mapped[float] = mapped_column(Float, default=0.6)
    llm_max_tokens: Mapped[int] = mapped_column(Integer, default=64000)


class UserSettingsModel(BaseModel):
    """
    Pydantic model for user settings API operations.
    """
    id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Onboarding
    onboarding_complete: bool = False
    
    # User Profile
    full_name: Optional[str] = None
    email: Optional[str] = None
    timezone: str = "UTC"
    notes: Optional[str] = None
    
    # Email Integration
    email_polling_enabled: bool = True
    email_polling_interval: int = 300
    email_create_tasks: bool = True
    email_max_per_fetch: int = 10
    email_label_filter: str = "INBOX"
    
    # Notifications
    notification_preferences: Dict[str, Any] = Field(default_factory=dict)
    
    # Task Defaults
    task_defaults: Dict[str, Any] = Field(default_factory=dict)
    
    # Agent Settings
    agent_polling_interval: int = 30
    agent_error_retry_interval: int = 60
    
    # Memory Settings
    memory_search_limit: int = 10
    memory_token_limit: int = 32000
    
    # MCP Server Preferences
    mcp_server_preferences: Dict[str, Any] = Field(default_factory=dict)
    
    # LLM Settings
    llm_model: str = "gemma3-12b-local"
    llm_provider: str = "ollama"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 64000

    class Config:
        from_attributes = True


class UserSettingsUpdateModel(BaseModel):
    """
    Pydantic model for updating user settings.
    All fields are optional for partial updates.
    """
    # User Profile
    full_name: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None
    notes: Optional[str] = None
    
    # Email Integration
    email_polling_enabled: Optional[bool] = None
    email_polling_interval: Optional[int] = None
    email_create_tasks: Optional[bool] = None
    email_max_per_fetch: Optional[int] = None
    email_label_filter: Optional[str] = None
    
    # Notifications
    notification_preferences: Optional[Dict[str, Any]] = None
    
    # Task Defaults
    task_defaults: Optional[Dict[str, Any]] = None
    
    # Agent Settings
    agent_polling_interval: Optional[int] = None
    agent_error_retry_interval: Optional[int] = None
    
    # Memory Settings
    memory_search_limit: Optional[int] = None
    memory_token_limit: Optional[int] = None
    
    # MCP Server Preferences
    mcp_server_preferences: Optional[Dict[str, Any]] = None
    
    # LLM Settings
    llm_model: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None


class OnboardingStatusModel(BaseModel):
    """
    Model for onboarding status checks.
    """
    onboarding_complete: bool
    missing_required_settings: list[str] = Field(default_factory=list)
    setup_required: bool = True