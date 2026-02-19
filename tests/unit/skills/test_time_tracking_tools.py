"""Tests for time tracking skill tools."""

import json
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


class TestLogHours:
    @pytest.mark.asyncio
    async def test_log_hours_writes_entries(self, mock_config):
        """log_hours tool writes entries to master Excel."""
        from skills.time_tracking.tools import log_hours

        result_str = await log_hours.ainvoke({
            "entries_json": json.dumps([
                {
                    "date": "2026-02-03",
                    "project": "ClientA - Development",
                    "project_id": "PRJA-001",
                    "hours": 4.0,
                    "description": "Feature work",
                }
            ])
        })

        result = json.loads(result_str)
        assert result["success"] is True
        assert result["entries_written"] == 1
        assert "next_action" in result

    @pytest.mark.asyncio
    async def test_log_hours_invalid_json_returns_error(self, mock_config):
        """log_hours returns error for invalid JSON input."""
        from skills.time_tracking.tools import log_hours

        result_str = await log_hours.ainvoke({"entries_json": "not valid json"})
        result = json.loads(result_str)
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_log_hours_multiple_entries(self, mock_config):
        """log_hours writes multiple entries in a single call."""
        from skills.time_tracking.tools import log_hours

        result_str = await log_hours.ainvoke({
            "entries_json": json.dumps([
                {"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0},
                {"date": "2026-02-03", "project": "B", "project_id": "B-001", "hours": 3.0},
            ])
        })

        result = json.loads(result_str)
        assert result["success"] is True
        assert result["entries_written"] == 2


class TestGetLoggedHours:
    @pytest.mark.asyncio
    async def test_get_logged_hours_returns_entries(self, mock_config):
        """get_logged_hours returns previously logged entries."""
        from skills.time_tracking.tools import log_hours, get_logged_hours

        await log_hours.ainvoke({
            "entries_json": json.dumps([
                {"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0}
            ])
        })

        result_str = await get_logged_hours.ainvoke({
            "start_date": "2026-02-03",
            "end_date": "2026-02-03",
        })

        result = json.loads(result_str)
        assert result["success"] is True
        assert len(result["entries"]) == 1
        assert result["total_hours"] == 4.0
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_get_logged_hours_filters_by_project(self, mock_config):
        """get_logged_hours filters entries by project_id when provided."""
        from skills.time_tracking.tools import log_hours, get_logged_hours

        await log_hours.ainvoke({
            "entries_json": json.dumps([
                {"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0},
                {"date": "2026-02-03", "project": "B", "project_id": "B-001", "hours": 3.0},
            ])
        })

        result_str = await get_logged_hours.ainvoke({
            "start_date": "2026-02-03",
            "end_date": "2026-02-03",
            "project_id": "A-001",
        })

        result = json.loads(result_str)
        assert result["success"] is True
        assert len(result["entries"]) == 1
        assert result["total_hours"] == 4.0

    @pytest.mark.asyncio
    async def test_get_logged_hours_empty_range(self, mock_config):
        """get_logged_hours returns empty list for range with no entries."""
        from skills.time_tracking.tools import get_logged_hours

        result_str = await get_logged_hours.ainvoke({
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
        })

        result = json.loads(result_str)
        assert result["success"] is True
        assert result["entries"] == []
        assert result["total_hours"] == 0


class TestListProjects:
    @pytest.mark.asyncio
    async def test_list_projects_returns_config(self, mock_config):
        """list_projects returns all configured projects."""
        from skills.time_tracking.tools import list_projects

        result_str = await list_projects.ainvoke({})
        result = json.loads(result_str)
        assert result["success"] is True
        assert len(result["projects"]) == 2
        assert result["projects"][0]["id"] == "PRJA-001"
        assert result["count"] == 2
        assert "next_action" in result


class TestConfigureProject:
    @pytest.mark.asyncio
    async def test_configure_project_adds_new(self, mock_config):
        """configure_project adds a new project to config."""
        from skills.time_tracking.tools import configure_project, list_projects

        result_str = await configure_project.ainvoke({
            "project_id": "NEW-001",
            "name": "New Project",
            "replicon_project": "New Replicon",
            "client_adapter": "new_client",
        })

        result = json.loads(result_str)
        assert result["success"] is True
        assert result["action"] == "added"
        assert result["project"]["id"] == "NEW-001"

        # Verify it persisted by listing projects
        list_result = json.loads(await list_projects.ainvoke({}))
        assert list_result["count"] == 3

    @pytest.mark.asyncio
    async def test_configure_project_updates_existing(self, mock_config):
        """configure_project updates an existing project."""
        from skills.time_tracking.tools import configure_project

        result_str = await configure_project.ainvoke({
            "project_id": "PRJA-001",
            "name": "Updated Name",
        })

        result = json.loads(result_str)
        assert result["success"] is True
        assert result["action"] == "updated"
        assert result["project"]["name"] == "Updated Name"


class TestPlaceholderStubs:
    @pytest.mark.asyncio
    async def test_suggest_hours_returns_not_configured(self, mock_config):
        """suggest_hours_from_calendar returns not-configured message."""
        from skills.time_tracking.tools import suggest_hours_from_calendar

        result_str = await suggest_hours_from_calendar.ainvoke({"target_date": "2026-02-03"})
        result = json.loads(result_str)
        assert result["success"] is False
        assert "not yet" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_push_to_replicon_returns_not_implemented(self, mock_config):
        """push_to_replicon returns not-implemented message."""
        from skills.time_tracking.tools import push_to_replicon

        result_str = await push_to_replicon.ainvoke({
            "start_date": "2026-02-03",
            "end_date": "2026-02-07",
        })
        result = json.loads(result_str)
        assert result["success"] is False
        assert "not yet" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fill_client_timesheet_missing_adapter(self, mock_config):
        """fill_client_timesheet returns error when adapter module doesn't exist."""
        from skills.time_tracking.tools import fill_client_timesheet

        result_str = await fill_client_timesheet.ainvoke({
            "project_id": "PRJA-001",
            "start_date": "2026-02-03",
            "end_date": "2026-02-07",
        })
        result = json.loads(result_str)
        assert result["success"] is False
        assert "failed to load adapter" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fill_client_timesheet_no_adapter_configured(self, mock_config):
        """fill_client_timesheet returns error when project has no client_adapter."""
        from skills.time_tracking.tools import fill_client_timesheet

        result_str = await fill_client_timesheet.ainvoke({
            "project_id": "INT-001",
            "start_date": "2026-02-03",
            "end_date": "2026-02-07",
        })
        result = json.loads(result_str)
        assert result["success"] is False
        assert "no client adapter" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fill_client_timesheet_unknown_project(self, mock_config):
        """fill_client_timesheet returns error when project not found."""
        from skills.time_tracking.tools import fill_client_timesheet

        result_str = await fill_client_timesheet.ainvoke({
            "project_id": "NONEXISTENT-999",
            "start_date": "2026-02-03",
            "end_date": "2026-02-07",
        })
        result = json.loads(result_str)
        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestGetTools:
    def test_get_tools_returns_all_tools(self):
        """get_tools() returns all 7 tools."""
        from skills.time_tracking.tools import get_tools

        tools = get_tools()
        assert len(tools) == 7

        tool_names = {t.name for t in tools}
        assert tool_names == {
            "log_hours",
            "get_logged_hours",
            "list_projects",
            "configure_project",
            "suggest_hours_from_calendar",
            "push_to_replicon",
            "fill_client_timesheet",
        }
