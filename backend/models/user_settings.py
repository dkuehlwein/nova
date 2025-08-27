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

from pydantic import BaseModel, Field, field_validator
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
    
    # Chat LLM Settings (Local-First HuggingFace Defaults)
    chat_llm_model: Mapped[str] = mapped_column(String(100), default="qwen3-32b")  # HuggingFace via Cerebras
    chat_llm_temperature: Mapped[float] = mapped_column(Float, default=0.7)  # Higher for creativity
    chat_llm_max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    
    # Memory LLM Settings (Separate from Chat for Flexibility)
    memory_llm_model: Mapped[str] = mapped_column(String(100), default="qwen3-32b")  # Same as chat for consistency
    memory_small_llm_model: Mapped[str] = mapped_column(String(100), default="qwen3-32b")  # Small model for quick operations
    memory_llm_temperature: Mapped[float] = mapped_column(Float, default=0.1)  # Lower for factual accuracy
    memory_llm_max_tokens: Mapped[int] = mapped_column(Integer, default=2048)  # Memory operations token limit
    
    # Embedding Model Settings
    embedding_model: Mapped[str] = mapped_column(String(100), default="qwen3-embedding-4b")  # #1 MTEB leaderboard
    
    # LiteLLM Connection Settings (Base URL only - master key in Tier 2)
    litellm_base_url: Mapped[str] = mapped_column(String(200), default="http://localhost:4000")
    
    # API Key Validation Status (Tier 3 - cached validation results)
    api_key_validation_status: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


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
    
    # Chat LLM Settings (Local-First HuggingFace Defaults)
    chat_llm_model: str = "qwen3-32b"  # HuggingFace via Cerebras
    chat_llm_temperature: float = 0.7  # Higher for creativity
    chat_llm_max_tokens: int = 4096
    
    # Memory LLM Settings (Separate from Chat for Flexibility)
    memory_llm_model: str = "qwen3-32b"  # Same as chat for consistency
    memory_small_llm_model: str = "qwen3-32b"  # Small model for quick operations
    memory_llm_temperature: float = 0.1  # Lower for factual accuracy
    memory_llm_max_tokens: int = 2048  # Memory operations token limit
    
    # Embedding Model Settings
    embedding_model: str = "qwen3-embedding-4b"  # #1 MTEB leaderboard
    
    # LiteLLM Connection Settings (Base URL only - master key in Tier 2)
    litellm_base_url: str = "http://localhost:4000"
    
    # API Key Validation Status
    api_key_validation_status: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('api_key_validation_status', mode='before')
    @classmethod
    def validate_api_key_status(cls, v):
        """Ensure api_key_validation_status is never None."""
        return v if v is not None else {}

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
    
    # Chat LLM Settings
    chat_llm_model: Optional[str] = None
    chat_llm_temperature: Optional[float] = None
    chat_llm_max_tokens: Optional[int] = None
    
    # Memory LLM Settings
    memory_llm_model: Optional[str] = None
    memory_small_llm_model: Optional[str] = None
    memory_llm_temperature: Optional[float] = None
    memory_llm_max_tokens: Optional[int] = None
    
    # Embedding Model Settings
    embedding_model: Optional[str] = None
    
    # LiteLLM Connection Settings (Base URL only - master key in Tier 2)
    litellm_base_url: Optional[str] = None
    
    # API Key Validation Status
    api_key_validation_status: Optional[Dict[str, Any]] = None


class OnboardingStatusModel(BaseModel):
    """
    Model for onboarding status checks.
    """
    onboarding_complete: bool
    missing_required_settings: list[str] = Field(default_factory=list)
    setup_required: bool = True