"""
Nova Memory Entity Types

Custom entity types for Nova's knowledge graph using Pydantic models.
These types help Graphiti understand and structure the information Nova works with.

Entity Hierarchy:
- Company: Base entity for organizations (clients, vendors, partners)
  - Attributes: industry, relationship_type (client, vendor, partner)
- Person: Individuals linked to companies via relationships
- Project: Work items linked to companies and people
- ProjectCode: Booking/billing codes for projects
- Email: Communication records
- Artifact: Files, documents, resources
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class Company(BaseModel):
    """
    Company entity - base type for all organizations.

    Whether a company is a client, vendor, or partner is expressed via:
    1. The relationship_type attribute
    2. Relationship edges in the graph (e.g., PROJECT -> HAS_CLIENT -> Company)
    """
    company_name: str = Field(..., description="Official company name")
    industry: Optional[str] = Field(None, description="Industry sector (e.g., 'Technology', 'Finance', 'Healthcare')")
    relationship_type: Optional[Literal["client", "vendor", "partner", "other"]] = Field(
        None,
        description="Primary relationship type with Nova's organization"
    )
    website: Optional[str] = Field(None, description="Company website URL")
    notes: Optional[str] = Field(None, description="Additional context about the company")


class Person(BaseModel):
    """
    Person entity for individuals in the knowledge graph.

    Company relationships are expressed via edges, not embedded here.
    E.g., Person -> WORKS_FOR -> Company, Person -> CONTACT_AT -> Company
    """
    full_name: str = Field(..., description="Full name of the person")
    email: Optional[str] = Field(None, description="Email address")
    role: Optional[str] = Field(None, description="Job title or role")
    phone: Optional[str] = Field(None, description="Phone number")


class Project(BaseModel):
    """
    Project entity for work items and engagements.

    Client relationships are expressed via edges:
    - Project -> HAS_CLIENT -> Company
    - Project -> ASSIGNED_TO -> Person
    - Project -> HAS_CODE -> ProjectCode
    """
    project_name: str = Field(..., description="Name of the project")
    description: Optional[str] = Field(None, description="Brief project description")
    status: Optional[Literal["active", "completed", "on_hold", "cancelled"]] = Field(
        None,
        description="Current project status"
    )
    start_date: Optional[str] = Field(None, description="Project start date (ISO format)")
    end_date: Optional[str] = Field(None, description="Project end date (ISO format)")


class ProjectCode(BaseModel):
    """
    Project code / booking code entity.

    Used for time tracking, billing, and project identification.
    Links to projects via edges: ProjectCode -> IDENTIFIES -> Project
    """
    code: str = Field(..., description="The project/booking code (e.g., 'ACME-2024-001')")
    code_type: Optional[Literal["booking", "billing", "internal", "external"]] = Field(
        None,
        description="Type of code"
    )
    description: Optional[str] = Field(None, description="What this code is used for")
    valid_from: Optional[str] = Field(None, description="Code validity start date")
    valid_until: Optional[str] = Field(None, description="Code validity end date")


class Email(BaseModel):
    """Email communication entity."""
    subject: Optional[str] = Field(None, description="Email subject line")
    sender: str = Field(..., description="Sender email address")
    recipients: str = Field(..., description="Comma-separated recipient addresses")
    date: Optional[str] = Field(None, description="Email date (ISO format)")
    thread_id: Optional[str] = Field(None, description="Email thread identifier")


class Artifact(BaseModel):
    """File, document, or resource entity."""
    artifact_name: str = Field(..., description="Name of the artifact")
    artifact_type: Literal["file", "link", "document", "presentation", "spreadsheet", "image", "other"] = Field(
        ...,
        description="Type of artifact"
    )
    path: Optional[str] = Field(None, description="File path or URL")
    description: Optional[str] = Field(None, description="What this artifact contains or is used for")
    mime_type: Optional[str] = Field(None, description="MIME type if applicable")


class Meeting(BaseModel):
    """Meeting or calendar event entity."""
    title: str = Field(..., description="Meeting title")
    meeting_type: Optional[Literal["call", "video", "in_person", "workshop", "presentation"]] = Field(
        None,
        description="Type of meeting"
    )
    scheduled_time: Optional[str] = Field(None, description="Scheduled date/time (ISO format)")
    duration_minutes: Optional[int] = Field(None, description="Meeting duration in minutes")
    location: Optional[str] = Field(None, description="Meeting location or video link")


class Task(BaseModel):
    """
    Task entity for action items and todos.

    Note: This is distinct from Nova's internal Task model in the database.
    This represents tasks mentioned in conversations/emails for the knowledge graph.
    """
    task_title: str = Field(..., description="Brief task description")
    status: Optional[Literal["pending", "in_progress", "completed", "cancelled"]] = Field(
        None,
        description="Task status"
    )
    priority: Optional[Literal["low", "medium", "high", "urgent"]] = Field(
        None,
        description="Task priority"
    )
    due_date: Optional[str] = Field(None, description="Due date (ISO format)")


# Entity types mapping for Graphiti
# These are SUGGESTED types - Graphiti can dynamically create new entity types
# as needed based on content analysis. This provides structure for common types.
NOVA_ENTITY_TYPES = {
    # Organizations
    "Company": Company,

    # People
    "Person": Person,

    # Work items
    "Project": Project,
    "ProjectCode": ProjectCode,
    "Task": Task,

    # Communications
    "Email": Email,
    "Meeting": Meeting,

    # Resources
    "Artifact": Artifact,
}
