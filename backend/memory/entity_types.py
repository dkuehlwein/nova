"""
Nova Memory Entity Types - schema.org Aligned

Defines SUGGESTED entity types for Nova's knowledge graph using Pydantic models.
These guide Graphiti's LLM extraction but don't constrain it - Graphiti can
dynamically create additional types as needed.

Design Philosophy:
- Define core types that need structured attributes
- Let Graphiti discover additional types dynamically
- Use schema.org vocabulary for semantic clarity
- Keep it minimal - only add types when you need specific attributes

References:
- schema.org: https://schema.org/
- W3C ORG: https://www.w3.org/TR/vocab-org/
- Graphiti: https://github.com/getzep/graphiti

Type Selection Criteria:
─────────────────────────────────────────────
Only define a type here if you need:
1. Specific structured attributes (not just a name)
2. Consistent extraction across documents
3. Type-specific business logic

Types NOT defined here will still be extracted by Graphiti
with a generic Entity type (name + labels).
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


# =============================================================================
# CORE ENTITY TYPES (schema.org aligned)
# =============================================================================
# Only types that need specific structured attributes

class Organization(BaseModel):
    """
    Organization entity - aligned with schema.org/Organization.

    Use for: companies, departments, teams, institutions.
    Graphiti will automatically extract relationships like WORKS_FOR, MEMBER_OF.
    """
    name: str = Field(..., description="Official name")
    organization_type: Optional[Literal["company", "department", "team", "institution", "other"]] = None
    industry: Optional[str] = Field(None, description="Industry sector (e.g., 'Technology', 'Consulting')")
    url: Optional[str] = None


class Person(BaseModel):
    """
    Person entity - aligned with schema.org/Person.

    Contact info and role are important for a personal assistant.
    Graphiti will automatically extract relationships to organizations.
    """
    name: str = Field(..., description="Full name")
    email: Optional[str] = None
    job_title: Optional[str] = None
    telephone: Optional[str] = None


class CourseInstance(BaseModel):
    """
    Specific offering of a training/course - aligned with schema.org/CourseInstance.

    Why CourseInstance over Course?
    - Course = curriculum/program definition (rarely needed as structured data)
    - CourseInstance = specific offering with dates/location (actionable for a PA)

    The LLM will infer the parent Course relationship automatically.
    """
    name: str = Field(..., description="Instance name (often includes date/cohort)")
    start_date: Optional[str] = Field(None, description="ISO format date")
    end_date: Optional[str] = Field(None, description="ISO format date")
    location: Optional[str] = None
    course_mode: Optional[Literal["online", "onsite", "blended"]] = None


class Event(BaseModel):
    """
    Time-bound occurrence - aligned with schema.org/Event.

    Use for: meetings, conferences, workshops.
    NOT for recurring training programs (use CourseInstance).
    """
    name: str = Field(..., description="Event name")
    event_type: Optional[Literal["meeting", "conference", "workshop", "webinar", "presentation", "other"]] = None
    start_date: Optional[str] = Field(None, description="ISO format datetime")
    end_date: Optional[str] = Field(None, description="ISO format datetime")
    location: Optional[str] = None


class Project(BaseModel):
    """
    Collaborative endeavor - aligned with schema.org/Project (pending).

    Use for: internal work items, client engagements, initiatives.
    """
    name: str = Field(..., description="Project name")
    status: Optional[Literal["planned", "active", "completed", "on_hold", "cancelled"]] = None
    start_date: Optional[str] = Field(None, description="ISO format date")
    end_date: Optional[str] = Field(None, description="ISO format date")


class Identifier(BaseModel):
    """
    Business identifier - project codes, booking codes, cost centers.

    Custom type (no direct schema.org equivalent).
    Important for business context - links codes to what they identify.
    """
    value: str = Field(..., description="The identifier value (e.g., '740020199')")
    identifier_type: Literal["project_code", "booking_code", "cost_center", "mtg_code", "other"]


class CreativeWork(BaseModel):
    """
    Creative content - aligned with schema.org/CreativeWork.

    Use for: presentations, demos, documents, videos, templates, code samples.
    Enables queries like "find me an AI demo for finance".

    schema.org subtypes we collapse into this:
    - PresentationDigitalDocument, TextDigitalDocument, SpreadsheetDigitalDocument
    - VideoObject, AudioObject, ImageObject
    - SoftwareSourceCode
    """
    name: str = Field(..., description="Asset name or title")
    content_type: Optional[Literal["presentation", "document", "spreadsheet", "video", "audio", "image", "code", "demo", "template", "other"]] = None
    topics: Optional[str] = Field(None, description="Comma-separated topics/tags (e.g., 'AI, finance, automation')")
    audience: Optional[str] = Field(None, description="Target audience (e.g., 'executives', 'developers', 'finance team')")
    url: Optional[str] = Field(None, description="URL, file path, or storage location")
    date_created: Optional[str] = Field(None, description="ISO format date")


# =============================================================================
# ENTITY TYPES REGISTRY
# =============================================================================

NOVA_ENTITY_TYPES = {
    "Organization": Organization,
    "Person": Person,
    "CourseInstance": CourseInstance,
    "Event": Event,
    "Project": Project,
    "Identifier": Identifier,
    "CreativeWork": CreativeWork,
}
"""
Entity types passed to Graphiti's add_episode().

