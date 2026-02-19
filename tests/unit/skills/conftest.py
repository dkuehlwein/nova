"""Shared fixtures for time tracking skill tests."""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config.yaml for the skill."""
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

    config_path = Path(__file__).parents[3] / "backend" / "skills" / "time_tracking" / "config.yaml"
    config_path.write_text(yaml.dump(config))
    yield config
    config_path.unlink(missing_ok=True)
