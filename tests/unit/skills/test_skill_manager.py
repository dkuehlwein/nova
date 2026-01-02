"""
Unit tests for the SkillManager and skill system.

Tests skill discovery, loading, tool namespacing, and error handling.

These tests are isolated unit tests that don't require the database or
full Nova infrastructure.
"""

import os
import sys

# Add backend to path for imports before any other imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Disable database-related imports for these tests
os.environ.setdefault("NOVA_SKIP_DB", "1")

import pytest
from pathlib import Path

from models.skill_models import (
    SkillActivation,
    SkillDefinition,
    SkillLoadError,
    SkillManifest,
    SkillNotFoundError,
)
from utils.skill_manager import SkillManager, set_skill_manager


@pytest.fixture
def skills_path(tmp_path):
    """Create a temporary skills directory with test skills."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create a valid test skill
    test_skill_dir = skills_dir / "test_skill"
    test_skill_dir.mkdir()

    # Create manifest
    manifest_content = """
name: test_skill
version: "1.0.0"
description: "A test skill for unit testing"
author: test-team
tags: [test, unit]
"""
    (test_skill_dir / "manifest.yaml").write_text(manifest_content)

    # Create instructions
    instructions_content = """
# Test Skill Instructions

This is a test skill for unit testing.

## Usage
Use the test_tool to perform testing operations.
"""
    (test_skill_dir / "instructions.md").write_text(instructions_content)

    # Create tools
    tools_content = '''
"""Test skill tools."""
from langchain_core.tools import tool

@tool
def test_tool(input: str) -> str:
    """A test tool that echoes input."""
    return f"Echo: {input}"

def get_tools():
    """Return all tools for this skill."""
    return [test_tool]
'''
    (test_skill_dir / "tools.py").write_text(tools_content)

    # Create an invalid skill (missing instructions)
    invalid_skill_dir = skills_dir / "invalid_skill"
    invalid_skill_dir.mkdir()
    (invalid_skill_dir / "manifest.yaml").write_text(manifest_content.replace("test_skill", "invalid_skill"))
    # No instructions.md - this makes it invalid

    return skills_dir


class TestSkillManager:
    """Tests for SkillManager class."""

    def test_init_creates_directory_if_missing(self, tmp_path):
        """SkillManager should create skills directory if it doesn't exist."""
        skills_path = tmp_path / "nonexistent" / "skills"
        assert not skills_path.exists()

        manager = SkillManager(skills_path=skills_path)

        assert skills_path.exists()
        assert manager.list_skills() == []

    def test_skill_discovery(self, skills_path):
        """SkillManager should discover valid skills on init."""
        manager = SkillManager(skills_path=skills_path)

        skills = manager.list_skills()
        assert "test_skill" in skills

    def test_get_skill_summaries(self, skills_path):
        """get_skill_summaries should return name -> description mapping."""
        manager = SkillManager(skills_path=skills_path)

        summaries = manager.get_skill_summaries()

        assert "test_skill" in summaries
        assert summaries["test_skill"] == "A test skill for unit testing"

    def test_get_manifest(self, skills_path):
        """get_manifest should return SkillManifest for valid skill."""
        manager = SkillManager(skills_path=skills_path)

        manifest = manager.get_manifest("test_skill")

        assert isinstance(manifest, SkillManifest)
        assert manifest.name == "test_skill"
        assert manifest.version == "1.0.0"
        assert manifest.author == "test-team"
        assert "test" in manifest.tags

    def test_get_manifest_not_found(self, skills_path):
        """get_manifest should raise SkillNotFoundError for unknown skill."""
        manager = SkillManager(skills_path=skills_path)

        with pytest.raises(SkillNotFoundError):
            manager.get_manifest("nonexistent_skill")

    @pytest.mark.asyncio
    async def test_load_skill(self, skills_path):
        """load_skill should return complete SkillDefinition."""
        manager = SkillManager(skills_path=skills_path)

        skill = await manager.load_skill("test_skill")

        assert isinstance(skill, SkillDefinition)
        assert skill.manifest.name == "test_skill"
        assert "Test Skill Instructions" in skill.instructions
        assert len(skill.tools) == 1
        assert skill.tools[0].name == "test_tool"

    @pytest.mark.asyncio
    async def test_load_skill_not_found(self, skills_path):
        """load_skill should raise SkillNotFoundError for unknown skill."""
        manager = SkillManager(skills_path=skills_path)

        with pytest.raises(SkillNotFoundError):
            await manager.load_skill("nonexistent_skill")

    @pytest.mark.asyncio
    async def test_load_skill_missing_instructions(self, skills_path):
        """load_skill should raise SkillLoadError for skill missing instructions."""
        manager = SkillManager(skills_path=skills_path)

        with pytest.raises(SkillLoadError) as exc_info:
            await manager.load_skill("invalid_skill")

        assert "missing instructions.md" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_skill_tools_namespaced(self, skills_path):
        """get_skill_tools should return namespaced tools."""
        manager = SkillManager(skills_path=skills_path)

        tools = await manager.get_skill_tools("test_skill", namespace=True)

        assert len(tools) >= 1
        tool_names = [t.name for t in tools]
        assert "test_skill__test_tool" in tool_names

    @pytest.mark.asyncio
    async def test_get_skill_tools_not_namespaced(self, skills_path):
        """get_skill_tools with namespace=False should return original names."""
        manager = SkillManager(skills_path=skills_path)

        tools = await manager.get_skill_tools("test_skill", namespace=False)

        assert len(tools) >= 1
        tool_names = [t.name for t in tools]
        assert "test_tool" in tool_names

    def test_reload(self, skills_path):
        """reload should rescan skills directory."""
        manager = SkillManager(skills_path=skills_path)
        initial_skills = manager.list_skills()

        # Create a new skill
        new_skill_dir = skills_path / "new_skill"
        new_skill_dir.mkdir()
        (new_skill_dir / "manifest.yaml").write_text("""
name: new_skill
version: "1.0.0"
description: "A newly added skill"
""")

        # Reload
        manager.reload()

        # New skill should be discovered
        assert "new_skill" in manager.list_skills()
        assert len(manager.list_skills()) == len(initial_skills) + 1


