"""
Skill system models for Nova's dynamic pluggable skills.

These models define the structure for skill manifests, activation state,
and full skill definitions used by the SkillManager.
"""

from typing import Any, TypedDict
from pydantic import BaseModel, Field


class SkillManifest(BaseModel):
    """
    Metadata for a skill, loaded from manifest.yaml.

    This is the lightweight representation used for discovery and
    displaying available skills in the system prompt.
    """
    name: str = Field(..., description="Unique skill identifier (directory name)")
    version: str = Field(..., description="Semantic version of the skill")
    description: str = Field(..., description="Short description for LLM discovery")
    author: str = Field(default="nova-team", description="Skill author or team")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")


class SkillActivation(TypedDict):
    """
    Metadata for an active skill in agent state.

    Tracks when a skill was activated and what tools it provides,
    enabling proper cleanup and state management.
    """
    activated_at_turn: int  # Turn number when skill was activated
    tools: list[str]  # Tool names provided by this skill (namespaced)


class SkillDefinition(BaseModel):
    """
    Full skill definition including all loaded components.

    This is the complete representation used when a skill is activated,
    containing the manifest, instructions, and loaded tool instances.
    """
    manifest: SkillManifest
    instructions: str = Field(..., description="Full instructions markdown content")
    tools: list[Any] = Field(default_factory=list, description="Loaded BaseTool instances")

    class Config:
        arbitrary_types_allowed = True  # Allow BaseTool instances


class SkillNotFoundError(Exception):
    """Raised when a requested skill does not exist."""
    pass


class SkillLoadError(Exception):
    """Raised when a skill fails to load (bad manifest, tools, etc.)."""
    pass
