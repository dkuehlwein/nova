"""
Skill Management API Endpoints

Provides REST API for listing available skills and their metadata.
Implements ADR-014 Phase 6 (Frontend & Observability).
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.logging import get_logger
from utils.skill_manager import get_skill_manager

logger = get_logger("skill-api")
router = APIRouter(prefix="/api/skills", tags=["Skills"])


class SkillInfo(BaseModel):
    """Skill information for API response."""
    name: str
    version: str
    description: str
    author: str
    tags: list[str]


class SkillsListResponse(BaseModel):
    """Response model for listing all skills."""
    skills: list[SkillInfo]
    count: int
    timestamp: str


@router.get("/", response_model=SkillsListResponse)
async def get_skills():
    """
    Get all available skills with their metadata.

    Returns skill manifests for all discovered skills in the skills directory.
    Skills are discovered based on the presence of a manifest.yaml file.
    """
    try:
        skill_manager = get_skill_manager()
        skill_names = skill_manager.list_skills()

        skills = []
        for name in skill_names:
            try:
                manifest = skill_manager.get_manifest(name)
                skills.append(SkillInfo(
                    name=manifest.name,
                    version=manifest.version,
                    description=manifest.description,
                    author=manifest.author,
                    tags=manifest.tags,
                ))
            except Exception as e:
                logger.warning(f"Failed to get manifest for skill {name}: {e}")
                continue

        logger.info(f"Skills list retrieved: {len(skills)} skills available")

        return SkillsListResponse(
            skills=skills,
            count=len(skills),
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to get skills list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve skills: {str(e)}")