class TestSkillModels:
    """Tests for skill-related Pydantic models."""

    def test_skill_manifest_validation(self):
        """SkillManifest should validate correctly."""
        manifest = SkillManifest(
            name="test",
            version="1.0.0",
            description="Test description"
        )

        assert manifest.name == "test"
        assert manifest.author == "nova-team"  # Default
        assert manifest.tags == []  # Default

    def test_skill_manifest_with_all_fields(self):
        """SkillManifest should accept all optional fields."""
        manifest = SkillManifest(
            name="test",
            version="2.0.0",
            description="Test",
            author="custom-author",
            tags=["tag1", "tag2"]
        )

        assert manifest.author == "custom-author"
        assert manifest.tags == ["tag1", "tag2"]

    def test_skill_activation_typing(self):
        """SkillActivation TypedDict should work correctly."""
        activation: SkillActivation = {
            "activated_at_turn": 5,
            "tools": ["skill__tool1", "skill__tool2"]
        }

        assert activation["activated_at_turn"] == 5
        assert len(activation["tools"]) == 2


class TestSkillToolsIntegration:
    """Integration tests for skill tools with the skill manager."""

    @pytest.mark.asyncio
    async def test_enable_skill_tool(self, skills_path):
        """enable_skill tool should return instructions and tool list."""
        # Set up the skill manager
        manager = SkillManager(skills_path=skills_path)
        set_skill_manager(manager)

        # Import and invoke the tool
        from tools.skill_tools import enable_skill

        result = await enable_skill.ainvoke({"skill_name": "test_skill"})

        assert "Skill Activated: test_skill" in result
        assert "Test Skill Instructions" in result
        assert "test_skill__test_tool" in result

    @pytest.mark.asyncio
    async def test_enable_skill_not_found(self, skills_path):
        """enable_skill should return error for unknown skill."""
        manager = SkillManager(skills_path=skills_path)
        set_skill_manager(manager)

        from tools.skill_tools import enable_skill

        result = await enable_skill.ainvoke({"skill_name": "nonexistent"})

        assert "Unknown skill 'nonexistent'" in result
        assert "test_skill" in result  # Should list available skills

    @pytest.mark.asyncio
    async def test_disable_skill_tool(self, skills_path):
        """disable_skill tool should return confirmation."""
        manager = SkillManager(skills_path=skills_path)
        set_skill_manager(manager)

        from tools.skill_tools import disable_skill

        result = await disable_skill.ainvoke({"skill_name": "test_skill"})

        assert "deactivated" in result
        assert "test_skill" in result
