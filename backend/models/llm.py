"""
LLM Models for API requests and responses.

Pydantic models for LLM model configuration management.
"""

from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class LLMModelConfig(BaseModel):
    """Configuration for LLM model providers."""
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2, le=2)
    presence_penalty: Optional[float] = Field(default=None, ge=-2, le=2)


class LLMModelCreate(BaseModel):
    """Schema for creating a new LLM model configuration."""
    name: str = Field(..., min_length=1, max_length=100)
    model_name: str = Field(..., min_length=1, max_length=200)
    provider: str = Field(..., min_length=1, max_length=50)
    is_default: bool = False
    is_active: bool = True
    config: Dict = Field(default_factory=dict)


class LLMModelUpdate(BaseModel):
    """Schema for updating an existing LLM model configuration."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    model_name: Optional[str] = Field(None, min_length=1, max_length=200)
    provider: Optional[str] = Field(None, min_length=1, max_length=50)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    config: Optional[Dict] = None


class LLMModelResponse(BaseModel):
    """Schema for LLM model configuration responses."""
    id: int
    name: str
    model_name: str
    provider: str
    is_default: bool
    is_active: bool
    config: Dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LLMModelList(BaseModel):
    """Schema for listing multiple LLM model configurations."""
    models: List[LLMModelResponse]
    total: int
    active_count: int
    default_model: Optional[LLMModelResponse] = None


class LLMModelSetDefault(BaseModel):
    """Schema for setting a model as default."""
    model_id: int


class LiteLLMConfigGenerate(BaseModel):
    """Response schema for generated LiteLLM configuration."""
    config: Dict
    message: str
    reload_required: bool = True