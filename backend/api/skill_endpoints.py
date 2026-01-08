"""
Skill Management API Endpoints

Provides REST API for listing available skills and their metadata,
and for viewing/editing skill configuration files.
Implements ADR-014 Phase 6 (Frontend & Observability).
"""

import os
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.skill_models import (
    SkillConfigResponse,
    SkillConfigUpdateRequest,
    SkillConfigUpdateResponse,
)
from utils.logging import get_logger
from utils.skill_manager import get_skill_manager

logger = get_logger("skill-api")
router = APIRouter(prefix="/api/skills", tags=["Skills"])

# Maximum config file size (1MB)
MAX_CONFIG_SIZE = 1024 * 1024


class SkillInfo(BaseModel):
    """Skill information for API response."""
    name: str
    version: str
    description: str
    author: str
    tags: list[str]
    has_config: bool = False


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
                skill_path = skill_manager.skills_path / name
                config_exists = (skill_path / "config.yaml").exists()
                skills.append(SkillInfo(
                    name=manifest.name,
                    version=manifest.version,
                    description=manifest.description,
                    author=manifest.author,
                    tags=manifest.tags,
                    has_config=config_exists,
                ))
            except Exception as e:
                logger.warning(f"Failed to get manifest for skill {name}: {e}")
                continue

        logger.info(f"Skills list retrieved: {len(skills)} skills available")

        return SkillsListResponse(
            skills=skills,
            count=len(skills),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to get skills list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve skills: {str(e)}")


def _get_skill_config_path(skill_name: str) -> Path:
    """
    Get the config.yaml path for a skill, validating skill exists.

    Includes path traversal protection to ensure the resolved path
    stays within the skills directory.
    """
    skill_manager = get_skill_manager()
    skill_names = skill_manager.list_skills()

    if skill_name not in skill_names:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    skill_path = skill_manager.skills_path / skill_name
    config_path = skill_path / "config.yaml"

    # Security: Ensure path doesn't escape skills directory (defense in depth)
    try:
        config_path.resolve().relative_to(skill_manager.skills_path.resolve())
    except ValueError:
        logger.error(
            "Path traversal attempt detected",
            extra={"data": {"skill_name": skill_name, "resolved_path": str(config_path.resolve())}},
        )
        raise HTTPException(status_code=403, detail="Invalid skill name")

    return config_path


@router.get("/{skill_name}/config", response_model=SkillConfigResponse)
async def get_skill_config(skill_name: str):
    """
    Get the configuration file content for a specific skill.

    Returns the raw YAML content of the skill's config.yaml file.
    Returns 404 if the skill doesn't exist or doesn't have a config file.
    """
    try:
        config_path = _get_skill_config_path(skill_name)

        if not config_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Skill '{skill_name}' does not have a config.yaml file"
            )

        try:
            content = config_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.error(
                f"Config file encoding error: {skill_name}",
                extra={"data": {"skill_name": skill_name, "path": str(config_path)}},
            )
            raise HTTPException(
                status_code=500,
                detail="Config file has invalid UTF-8 encoding"
            )

        stat = config_path.stat()

        logger.info(
            f"Skill config retrieved: {skill_name}",
            extra={"data": {"skill_name": skill_name, "size": stat.st_size}},
        )

        return SkillConfigResponse(
            skill_name=skill_name,
            content=content,
            file_path=f"skills/{skill_name}/config.yaml",
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            size_bytes=stat.st_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get skill config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve skill config: {str(e)}")


@router.put("/{skill_name}/config", response_model=SkillConfigUpdateResponse)
async def update_skill_config(skill_name: str, request: SkillConfigUpdateRequest):
    """
    Update the configuration file for a specific skill.

    Validates YAML syntax before saving. Returns 400 if YAML is invalid.
    Hot-reload is automatic via the existing file watcher.
    """
    try:
        config_path = _get_skill_config_path(skill_name)

        if not config_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Skill '{skill_name}' does not have a config.yaml file"
            )

        # Check content size
        if len(request.content) > MAX_CONFIG_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Config file too large (max {MAX_CONFIG_SIZE} bytes)"
            )

        # Validate YAML syntax
        try:
            yaml.safe_load(request.content)
        except yaml.YAMLError as e:
            logger.warning(
                f"Invalid YAML in skill config update: {skill_name}",
                extra={"data": {"skill_name": skill_name, "error": str(e)}},
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid YAML syntax: {str(e)}"
            )

        # Atomic write using temp file + rename to prevent race conditions
        temp_fd = None
        temp_path = None
        try:
            temp_fd, temp_path = tempfile.mkstemp(
                dir=config_path.parent,
                prefix=f".{config_path.name}.",
                suffix=".tmp"
            )
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                temp_fd = None  # fd is now owned by the file object
                f.write(request.content)
            shutil.move(temp_path, config_path)
            temp_path = None  # Successfully moved
        except Exception as write_error:
            if temp_fd is not None:
                os.close(temp_fd)
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            raise write_error

        stat = config_path.stat()

        logger.info(
            f"Skill config updated: {skill_name}",
            extra={"data": {"skill_name": skill_name, "size": stat.st_size}},
        )

        return SkillConfigUpdateResponse(
            skill_name=skill_name,
            content=request.content,
            file_path=f"skills/{skill_name}/config.yaml",
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            size_bytes=stat.st_size,
            message="Configuration saved successfully. Hot-reload applied.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update skill config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update skill config: {str(e)}")
