"""
Unit tests for time_tracking skill discovery.

Verifies that SkillManager discovers the time_tracking skill and loads
its manifest with correct metadata. Uses the real skills directory
to ensure the actual manifest.yaml is valid.
"""

from pathlib import Path

import pytest

from models.skill_models import SkillManifest
from utils.skill_manager import SkillManager

# Real skills directory in the repository
SKILLS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "backend" / "skills"


@pytest.fixture
def manager():
    """Create a SkillManager pointing at the real skills directory."""
    return SkillManager(skills_path=SKILLS_PATH)


class TestTimeTrackingDiscovery:
    """Verify SkillManager discovers time_tracking with correct metadata."""

    def test_time_tracking_discovered_in_list_skills(self, manager):
        """SkillManager.list_skills() should include time_tracking."""
        assert "time_tracking" in manager.list_skills()

    def test_time_tracking_manifest_fields(self, manager):
        """Manifest should load with correct metadata fields."""
        manifest = manager.get_manifest("time_tracking")

        assert isinstance(manifest, SkillManifest)
        assert manifest.name == "time_tracking"
        assert manifest.version == "1.0.0"
        assert manifest.author == "nova-team"
        assert "Track work hours" in manifest.description
        assert "Replicon" in manifest.description
        assert set(manifest.tags) == {"time", "tracking", "timesheet", "replicon", "excel"}

    def test_time_tracking_in_skill_summaries(self, manager):
        """get_skill_summaries() should include time_tracking with its description."""
        summaries = manager.get_skill_summaries()
        assert "time_tracking" in summaries
        assert "Track work hours" in summaries["time_tracking"]
