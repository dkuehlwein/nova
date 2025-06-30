"""
Nova Memory Entity Types

Custom entity types for Nova's knowledge graph using Pydantic models.
These types help Graphiti understand and structure the information Nova works with.
"""

from pydantic import BaseModel
from typing import Optional


class Person(BaseModel):
    """Person entity for knowledge graph."""
    full_name: str
    email: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None


class Project(BaseModel):
    """Project entity for knowledge graph."""
    project_name: str
    client: Optional[str] = None
    booking_code: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None


class Email(BaseModel):
    """Email communication entity."""
    subject: Optional[str] = None
    sender: str
    recipients: str
    date: Optional[str] = None


class Artifact(BaseModel):
    """File, document, or resource entity."""
    artifact_name: str
    artifact_type: str  # "file", "link", "document", "presentation"
    path: Optional[str] = None
    description: Optional[str] = None


# Entity types mapping for Graphiti
# These are SUGGESTED types - Graphiti can dynamically create new entity types
# as needed based on content analysis. This just provides structure for common types.
NOVA_ENTITY_TYPES = {
    "Person": Person,
    "Project": Project,
    "Email": Email,
    "Artifact": Artifact,
} 