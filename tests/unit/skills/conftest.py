"""Shared fixtures for time tracking skill tests."""

from unittest.mock import patch

import pytest


@pytest.fixture
def mock_config(tmp_path):
    """Provide a mock config without touching real files on disk.

    Patches _load_skill_config and _save_skill_config in the tools module
    so that no real config.yaml is read or written.  Uses tmp_path for
    directory paths to ensure test isolation.
    """
    config = {
        "timesheet_dir": str(tmp_path / "timesheets"),
        "templates_dir": str(tmp_path / "templates"),
        "output_dir": str(tmp_path / "output"),
        "projects": [
            {
                "id": "PRJA-001",
                "name": "ClientA - Development",
                "replicon_project": "Project A",
                "client_adapter": "client_a",
            },
            {
                "id": "INT-001",
                "name": "Internal - Meetings",
                "replicon_project": "Internal",
                "client_adapter": None,
            },
        ],
    }

    # Use a mutable container so save updates are visible to subsequent loads
    state = {"config": config}

    def fake_load():
        # Return a copy so callers mutating the dict don't break future loads
        import copy
        return copy.deepcopy(state["config"])

    def fake_save(new_config):
        import copy
        state["config"] = copy.deepcopy(new_config)

    with (
        patch("skills.time_tracking.tools._load_skill_config", side_effect=fake_load),
        patch("skills.time_tracking.tools._save_skill_config", side_effect=fake_save),
    ):
        yield config