These are SUGGESTIONS - Graphiti will:
1. Try to classify entities into these types
2. Extract the structured attributes defined above
3. Create new types dynamically if needed (with generic attributes)

Types intentionally NOT included:
- Course: CourseInstance captures actionable info; Course is just context
- EmailMessage: Handled by email processing, not knowledge extraction
- DigitalDocument: Generic artifacts don't need structured attributes
"""


# =============================================================================
# EDGE TYPE CONSTRAINTS (optional)
# =============================================================================

NOVA_EDGE_TYPE_MAP = {
    # (source_type, target_type) -> allowed edge types
    # Only define if you need to CONSTRAIN what edges can be created
    # Otherwise let Graphiti infer relationships freely

    ("Person", "Organization"): ["WORKS_FOR", "MEMBER_OF", "AFFILIATED_WITH"],
    ("Person", "Person"): ["REPORTS_TO", "KNOWS", "COLLEAGUE_OF"],
    ("CourseInstance", "Person"): ["ATTENDEE", "INSTRUCTOR"],
    ("Identifier", "Project"): ["IDENTIFIES"],
    ("Identifier", "CourseInstance"): ["IDENTIFIES"],
    ("CreativeWork", "Person"): ["AUTHOR", "CONTRIBUTOR"],
    ("CreativeWork", "Organization"): ["ABOUT", "PUBLISHER"],
    ("CreativeWork", "Project"): ["PART_OF", "DOCUMENTS"],
}
"""
Optional edge type constraints.

Only define mappings where you need to ensure consistency.
Unmapped (source, target) pairs will use Graphiti's default behavior.

Common edge types (schema.org aligned):
- WORKS_FOR (schema:worksFor) - employment
- MEMBER_OF (schema:memberOf) - membership
- REPORTS_TO (org:reportsTo) - hierarchy
- ATTENDEE (schema:attendee) - participation
- INSTRUCTOR (schema:instructor) - teaching
- IDENTIFIES (custom) - code → entity mapping
"""


# =============================================================================
# CUSTOM EXTRACTION INSTRUCTIONS
# =============================================================================

NOVA_EXTRACTION_INSTRUCTIONS = """
Extract entities using schema.org vocabulary (https://schema.org/).
Use the provided entity types when appropriate; create new schema.org-aligned types if needed.

EXTRACTION GUIDANCE:

1. PEOPLE: Look beyond explicit mentions.
   - Email signatures contain name, title, phone, organization
   - CC/To lists reveal team members and stakeholders
   - "Lisa's manager" or "reporting to John" reveals hierarchy

2. ORGANIZATIONS: Distinguish levels.
   - "Nextera Consulting" = company
   - "Cloud & Infrastructure" = department
   - "DL DE Cloud Services" = team (distribution lists are teams)

3. IDENTIFIERS: Capture business codes with context.
   - "MTG code: 740020199" → Identifier linked to what it funds
   - "Project code for the bootcamp" → IDENTIFIES relationship

4. RELATIONSHIPS: Infer from behavior, not just statements.
   - Person answers questions about X → likely responsible for X
   - Person waits for approval from Y → Y is superior/approver
   - Person executes requests for Z → supports Z's initiative

5. DATES: Always ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
   Resolve relative dates ("next week", "last year") to absolute dates.

6. GERMAN BUSINESS CONTEXT: Common patterns.
   - "DL DE" prefix = German distribution list
   - Email format: firstname.lastname@domain
   - Titles after comma: "Müller, Anna" = Anna Müller
"""
"""
Custom instructions passed to Graphiti's entity extraction prompt.

This guides the LLM on WHAT to extract and HOW to interpret it,
without needing to define rigid schemas for every possible type.
"""
