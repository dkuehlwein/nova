"""Time tracking skill tools for the Nova agent."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import yaml
from langchain_core.tools import tool

from utils.logging import get_logger

logger = get_logger(__name__)

_SKILL_DIR = Path(__file__).parent


def _load_skill_config() -> dict:
    """Load skill configuration from config.yaml, falling back to config.yaml.example."""
    config_path = _SKILL_DIR / "config.yaml"
    if not config_path.exists():
        config_path = _SKILL_DIR / "config.yaml.example"

    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}

    return {}


def _save_skill_config(config: dict) -> None:
    """Save skill configuration to config.yaml."""
    config_path = _SKILL_DIR / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def _import_skill_module(module_name: str) -> ModuleType:
    """Import a module from the skill directory. Supports dot-separated paths (e.g. 'adapters.client_a')."""
    parts = module_name.split(".")
    module_path = _SKILL_DIR / Path(*parts).with_suffix(".py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_config_dir(config: dict, key: str, default: str) -> str:
    """Resolve a directory path from config, expanding ~ to home."""
    return str(Path(config.get(key, default)).expanduser())


def _get_timesheet_dir() -> str:
    """Resolve the timesheet directory from config, expanding ~ to home."""
    return _resolve_config_dir(_load_skill_config(), "timesheet_dir", "~/timesheets")


@tool
async def log_hours(entries_json: str) -> str:
    """
    Log time entries to the master Excel timesheet.

    Args:
        entries_json: JSON array of entries. Each entry must have:
            - date (str): "YYYY-MM-DD" format
            - project (str): Human-readable project name
            - project_id (str): Project identifier from config
            - hours (float): Number of hours
            Optional:
            - start (str): "HH:MM" start time
            - end (str): "HH:MM" end time
            - description (str): What was done

    Returns:
        JSON with success status, file written, and entry count.
    """
    try:
        entries = json.loads(entries_json)
    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid JSON: {e}",
            "next_action": "Report the error to the user and ask them to check the config.",
        })

    try:
        excel_manager = _import_skill_module("excel_manager")
        result = excel_manager.log_entries(entries, timesheet_dir=_get_timesheet_dir())
    except Exception as e:
        logger.error(f"Failed to log hours: {e}", extra={"data": {"error": str(e)}})
        return json.dumps({
            "success": False,
            "error": str(e),
            "next_action": "Report the error to the user and ask them to check the config.",
        })

    return json.dumps({
        **result,
        "next_action": "Confirm to the user what was logged. If this is a daily log, ask if they want to push to any external systems.",
    })


@tool
async def get_logged_hours(
    start_date: str,
    end_date: str,
    project_id: str = "",
) -> str:
    """
    Read logged hours from the master Excel for a date range.

    Args:
        start_date: Start date in "YYYY-MM-DD" format
        end_date: End date in "YYYY-MM-DD" format
        project_id: Optional project ID to filter by

    Returns:
        JSON with entries list and total hours.
    """
    try:
        excel_manager = _import_skill_module("excel_manager")
        entries = excel_manager.read_entries(
            start_date=start_date,
            end_date=end_date,
            timesheet_dir=_get_timesheet_dir(),
            project_id=project_id or None,
        )
    except Exception as e:
        logger.error(f"Failed to read hours: {e}", extra={"data": {"error": str(e)}})
        return json.dumps({
            "success": False,
            "error": str(e),
            "next_action": "Report the error to the user.",
        })

    total_hours = sum(e.get("hours", 0) for e in entries)

    return json.dumps({
        "success": True,
        "entries": entries,
        "total_hours": total_hours,
        "count": len(entries),
        "next_action": "Present the entries to the user in a readable format.",
    })


@tool
async def list_projects() -> str:
    """
    List all configured projects with their IDs and mappings.

    Returns:
        JSON with projects list showing ID, name, Replicon mapping, and client adapter.
    """
    config = _load_skill_config()
    projects = config.get("projects", [])

    return json.dumps({
        "success": True,
        "projects": projects,
        "count": len(projects),
        "next_action": "Present the project list to the user. If they need to add a project, use configure_project.",
    })


@tool
async def configure_project(
    project_id: str,
    name: str,
    replicon_project: str = "",
    client_adapter: str = "",
) -> str:
    """
    Add or update a project in the skill configuration.

    Args:
        project_id: Unique project identifier (e.g., "PRJA-001")
        name: Human-readable project name
        replicon_project: Name as it appears in Replicon UI (optional)
        client_adapter: Name of the client adapter module (optional, e.g., "client_a")

    Returns:
        JSON with success status.
    """
    config = _load_skill_config()
    projects = config.get("projects", [])

    new_project = {
        "id": project_id,
        "name": name,
        "replicon_project": replicon_project or None,
        "client_adapter": client_adapter or None,
    }

    # Update existing or add new
    action = "added"
    for i, p in enumerate(projects):
        if p.get("id") == project_id:
            projects[i] = new_project
            action = "updated"
            break
    else:
        projects.append(new_project)

    config["projects"] = projects
    _save_skill_config(config)

    return json.dumps({
        "success": True,
        "project": new_project,
        "action": action,
        "next_action": "Confirm the project was configured. The agent should remember this project's name/ID association in memory for future reference.",
    })


@tool
async def suggest_hours_from_calendar(target_date: str = "") -> str:
    """
    Suggest time allocation based on calendar events for a given date.

    Uses the configured MCP server (MS Graph or Google Calendar) to read
    calendar events and propose a time breakdown.

    Args:
        target_date: Date to suggest hours for ("YYYY-MM-DD"). Defaults to today.

    Returns:
        JSON with suggested entries based on calendar events.
    """
    # TODO: Implement calendar integration via MCP server
    return json.dumps({
        "success": False,
        "error": "Calendar integration not yet configured. Please log hours manually using log_hours.",
        "next_action": "Ask the user to provide their hours manually for today. Use log_hours to record them.",
    })


@tool
async def push_to_replicon(start_date: str, end_date: str) -> str:
    """
    Push logged hours to Replicon via browser automation.

    Reads entries from the master Excel for the given date range and
    fills them into the Replicon timesheet web UI.

    Args:
        start_date: Start of date range ("YYYY-MM-DD")
        end_date: End of date range ("YYYY-MM-DD")

    Returns:
        JSON with push status.
    """
    # TODO: Implement Replicon browser automation
    return json.dumps({
        "success": False,
        "error": "Replicon integration not yet implemented.",
        "next_action": "Inform the user that Replicon push is not yet available.",
    })


@tool
async def fill_client_timesheet(project_id: str, start_date: str, end_date: str) -> str:
    """
    Fill a client's Excel template with logged hours.

    Reads entries from the master Excel for the given project and date range,
    then fills them into the client's specific template format.

    Args:
        project_id: Project ID to fill hours for
        start_date: Start of date range ("YYYY-MM-DD")
        end_date: End of date range ("YYYY-MM-DD")

    Returns:
        JSON with fill status and output file path.
    """
    config = _load_skill_config()
    timesheet_dir = _resolve_config_dir(config, "timesheet_dir", "~/timesheets")
    templates_dir = _resolve_config_dir(config, "templates_dir", "~/timesheets/templates")
    output_dir = _resolve_config_dir(config, "output_dir", "~/timesheets/output")

    # Find the project config
    projects = config.get("projects", [])
    project_config = next((p for p in projects if p.get("id") == project_id), None)
    if not project_config:
        return json.dumps({
            "success": False,
            "error": f"Project '{project_id}' not found in config.",
            "next_action": "Use list_projects to show available projects.",
        })

    adapter_name = project_config.get("client_adapter")
    if not adapter_name:
        return json.dumps({
            "success": False,
            "error": f"No client adapter configured for project '{project_id}'.",
            "next_action": "This project doesn't have a client template. No action needed.",
        })

    # Read entries from master Excel
    try:
        excel_manager = _import_skill_module("excel_manager")
        entries = excel_manager.read_entries(start_date, end_date, timesheet_dir=timesheet_dir)
    except Exception as e:
        logger.error(f"Failed to read entries: {e}", extra={"data": {"error": str(e)}})
        return json.dumps({
            "success": False,
            "error": f"Failed to read entries: {e}",
            "next_action": "Report the error to the user.",
        })

    # Load and run adapter
    try:
        adapter_module = _import_skill_module(f"adapters.{adapter_name}")
        adapter = adapter_module.get_adapter(project_id)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to load adapter '{adapter_name}': {e}",
            "next_action": "The client adapter module may not exist yet. It needs to be created.",
        })

    filtered = adapter.filter_entries(entries, start_date, end_date)
    if not filtered:
        return json.dumps({
            "success": False,
            "error": f"No entries for project '{project_id}' in date range.",
            "next_action": "No hours logged for this project in the given period.",
        })

    template_path = Path(templates_dir) / f"{adapter_name}_template.xlsx"
    month_str = filtered[0]["date"][:7]
    output_path = Path(output_dir) / f"{adapter_name}_{month_str}.xlsx"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        result = adapter.fill_template(filtered, template_path, output_path)
    except Exception as e:
        logger.error(f"Failed to fill template: {e}", extra={"data": {"error": str(e)}})
        return json.dumps({
            "success": False,
            "error": f"Failed to fill template: {e}",
            "next_action": "Report the error to the user.",
        })

    return json.dumps({
        **result,
        "next_action": "Inform the user that the client timesheet was filled.",
    })


def get_tools():
    """Return all tools provided by this skill."""
    return [
        log_hours,
        get_logged_hours,
        list_projects,
        configure_project,
        suggest_hours_from_calendar,
        push_to_replicon,
        fill_client_timesheet,
    ]
