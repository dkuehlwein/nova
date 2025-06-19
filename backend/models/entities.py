"""
Nova Entities Domain Models

Modern Pydantic V2 models for entity-related API endpoints including persons, 
projects, and artifacts.
All models follow latest Pydantic V2 patterns with proper validation and serialization.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Person Models
class PersonCreate(BaseModel):
    """Request model for creating new persons."""
    name: str = Field(..., description="Person name")
    email: str = Field(..., description="Person email address")
    role: Optional[str] = Field(None, description="Person role/title")
    description: Optional[str] = Field(None, description="Person description")
    current_focus: Optional[str] = Field(None, description="Current focus area")


class PersonResponse(BaseModel):
    """Response model for person data."""
    id: UUID = Field(..., description="Person ID")
    name: str = Field(..., description="Person name")
    email: str = Field(..., description="Person email address")
    role: Optional[str] = Field(None, description="Person role/title")
    description: Optional[str] = Field(None, description="Person description")
    current_focus: Optional[str] = Field(None, description="Current focus area")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = ConfigDict(from_attributes=True)


# Project Models
class ProjectCreate(BaseModel):
    """Request model for creating new projects."""
    name: str = Field(..., description="Project name")
    client: str = Field(..., description="Client name")
    booking_code: Optional[str] = Field(None, description="Project booking code")
    summary: Optional[str] = Field(None, description="Project summary")


class ProjectResponse(BaseModel):
    """Response model for project data."""
    id: UUID = Field(..., description="Project ID")
    name: str = Field(..., description="Project name")
    client: str = Field(..., description="Client name")
    booking_code: Optional[str] = Field(None, description="Project booking code")
    summary: Optional[str] = Field(None, description="Project summary")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = ConfigDict(from_attributes=True)


# Artifact Models
class ArtifactCreate(BaseModel):
    """Request model for creating new artifacts."""
    link: str = Field(..., description="Artifact link/URL")
    title: Optional[str] = Field(None, description="Artifact title")
    summary: Optional[str] = Field(None, description="Artifact summary")


class ArtifactResponse(BaseModel):
    """Response model for artifact data."""
    id: UUID = Field(..., description="Artifact ID")
    link: str = Field(..., description="Artifact link/URL")
    title: Optional[str] = Field(None, description="Artifact title")
    summary: Optional[str] = Field(None, description="Artifact summary")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = ConfigDict(from_attributes=True) 