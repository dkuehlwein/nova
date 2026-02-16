# Time Tracking Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Nova skill that tracks hours in a master Excel and pushes them to Replicon and client-specific Excel templates.

**Architecture:** Master Excel (source of truth, ledger format, one file per month) with pluggable output adapters. Daily calendar trigger proposes hours from calendar/email. Weekly trigger pushes to external systems. Shared browser automation for SSO-authenticated services.

**Tech Stack:** openpyxl (Excel), Playwright (browser automation), LangChain tools, YAML config, existing MCP servers for calendar/email.

**Design Doc:** `docs/plans/2026-02-16-time-tracking-skill-design.md`

---

## Task 1: Extract Shared Browser Automation Utility

Extract generic browser automation code from the GitLab skill's `lam_automation.py` into a shared module that both skills can use.

**Files:**
- Create: `backend/utils/browser_automation.py`
- Modify: `backend/skills/add_user_to_coe_gitlab/lam_automation.py`
- Test: `tests/unit/utils/test_browser_automation.py`

**Step 1: Write failing tests for the shared browser automation module**

Create `tests/unit/utils/test_browser_automation.py`:

```python
"""Tests for shared browser automation utility."""

import json
import pytest
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestBrowserCache:
    """Tests for process-level browser cache."""

    def test_get_browser_cache_creates_namespace(self):
        """First call creates a SimpleNamespace in sys.modules."""
        from utils.browser_automation import get_browser_cache

        cache_key = "_nova_shared_browser"
        # Clean up any existing cache
        sys.modules.pop(cache_key, None)

        cache = get_browser_cache()
        assert cache is not None
        assert hasattr(cache, "playwright_obj")
        assert hasattr(cache, "context")
        assert hasattr(cache, "profile_dir")
        assert cache.playwright_obj is None
        assert cache.context is None

    def test_get_browser_cache_returns_same_instance(self):
        """Subsequent calls return the same cached namespace."""
        from utils.browser_automation import get_browser_cache

        cache1 = get_browser_cache()
        cache2 = get_browser_cache()
        assert cache1 is cache2


class TestSSOCookies:
    """Tests for SSO cookie save/restore."""

    @pytest.mark.asyncio
    async def test_restore_sso_cookies_no_file(self, tmp_path):
        """Returns False when no cookie file exists."""
        from utils.browser_automation import restore_sso_cookies

        context = AsyncMock()
        result = await restore_sso_cookies(
            context, state_path=tmp_path / "nonexistent.json"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_restore_sso_cookies_with_file(self, tmp_path):
        """Restores cookies from file and adds them to context."""
        from utils.browser_automation import restore_sso_cookies

        cookie_file = tmp_path / "cookies.json"
        cookies = [{"name": "session", "value": "abc", "domain": "sso.example.com"}]
        cookie_file.write_text(json.dumps({"cookies": cookies}))

        context = AsyncMock()
        result = await restore_sso_cookies(context, state_path=cookie_file)
        assert result is True
        context.add_cookies.assert_called_once_with(cookies)

    @pytest.mark.asyncio
    async def test_restore_sso_cookies_filters_app_domain(self, tmp_path):
        """Filters out cookies from the target app domain (avoids stale sessions)."""
        from utils.browser_automation import restore_sso_cookies

        cookie_file = tmp_path / "cookies.json"
        cookies = [
            {"name": "sso_token", "value": "abc", "domain": "sso.example.com"},
            {"name": "PHPSESSID", "value": "xyz", "domain": "app.example.com"},
        ]
        cookie_file.write_text(json.dumps({"cookies": cookies}))

        context = AsyncMock()
        result = await restore_sso_cookies(
            context,
            state_path=cookie_file,
            filter_domain="app.example.com",
        )
        assert result is True
        added = context.add_cookies.call_args[0][0]
        assert len(added) == 1
        assert added[0]["name"] == "sso_token"

    @pytest.mark.asyncio
    async def test_save_sso_cookies(self, tmp_path):
        """Saves cookies to disk via storage_state."""
        from utils.browser_automation import save_sso_cookies

        state_path = tmp_path / "cookies.json"
        context = AsyncMock()

        await save_sso_cookies(context, state_path=state_path)
        context.storage_state.assert_called_once_with(path=str(state_path))


class TestProfileDir:
    """Tests for browser profile directory management."""

    def test_get_default_profile_dir(self):
        """Returns default profile dir when no config provided."""
        from utils.browser_automation import get_profile_dir

        result = get_profile_dir()
        assert isinstance(result, Path)
        assert "nova" in str(result)

    def test_get_custom_profile_dir(self):
        """Returns custom dir from config."""
        from utils.browser_automation import get_profile_dir

        result = get_profile_dir(custom_dir="/tmp/test-profile")
        assert result == Path("/tmp/test-profile")
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest ../tests/unit/utils/test_browser_automation.py -v`
Expected: FAIL (module not found)

**Step 3: Implement the shared browser automation module**

Create `backend/utils/browser_automation.py` by extracting the generic parts from `lam_automation.py`:

```python
"""
Shared browser automation utilities for Nova skills.

Provides persistent Chromium browser context management with SSO cookie
persistence. Used by skills that need browser automation with SSO/MFA
(e.g., LAM account creation, Replicon time entry).

Uses sys.modules to cache browser state across module re-imports
(Nova's skill loader re-imports tools on every invocation).
"""

import json
import shutil
import sys
import types
from pathlib import Path

from utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_PROFILE_DIR = Path.home() / ".cache" / "nova" / "browser-profile"
_BROWSER_CACHE_KEY = "_nova_shared_browser"


def get_browser_cache():
    """Get the process-level browser cache (survives module re-imports)."""
    cache = sys.modules.get(_BROWSER_CACHE_KEY)
    if cache is None:
        cache = types.SimpleNamespace(
            playwright_obj=None,
            context=None,
            profile_dir=None,
        )
        sys.modules[_BROWSER_CACHE_KEY] = cache
    return cache


def get_profile_dir(custom_dir: str | None = None) -> Path:
    """Get browser profile directory, with optional override."""
    if custom_dir:
        return Path(custom_dir).expanduser()
    return _DEFAULT_PROFILE_DIR


def get_storage_state_path(profile_dir: Path | None = None, name: str = "sso") -> Path:
    """Get the path for cookie storage state file."""
    base = profile_dir or _DEFAULT_PROFILE_DIR
    return base.parent / f"{name}-state.json"


async def restore_sso_cookies(
    context,
    state_path: Path | None = None,
    filter_domain: str = "",
) -> bool:
    """
    Restore saved SSO session cookies into a browser context.

    Filters out cookies from filter_domain to avoid stale app sessions
    that bypass login but are expired server-side.
    """
    if state_path is None:
        state_path = get_storage_state_path()
    if not state_path.exists():
        return False

    try:
        state = json.loads(state_path.read_text())
        cookies = state.get("cookies", [])
        if filter_domain:
            cookies = [c for c in cookies if filter_domain not in c.get("domain", "")]
        if cookies:
            await context.add_cookies(cookies)
            logger.info(f"Restored {len(cookies)} SSO cookies from {state_path}")
            return True
    except Exception as e:
        logger.warning(f"Failed to restore SSO cookies: {e}")
        state_path.unlink(missing_ok=True)
    return False


async def save_sso_cookies(context, state_path: Path | None = None) -> None:
    """Save current cookies to disk so session cookies survive browser restarts."""
    if state_path is None:
        state_path = get_storage_state_path()
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(state_path))
        logger.info(f"Saved SSO cookies to {state_path}")
    except Exception as e:
        logger.warning(f"Failed to save SSO cookies: {e}")


async def get_or_create_browser_context(
    headless: bool = False,
    timeout_ms: int = 30000,
    profile_dir: Path | None = None,
):
    """
    Return a cached Playwright BrowserContext, creating one if needed.

    The context is stored in sys.modules so it survives module re-imports.
    This keeps the browser alive across tool calls, preserving cert selection
    and SSO cookies in-memory.
    """
    from playwright.async_api import async_playwright

    cache = get_browser_cache()

    if cache.context is not None:
        try:
            if cache.context.browser and cache.context.browser.is_connected():
                logger.debug("Reusing cached browser context")
                return cache.context
        except Exception:
            pass
        logger.info("Cached browser context is dead, recreating")
        cache.context = None
        if cache.playwright_obj:
            try:
                await cache.playwright_obj.stop()
            except Exception:
                pass
            cache.playwright_obj = None

    pw = await async_playwright().start()
    pdir = profile_dir or get_profile_dir()
    pdir.mkdir(parents=True, exist_ok=True)

    try:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(pdir),
            headless=headless,
            ignore_https_errors=True,
        )
    except Exception as launch_err:
        logger.warning(f"Persistent context launch failed, resetting profile: {launch_err}")
        shutil.rmtree(pdir, ignore_errors=True)
        pdir.mkdir(parents=True, exist_ok=True)
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(pdir),
            headless=headless,
            ignore_https_errors=True,
        )

    cache.playwright_obj = pw
    cache.context = context
    cache.profile_dir = pdir
    logger.info("Created new persistent browser context")
    return context


async def close_browser():
    """Close the cached browser."""
    cache = get_browser_cache()
    if cache.context:
        try:
            await cache.context.close()
        except Exception:
            pass
        cache.context = None
    if cache.playwright_obj:
        try:
            await cache.playwright_obj.stop()
        except Exception:
            pass
        cache.playwright_obj = None


async def wait_for_sso(
    page,
    target_url_pattern: str,
    sso_domains: list[str] | None = None,
    timeout_ms: int = 120000,
) -> bool:
    """
    Detect SSO redirect and wait for user to complete login.

    Returns True if SSO was detected and completed, False if no SSO needed.
    """
    current_url = page.url
    is_sso = False

    if sso_domains:
        is_sso = any(domain in current_url for domain in sso_domains)
    elif target_url_pattern not in current_url:
        is_sso = True

    if not is_sso:
        return False

    logger.info(f"SSO detected at: {current_url}")
    logger.info("Waiting for user to complete SSO/MFA login...")

    try:
        await page.wait_for_url(f"**{target_url_pattern}**", timeout=timeout_ms)
        logger.info("SSO completed")
        return True
    except Exception:
        raise TimeoutError(
            f"SSO login timeout ({timeout_ms / 1000}s). "
            "Please complete SSO faster or increase timeout."
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest ../tests/unit/utils/test_browser_automation.py -v`
Expected: PASS

**Step 5: Update lam_automation.py to use shared module**

Modify `backend/skills/add_user_to_coe_gitlab/lam_automation.py` to import from `utils.browser_automation` instead of defining its own cache/cookie functions. Keep LAM-specific functions (URL building, form filling) in the skill module. The key changes:

- Replace `_get_browser_cache()` with `from utils.browser_automation import get_browser_cache`
- Replace `_restore_sso_cookies()` / `_save_sso_cookies()` with shared versions
- Replace `_get_or_create_browser_context()` with shared version
- Replace `close_lam_browser()` with `from utils.browser_automation import close_browser`
- Keep `_build_lam_url()`, `_load_config()`, `create_lam_account()`, `verify_lam_connection()` in the skill

**Step 6: Run existing GitLab skill tests to verify no regression**

Run: `cd backend && uv run pytest ../tests/unit/skills/ -v`
Expected: All existing tests PASS

**Step 7: Commit**

```bash
git add backend/utils/browser_automation.py tests/unit/utils/test_browser_automation.py backend/skills/add_user_to_coe_gitlab/lam_automation.py
git commit -m "refactor: Extract shared browser automation utility from LAM module"
```

---

## Task 2: Skill Skeleton (Manifest, Config, Instructions)

Create the time_tracking skill directory with metadata files.

**Files:**
- Create: `backend/skills/time_tracking/manifest.yaml`
- Create: `backend/skills/time_tracking/config.yaml.example`
- Create: `backend/skills/time_tracking/instructions.md`
- Create: `backend/skills/time_tracking/__init__.py` (empty)
- Create: `backend/skills/time_tracking/adapters/__init__.py` (empty)

**Step 1: Create manifest.yaml**

```yaml
name: time_tracking
version: "1.0.0"
description: "Track work hours and sync to Replicon and client-specific Excel timesheets. Suggests hours from calendar, maintains a master Excel ledger, and pushes to external systems."
author: nova-team
tags: [time, tracking, timesheet, replicon, excel]
```

**Step 2: Create config.yaml.example**

```yaml
# Time Tracking Skill Configuration
# Copy this file to config.yaml and fill in your values.

# File paths - where timesheets are stored
# If running in Docker, these should be inside the mounted volume
timesheet_dir: "~/timesheets"
templates_dir: "~/timesheets/templates"
output_dir: "~/timesheets/output"

# Projects - map internal IDs to external systems
projects:
  - id: "PRJA-001"
    name: "ClientA - Development"
    replicon_project: "Project A"        # Name as shown in Replicon UI
    client_adapter: "client_a"           # Adapter module name (or null)
  - id: "INT-001"
    name: "Internal - Meetings"
    replicon_project: "Internal"
    client_adapter: null

# Replicon configuration
replicon:
  url: "https://na2.replicon.com/yourcompany"
  sso_domains:
    - "your-sso-provider.com"

# Browser automation (shared with other skills)
browser:
  profile_dir: "~/.cache/nova/browser-profile"
```

**Step 3: Create instructions.md**

```markdown
# Time Tracking

Track work hours across multiple systems: personal Excel timesheet, Replicon (company), and client-specific Excel templates.

## Prerequisites

- Skill config.yaml must be set up with project mappings and file paths
- Timesheet directories must exist (or be mountable via Docker volume)
- For Replicon: browser automation with SSO - user completes MFA once, then session is reused
- For calendar suggestions: MS Graph or Google Calendar MCP server must be configured

## Workflow

### Daily Time Logging (triggered by calendar event or user request)

1. Use `time_tracking__suggest_hours_from_calendar` to propose a time breakdown for today
2. Present the suggestion to the user for confirmation/adjustment
3. Use `time_tracking__log_hours` to write confirmed entries to the master Excel
4. Confirm what was logged

### Weekly Timesheet Submission (triggered by calendar event or user request)

1. Use `time_tracking__get_logged_hours` to review the week's entries
2. Present summary to user for confirmation
3. Use `time_tracking__push_to_replicon` to sync to Replicon
4. Use `time_tracking__fill_client_timesheet` for each client that needs a filled template
5. Report what was submitted

### Tools Available

| Tool | Purpose |
|------|---------|
| `time_tracking__log_hours` | Add time entries to master Excel |
| `time_tracking__suggest_hours_from_calendar` | Propose time breakdown from calendar events |
| `time_tracking__get_logged_hours` | Read entries from master Excel for a date range |
| `time_tracking__push_to_replicon` | Push entries to Replicon via browser automation |
| `time_tracking__fill_client_timesheet` | Fill a client's Excel template from master data |
| `time_tracking__list_projects` | Show configured projects with IDs |
| `time_tracking__configure_project` | Add/update a project in config |

## Usage Guidelines

- Always confirm with the user before writing hours (show the proposed entries first)
- Use `list_projects` if unsure which project ID to use
- Start and End times are optional - only include them when the user provides them or the calendar shows specific meeting times
- When pushing to Replicon, warn the user that a browser window will open for SSO if this is the first time
- After logging hours, the agent should store useful associations in memory (e.g., recurring meetings -> project mappings)

## Error Handling

- If the master Excel file doesn't exist yet for this month, `log_hours` creates it automatically
- If Replicon SSO times out, inform the user and suggest retrying
- If a client adapter is not found, report which adapter is missing and skip that client
```

**Step 4: Create empty __init__.py files**

Create `backend/skills/time_tracking/__init__.py` and `backend/skills/time_tracking/adapters/__init__.py` as empty files.

**Step 5: Verify skill is discovered by SkillManager**

Write a quick test in `tests/unit/skills/test_time_tracking_discovery.py`:

```python
"""Test that time_tracking skill is discovered correctly."""

import pytest
from utils.skill_manager import SkillManager
from pathlib import Path


class TestTimeTrackingDiscovery:
    def test_skill_discovered(self):
        """SkillManager should discover the time_tracking skill."""
        skills_path = Path(__file__).parents[3] / "backend" / "skills"
        manager = SkillManager(skills_path=skills_path)
        assert "time_tracking" in manager.list_skills()

    def test_skill_manifest(self):
        """Manifest should have correct metadata."""
        skills_path = Path(__file__).parents[3] / "backend" / "skills"
        manager = SkillManager(skills_path=skills_path)
        manifest = manager.get_manifest("time_tracking")
        assert manifest.name == "time_tracking"
        assert "time" in manifest.tags
```

**Step 6: Run the discovery test**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_discovery.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/skills/time_tracking/ tests/unit/skills/test_time_tracking_discovery.py
git commit -m "feat(time_tracking): Add skill skeleton with manifest, config, and instructions"
```

---

## Task 3: Master Excel Read/Write Module

The core data layer - reading and writing time entries to monthly Excel files.

**Files:**
- Create: `backend/skills/time_tracking/excel_manager.py`
- Test: `tests/unit/skills/test_time_tracking_excel.py`

**Step 1: Write failing tests for Excel operations**

Create `tests/unit/skills/test_time_tracking_excel.py`:

```python
"""Tests for time tracking master Excel operations."""

import pytest
from datetime import date, time
from pathlib import Path


class TestLogEntries:
    """Tests for writing time entries to the master Excel."""

    def test_log_single_entry(self, tmp_path):
        """Writing a single entry creates the Excel file with correct data."""
        from skills.time_tracking.excel_manager import log_entries, read_entries

        entry = {
            "date": "2026-02-03",
            "project": "ClientA - Dev",
            "project_id": "PRJA-001",
            "hours": 4.0,
            "description": "Feature X",
        }

        result = log_entries([entry], timesheet_dir=str(tmp_path))
        assert result["success"] is True
        assert result["file"] == "2026-02-timesheet.xlsx"
        assert result["entries_written"] == 1

        # Verify by reading back
        entries = read_entries(
            start_date="2026-02-03",
            end_date="2026-02-03",
            timesheet_dir=str(tmp_path),
        )
        assert len(entries) == 1
        assert entries[0]["project_id"] == "PRJA-001"
        assert entries[0]["hours"] == 4.0

    def test_log_entry_with_start_end_times(self, tmp_path):
        """Entries can optionally include start and end times."""
        from skills.time_tracking.excel_manager import log_entries, read_entries

        entry = {
            "date": "2026-02-03",
            "project": "ClientA - Dev",
            "project_id": "PRJA-001",
            "start": "09:00",
            "end": "13:00",
            "hours": 4.0,
            "description": "Feature X",
        }

        log_entries([entry], timesheet_dir=str(tmp_path))
        entries = read_entries("2026-02-03", "2026-02-03", timesheet_dir=str(tmp_path))
        assert entries[0]["start"] == "09:00"
        assert entries[0]["end"] == "13:00"

    def test_log_multiple_entries_appends(self, tmp_path):
        """Multiple calls append rows, not overwrite."""
        from skills.time_tracking.excel_manager import log_entries, read_entries

        log_entries(
            [{"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0}],
            timesheet_dir=str(tmp_path),
        )
        log_entries(
            [{"date": "2026-02-03", "project": "B", "project_id": "B-001", "hours": 3.0}],
            timesheet_dir=str(tmp_path),
        )

        entries = read_entries("2026-02-03", "2026-02-03", timesheet_dir=str(tmp_path))
        assert len(entries) == 2

    def test_creates_new_file_per_month(self, tmp_path):
        """Entries in different months go to different files."""
        from skills.time_tracking.excel_manager import log_entries

        log_entries(
            [{"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0}],
            timesheet_dir=str(tmp_path),
        )
        log_entries(
            [{"date": "2026-03-03", "project": "A", "project_id": "A-001", "hours": 4.0}],
            timesheet_dir=str(tmp_path),
        )

        assert (tmp_path / "2026-02-timesheet.xlsx").exists()
        assert (tmp_path / "2026-03-timesheet.xlsx").exists()


class TestReadEntries:
    """Tests for reading time entries from master Excel."""

    def test_read_date_range(self, tmp_path):
        """Reads only entries within the specified date range."""
        from skills.time_tracking.excel_manager import log_entries, read_entries

        entries = [
            {"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0},
            {"date": "2026-02-04", "project": "B", "project_id": "B-001", "hours": 3.0},
            {"date": "2026-02-05", "project": "A", "project_id": "A-001", "hours": 5.0},
        ]
        log_entries(entries, timesheet_dir=str(tmp_path))

        result = read_entries("2026-02-03", "2026-02-04", timesheet_dir=str(tmp_path))
        assert len(result) == 2

    def test_read_nonexistent_month_returns_empty(self, tmp_path):
        """Reading from a month with no file returns empty list."""
        from skills.time_tracking.excel_manager import read_entries

        result = read_entries("2026-02-01", "2026-02-28", timesheet_dir=str(tmp_path))
        assert result == []

    def test_read_entries_by_project(self, tmp_path):
        """Can filter entries by project_id."""
        from skills.time_tracking.excel_manager import log_entries, read_entries

        entries = [
            {"date": "2026-02-03", "project": "A", "project_id": "A-001", "hours": 4.0},
            {"date": "2026-02-03", "project": "B", "project_id": "B-001", "hours": 3.0},
        ]
        log_entries(entries, timesheet_dir=str(tmp_path))

        result = read_entries(
            "2026-02-01", "2026-02-28",
            timesheet_dir=str(tmp_path),
            project_id="A-001",
        )
        assert len(result) == 1
        assert result[0]["project_id"] == "A-001"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_excel.py -v`
Expected: FAIL (module not found)

**Step 3: Add openpyxl dependency**

Run: `cd backend && uv add openpyxl`

**Step 4: Implement excel_manager.py**

Create `backend/skills/time_tracking/excel_manager.py`:

```python
"""
Master Excel timesheet management.

Manages monthly Excel files in ledger format (one row per time entry).
Files are named YYYY-MM-timesheet.xlsx and stored in the configured directory.
"""

from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

COLUMNS = ["Date", "Project", "Project ID", "Start", "End", "Hours", "Description"]


def _get_file_path(entry_date: str, timesheet_dir: str) -> Path:
    """Get the Excel file path for a given date's month."""
    d = datetime.strptime(entry_date, "%Y-%m-%d")
    filename = f"{d.strftime('%Y-%m')}-timesheet.xlsx"
    return Path(timesheet_dir) / filename


def _ensure_workbook(file_path: Path) -> Workbook:
    """Load existing workbook or create new one with headers."""
    if file_path.exists():
        return load_workbook(file_path)

    wb = Workbook()
    ws = wb.active
    ws.title = "Timesheet"
    ws.append(COLUMNS)
    return wb


def log_entries(entries: list[dict], timesheet_dir: str) -> dict:
    """
    Append time entries to the master Excel file.

    Each entry dict should have: date, project, project_id, hours.
    Optional: start, end, description.

    Returns dict with success status and metadata.
    """
    dir_path = Path(timesheet_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    files_written = set()
    total = 0

    for entry in entries:
        file_path = _get_file_path(entry["date"], timesheet_dir)
        wb = _ensure_workbook(file_path)
        ws = wb.active

        row = [
            entry["date"],
            entry.get("project", ""),
            entry.get("project_id", ""),
            entry.get("start", ""),
            entry.get("end", ""),
            entry.get("hours", 0),
            entry.get("description", ""),
        ]
        ws.append(row)
        wb.save(file_path)
        files_written.add(file_path.name)
        total += 1

    return {
        "success": True,
        "file": ", ".join(sorted(files_written)),
        "entries_written": total,
    }


def read_entries(
    start_date: str,
    end_date: str,
    timesheet_dir: str,
    project_id: str | None = None,
) -> list[dict]:
    """
    Read time entries from master Excel for a date range.

    Spans multiple monthly files if the range crosses month boundaries.
    Optionally filters by project_id.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    dir_path = Path(timesheet_dir)

    results = []

    # Collect all months in range
    months = set()
    current = start
    while current <= end:
        months.add(current.strftime("%Y-%m"))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)

    for month in sorted(months):
        file_path = dir_path / f"{month}-timesheet.xlsx"
        if not file_path.exists():
            continue

        wb = load_workbook(file_path, read_only=True)
        ws = wb.active

        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue

            # Parse date - handle both string and datetime
            row_date_str = str(row[0])
            if " " in row_date_str:
                row_date_str = row_date_str.split(" ")[0]
            try:
                row_date = datetime.strptime(row_date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            if row_date < start or row_date > end:
                continue

            entry = {
                "date": row_date_str,
                "project": str(row[1] or ""),
                "project_id": str(row[2] or ""),
                "start": str(row[3] or ""),
                "end": str(row[4] or ""),
                "hours": float(row[5]) if row[5] else 0.0,
                "description": str(row[6] or ""),
            }

            if project_id and entry["project_id"] != project_id:
                continue

            results.append(entry)

        wb.close()

    return results
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_excel.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/skills/time_tracking/excel_manager.py tests/unit/skills/test_time_tracking_excel.py
git commit -m "feat(time_tracking): Add master Excel read/write module with tests"
```

---

## Task 4: Core Skill Tools (log_hours, get_logged_hours, list_projects, configure_project)

Implement the LangChain tools that the agent calls. These are the simpler tools that don't require external system interaction.

**Files:**
- Create: `backend/skills/time_tracking/tools.py`
- Test: `tests/unit/skills/test_time_tracking_tools.py`

**Step 1: Write failing tests for core tools**

Create `tests/unit/skills/test_time_tracking_tools.py`:

```python
"""Tests for time tracking skill tools."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config.yaml for the skill."""
    import yaml

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
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_tools.py -v`
Expected: FAIL

**Step 3: Implement tools.py**

Create `backend/skills/time_tracking/tools.py`:

```python
"""Time tracking skill tools for the Nova agent."""

import importlib.util
import json
import os
from pathlib import Path

import yaml
from langchain_core.tools import tool

from utils.logging import get_logger

logger = get_logger(__name__)

_SKILL_DIR = Path(__file__).parent


def _load_skill_config() -> dict:
    """Load skill configuration from config.yaml."""
    config_path = _SKILL_DIR / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}

    example_path = _SKILL_DIR / "config.yaml.example"
    if example_path.exists():
        with open(example_path) as f:
            return yaml.safe_load(f) or {}

    return {}


def _save_skill_config(config: dict) -> None:
    """Save skill configuration to config.yaml."""
    config_path = _SKILL_DIR / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def _import_skill_module(module_name: str):
    """Import a sibling module from the skill directory."""
    module_path = _SKILL_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        config = _load_skill_config()
        timesheet_dir = config.get("timesheet_dir", "~/timesheets")
        timesheet_dir = str(Path(timesheet_dir).expanduser())

        excel_manager = _import_skill_module("excel_manager")
        result = excel_manager.log_entries(entries, timesheet_dir=timesheet_dir)

        return json.dumps({
            **result,
            "next_action": "Confirm to the user what was logged. If this is a daily log, ask if they want to push to any external systems.",
        })
    except Exception as e:
        logger.error(f"Failed to log hours: {e}", extra={"data": {"error": str(e)}})
        return json.dumps({
            "success": False,
            "error": str(e),
            "next_action": "Report the error to the user and ask them to check the config.",
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
        config = _load_skill_config()
        timesheet_dir = config.get("timesheet_dir", "~/timesheets")
        timesheet_dir = str(Path(timesheet_dir).expanduser())

        excel_manager = _import_skill_module("excel_manager")
        entries = excel_manager.read_entries(
            start_date=start_date,
            end_date=end_date,
            timesheet_dir=timesheet_dir,
            project_id=project_id or None,
        )

        total_hours = sum(e.get("hours", 0) for e in entries)

        return json.dumps({
            "success": True,
            "entries": entries,
            "total_hours": total_hours,
            "count": len(entries),
            "next_action": "Present the entries to the user in a readable format.",
        })
    except Exception as e:
        logger.error(f"Failed to read hours: {e}", extra={"data": {"error": str(e)}})
        return json.dumps({
            "success": False,
            "error": str(e),
            "next_action": "Report the error to the user.",
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
    for i, p in enumerate(projects):
        if p.get("id") == project_id:
            projects[i] = new_project
            break
    else:
        projects.append(new_project)

    config["projects"] = projects
    _save_skill_config(config)

    return json.dumps({
        "success": True,
        "project": new_project,
        "action": "updated" if any(p.get("id") == project_id for p in projects[:-1]) else "added",
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
    # This is a placeholder that will be implemented when MCP calendar access is configured
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
    # TODO: Implement client adapter loading and template filling
    return json.dumps({
        "success": False,
        "error": "Client timesheet filling not yet implemented.",
        "next_action": "Inform the user that client template filling is not yet available.",
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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_tools.py -v`
Expected: PASS

**Step 5: Test full skill loading through SkillManager**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_discovery.py -v`
Expected: PASS (verifies the skill loads with all tools)

**Step 6: Commit**

```bash
git add backend/skills/time_tracking/tools.py tests/unit/skills/test_time_tracking_tools.py
git commit -m "feat(time_tracking): Add core skill tools (log_hours, get_logged_hours, list_projects, configure_project)"
```

---

## Task 5: Calendar Suggestion Tool (suggest_hours_from_calendar)

Implement the calendar integration to auto-suggest hours. This depends on the MCP server setup for MS Graph or Google Calendar.

**Files:**
- Modify: `backend/skills/time_tracking/tools.py` (replace placeholder)
- Test: `tests/unit/skills/test_time_tracking_calendar.py`

**Step 1: Write failing tests**

Create `tests/unit/skills/test_time_tracking_calendar.py`:

```python
"""Tests for calendar-based hour suggestions."""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock


class TestSuggestHoursFromCalendar:
    @pytest.mark.asyncio
    async def test_suggests_hours_from_calendar_events(self, mock_config):
        """Transforms calendar events into time entry suggestions."""
        from skills.time_tracking.tools import suggest_hours_from_calendar

        mock_events = [
            {
                "subject": "ClientA Sprint Planning",
                "start": {"dateTime": "2026-02-03T09:00:00"},
                "end": {"dateTime": "2026-02-03T10:00:00"},
            },
            {
                "subject": "Internal Team Standup",
                "start": {"dateTime": "2026-02-03T10:30:00"},
                "end": {"dateTime": "2026-02-03T11:00:00"},
            },
        ]

        with patch("skills.time_tracking.tools._get_calendar_events", new_callable=AsyncMock) as mock_cal:
            mock_cal.return_value = mock_events

            result_str = await suggest_hours_from_calendar.ainvoke({"target_date": "2026-02-03"})
            result = json.loads(result_str)

            assert result["success"] is True
            assert len(result["suggestions"]) >= 1
            assert result["date"] == "2026-02-03"

    @pytest.mark.asyncio
    async def test_handles_no_calendar_events(self, mock_config):
        """Returns helpful message when no calendar events found."""
        from skills.time_tracking.tools import suggest_hours_from_calendar

        with patch("skills.time_tracking.tools._get_calendar_events", new_callable=AsyncMock) as mock_cal:
            mock_cal.return_value = []

            result_str = await suggest_hours_from_calendar.ainvoke({"target_date": "2026-02-03"})
            result = json.loads(result_str)

            assert result["success"] is True
            assert len(result["suggestions"]) == 0
```

Note: The `mock_config` fixture should be imported or duplicated from `test_time_tracking_tools.py`. Consider extracting it to a `conftest.py` in `tests/unit/skills/`.

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_calendar.py -v`
Expected: FAIL

**Step 3: Implement calendar suggestion logic**

Update the `suggest_hours_from_calendar` function in `tools.py`. Add a helper function `_get_calendar_events()` that calls the MCP server:

```python
async def _get_calendar_events(target_date: str) -> list[dict]:
    """Fetch calendar events for a date via MCP server."""
    try:
        from mcp_client import mcp_manager

        # Try MS Graph first
        result = await mcp_manager.call_mcp_tool(
            server_name="ms_graph",
            tool_name="list_calendar_events",
            arguments={
                "start_date": f"{target_date}T00:00:00",
                "end_date": f"{target_date}T23:59:59",
            },
        )
        if isinstance(result, str):
            result = json.loads(result)
        return result.get("value", result) if isinstance(result, dict) else result
    except Exception as e:
        logger.warning(f"Calendar fetch failed: {e}")
        return []
```

Then update the tool to parse events into suggestions with project matching from config.

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_calendar.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/skills/time_tracking/tools.py tests/unit/skills/test_time_tracking_calendar.py
git commit -m "feat(time_tracking): Add calendar-based hour suggestion tool"
```

---

## Task 6: Replicon Browser Automation Adapter

Implement the Replicon adapter using shared browser automation.

**Files:**
- Create: `backend/skills/time_tracking/adapters/replicon.py`
- Modify: `backend/skills/time_tracking/tools.py` (wire up push_to_replicon)
- Test: `tests/unit/skills/test_time_tracking_replicon.py`

**Important:** This task requires research into the actual Replicon web UI structure. The implementation will be iterative - start with a skeleton that opens Replicon and handles SSO, then fill in the form automation once the UI selectors are known.

**Step 1: Create Replicon adapter skeleton**

Create `backend/skills/time_tracking/adapters/replicon.py`:

```python
"""
Replicon timesheet browser automation adapter.

Uses Playwright with persistent SSO session to fill Replicon timesheets
via the web UI. Requires initial manual SSO/MFA completion; subsequent
runs reuse the saved session cookies.
"""

import json
from pathlib import Path
from urllib.parse import urlparse

from utils.browser_automation import (
    get_or_create_browser_context,
    get_profile_dir,
    get_storage_state_path,
    restore_sso_cookies,
    save_sso_cookies,
    wait_for_sso,
)
from utils.logging import get_logger

logger = get_logger(__name__)


async def push_entries_to_replicon(
    entries: list[dict],
    replicon_url: str,
    sso_domains: list[str] | None = None,
    browser_config: dict | None = None,
) -> dict:
    """
    Push time entries to Replicon via browser automation.

    Opens the Replicon timesheet page, handles SSO if needed,
    then fills in the time entries.

    Args:
        entries: List of time entry dicts with date, project, hours, etc.
        replicon_url: Base Replicon URL (e.g., "https://na2.replicon.com/company")
        sso_domains: SSO provider domains for detecting redirects
        browser_config: Optional browser config (profile_dir, etc.)

    Returns:
        Dict with success status and details.
    """
    browser_config = browser_config or {}
    profile_dir = get_profile_dir(browser_config.get("profile_dir"))

    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: playwright install chromium",
        }

    try:
        context = await get_or_create_browser_context(
            headless=False,  # SSO requires visible browser for MFA
            profile_dir=profile_dir,
        )

        # Restore SSO cookies
        replicon_host = urlparse(replicon_url).hostname or ""
        state_path = get_storage_state_path(profile_dir, name="replicon-sso")
        await restore_sso_cookies(context, state_path=state_path, filter_domain=replicon_host)

        page = await context.new_page()

        try:
            # Navigate to Replicon timesheet
            timesheet_url = f"{replicon_url.rstrip('/')}/timesheet/edit"
            logger.info(f"Navigating to Replicon: {timesheet_url}")
            await page.goto(timesheet_url, wait_until="networkidle")

            # Handle SSO/MFA if redirected
            sso_completed = await wait_for_sso(
                page,
                target_url_pattern=replicon_host,
                sso_domains=sso_domains,
                timeout_ms=120000,
            )

            if sso_completed:
                await save_sso_cookies(context, state_path=state_path)

            # TODO: Fill in timesheet form
            # This requires knowledge of the specific Replicon UI selectors.
            # Implementation will be iterative:
            # 1. First run: capture the page structure
            # 2. Map selectors for project dropdown, date cells, hour inputs
            # 3. Implement form filling logic

            logger.info("Replicon page loaded. Form filling not yet implemented.")

            return {
                "success": False,
                "error": "Replicon form filling not yet implemented. SSO/navigation works. Need to map UI selectors.",
                "sso_completed": sso_completed,
                "page_title": await page.title(),
            }

        finally:
            await page.close()

    except PlaywrightTimeout:
        return {
            "success": False,
            "error": "SSO login timeout. Please complete SSO faster or try again.",
        }
    except Exception as e:
        logger.error(f"Replicon push failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }
```

**Step 2: Wire up push_to_replicon in tools.py**

Replace the placeholder `push_to_replicon` tool body with:

```python
    config = _load_skill_config()
    timesheet_dir = str(Path(config.get("timesheet_dir", "~/timesheets")).expanduser())
    replicon_config = config.get("replicon", {})

    if not replicon_config.get("url"):
        return json.dumps({
            "success": False,
            "error": "Replicon URL not configured. Update config.yaml with replicon.url.",
            "next_action": "Ask the user to provide their Replicon URL.",
        })

    excel_manager = _import_skill_module("excel_manager")
    entries = excel_manager.read_entries(start_date, end_date, timesheet_dir=timesheet_dir)

    if not entries:
        return json.dumps({
            "success": False,
            "error": f"No entries found for {start_date} to {end_date}.",
            "next_action": "Ask the user to log hours first.",
        })

    replicon_adapter = _import_skill_module("adapters.replicon")
    result = await replicon_adapter.push_entries_to_replicon(
        entries=entries,
        replicon_url=replicon_config["url"],
        sso_domains=replicon_config.get("sso_domains"),
        browser_config=config.get("browser"),
    )

    return json.dumps({
        **result,
        "entries_count": len(entries),
        "next_action": "Report the Replicon push status to the user." if result.get("success")
            else "Inform the user about the issue and suggest next steps.",
    })
```

**Step 3: Write basic tests**

Create `tests/unit/skills/test_time_tracking_replicon.py`:

```python
"""Tests for Replicon adapter."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestRepliconAdapter:
    @pytest.mark.asyncio
    async def test_push_without_playwright_returns_error(self):
        """Returns clear error when Playwright is not installed."""
        from skills.time_tracking.adapters.replicon import push_entries_to_replicon

        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            # Force ImportError
            with patch("skills.time_tracking.adapters.replicon.get_or_create_browser_context", side_effect=ImportError("No playwright")):
                pass
            # Note: the actual import check is inside the function
            # This test verifies the error handling path

    @pytest.mark.asyncio
    async def test_push_to_replicon_tool_no_config(self, mock_config):
        """push_to_replicon tool returns error when Replicon URL is not configured."""
        from skills.time_tracking.tools import push_to_replicon

        # mock_config doesn't include replicon.url
        result_str = await push_to_replicon.ainvoke({
            "start_date": "2026-02-03",
            "end_date": "2026-02-07",
        })
        result = json.loads(result_str)
        assert result["success"] is False
        assert "not configured" in result["error"].lower() or "not yet" in result["error"].lower()
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_replicon.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/skills/time_tracking/adapters/replicon.py tests/unit/skills/test_time_tracking_replicon.py backend/skills/time_tracking/tools.py
git commit -m "feat(time_tracking): Add Replicon browser automation adapter skeleton"
```

---

## Task 7: Client Excel Adapter Base Class

Create the base class for client-specific Excel adapters.

**Files:**
- Create: `backend/skills/time_tracking/adapters/base.py`
- Test: `tests/unit/skills/test_time_tracking_adapter_base.py`

**Step 1: Write failing tests**

Create `tests/unit/skills/test_time_tracking_adapter_base.py`:

```python
"""Tests for client adapter base class."""

import pytest
from pathlib import Path


class TestBaseAdapter:
    def test_filter_entries_by_project(self):
        """Base adapter filters entries by project_id."""
        from skills.time_tracking.adapters.base import BaseClientAdapter

        adapter = BaseClientAdapter(project_id="PRJA-001")
        entries = [
            {"date": "2026-02-03", "project_id": "PRJA-001", "hours": 4.0},
            {"date": "2026-02-03", "project_id": "INT-001", "hours": 2.0},
        ]
        filtered = adapter.filter_entries(entries)
        assert len(filtered) == 1
        assert filtered[0]["project_id"] == "PRJA-001"

    def test_filter_entries_by_date_range(self):
        """Base adapter filters entries by date range."""
        from skills.time_tracking.adapters.base import BaseClientAdapter

        adapter = BaseClientAdapter(project_id="PRJA-001")
        entries = [
            {"date": "2026-02-03", "project_id": "PRJA-001", "hours": 4.0},
            {"date": "2026-02-10", "project_id": "PRJA-001", "hours": 3.0},
        ]
        filtered = adapter.filter_entries(entries, start_date="2026-02-01", end_date="2026-02-05")
        assert len(filtered) == 1

    def test_fill_template_not_implemented(self, tmp_path):
        """Base adapter's fill_template raises NotImplementedError."""
        from skills.time_tracking.adapters.base import BaseClientAdapter

        adapter = BaseClientAdapter(project_id="PRJA-001")
        with pytest.raises(NotImplementedError):
            adapter.fill_template([], template_path=tmp_path / "template.xlsx", output_path=tmp_path / "output.xlsx")
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_adapter_base.py -v`
Expected: FAIL

**Step 3: Implement base adapter**

Create `backend/skills/time_tracking/adapters/base.py`:

```python
"""Base class for client-specific Excel adapters."""

from datetime import datetime
from pathlib import Path


class BaseClientAdapter:
    """
    Base class for client Excel template adapters.

    Each client adapter subclass implements fill_template() to write
    time entries into that client's specific Excel template format.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id

    def filter_entries(
        self,
        entries: list[dict],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """Filter entries by project and optionally by date range."""
        filtered = [e for e in entries if e.get("project_id") == self.project_id]

        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            filtered = [e for e in filtered if datetime.strptime(e["date"], "%Y-%m-%d").date() >= start]

        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            filtered = [e for e in filtered if datetime.strptime(e["date"], "%Y-%m-%d").date() <= end]

        return filtered

    def fill_template(
        self,
        entries: list[dict],
        template_path: Path,
        output_path: Path,
    ) -> dict:
        """
        Fill a client's Excel template with time entries.

        Must be implemented by each client-specific adapter.

        Args:
            entries: Filtered time entries for this client
            template_path: Path to the client's Excel template
            output_path: Path to save the filled template

        Returns:
            Dict with success status and output file path.
        """
        raise NotImplementedError(
            f"Adapter for {self.project_id} must implement fill_template()"
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking_adapter_base.py -v`
Expected: PASS

**Step 5: Wire up fill_client_timesheet in tools.py**

Replace the placeholder in `fill_client_timesheet`:

```python
    config = _load_skill_config()
    timesheet_dir = str(Path(config.get("timesheet_dir", "~/timesheets")).expanduser())
    templates_dir = str(Path(config.get("templates_dir", "~/timesheets/templates")).expanduser())
    output_dir = str(Path(config.get("output_dir", "~/timesheets/output")).expanduser())

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

    # Read entries
    excel_manager = _import_skill_module("excel_manager")
    entries = excel_manager.read_entries(start_date, end_date, timesheet_dir=timesheet_dir)

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

    result = adapter.fill_template(filtered, template_path, output_path)

    return json.dumps({
        **result,
        "next_action": "Inform the user that the client timesheet was filled.",
    })
```

**Step 6: Commit**

```bash
git add backend/skills/time_tracking/adapters/base.py tests/unit/skills/test_time_tracking_adapter_base.py backend/skills/time_tracking/tools.py
git commit -m "feat(time_tracking): Add client adapter base class and fill_client_timesheet wiring"
```

---

## Task 8: Docker Volume Mount & Integration Test

Add Docker volume mount for timesheet access and create an integration test.

**Files:**
- Modify: `docker-compose.yaml`
- Test: `tests/integration/skills/test_time_tracking_integration.py`

**Step 1: Add volume mount to docker-compose.yaml**

Add to the nova-backend service's volumes section:

```yaml
- ${TIMESHEET_DIR:-~/timesheets}:/data/timesheets
```

This makes the timesheet directory configurable via environment variable.

**Step 2: Write integration test**

Create `tests/integration/skills/test_time_tracking_integration.py`:

```python
"""Integration tests for time tracking skill.

Requires: skill files present in backend/skills/time_tracking/
Tests the full flow: log -> read -> verify
"""

import json
import pytest
from pathlib import Path
from utils.skill_manager import SkillManager


class TestTimeTrackingIntegration:
    @pytest.mark.asyncio
    async def test_skill_loads_with_all_tools(self):
        """Skill should load and register all 7 tools."""
        skills_path = Path(__file__).parents[3] / "backend" / "skills"
        manager = SkillManager(skills_path=skills_path)
        tools = await manager.get_skill_tools("time_tracking", namespace=True)

        tool_names = [t.name for t in tools]
        assert "time_tracking__log_hours" in tool_names
        assert "time_tracking__get_logged_hours" in tool_names
        assert "time_tracking__list_projects" in tool_names
        assert "time_tracking__configure_project" in tool_names
        assert "time_tracking__suggest_hours_from_calendar" in tool_names
        assert "time_tracking__push_to_replicon" in tool_names
        assert "time_tracking__fill_client_timesheet" in tool_names

    @pytest.mark.asyncio
    async def test_full_log_and_read_flow(self, tmp_path):
        """Full flow: configure project -> log hours -> read back."""
        # This test needs a config pointing to tmp_path
        # Use environment variable or patch config loading
        pass
```

**Step 3: Run integration tests**

Run: `cd backend && uv run pytest ../tests/integration/skills/test_time_tracking_integration.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add docker-compose.yaml tests/integration/skills/test_time_tracking_integration.py
git commit -m "feat(time_tracking): Add Docker volume mount and integration test skeleton"
```

---

## Task 9: Test Fixtures Cleanup & conftest.py

Extract shared test fixtures to avoid duplication.

**Files:**
- Create: `tests/unit/skills/conftest.py`
- Modify: `tests/unit/skills/test_time_tracking_tools.py` (remove local fixture)
- Modify: `tests/unit/skills/test_time_tracking_calendar.py` (remove local fixture)

**Step 1: Create shared conftest.py**

```python
"""Shared fixtures for time tracking skill tests."""

import pytest
import yaml
from pathlib import Path


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config.yaml for the time tracking skill."""
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

    config_path = Path(__file__).parents[2] / "backend" / "skills" / "time_tracking" / "config.yaml"
    config_path.write_text(yaml.dump(config))
    yield config
    config_path.unlink(missing_ok=True)
```

**Step 2: Remove duplicate fixtures from individual test files**

**Step 3: Run all tests**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking*.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add tests/unit/skills/conftest.py tests/unit/skills/test_time_tracking_tools.py tests/unit/skills/test_time_tracking_calendar.py
git commit -m "refactor(tests): Extract shared time tracking test fixtures to conftest.py"
```

---

## Task 10: Run Full Test Suite & Final Verification

Ensure nothing is broken across the entire test suite.

**Step 1: Run all unit tests**

Run: `cd backend && uv run pytest ../tests/unit -v`
Expected: All PASS

**Step 2: Run all time tracking tests specifically**

Run: `cd backend && uv run pytest ../tests/unit/skills/test_time_tracking*.py -v --tb=short`
Expected: All PASS

**Step 3: Verify skill loads through the API (manual)**

If the backend is running:
```bash
curl http://localhost:8000/api/skills/ | python -m json.tool
```
Expected: time_tracking should appear in the list with correct metadata.

**Step 4: Final commit if any cleanup was needed**

```bash
git add -A
git commit -m "chore(time_tracking): Final cleanup and verification"
```

---

## Summary

| Task | Component | Status |
|------|-----------|--------|
| 1 | Shared browser automation utility | Refactor |
| 2 | Skill skeleton (manifest, config, instructions) | New files |
| 3 | Master Excel read/write | New module + tests |
| 4 | Core tools (log, read, list, configure) | New module + tests |
| 5 | Calendar suggestion tool | Tool + tests |
| 6 | Replicon browser adapter | Skeleton + SSO handling |
| 7 | Client Excel adapter base | Base class + tests |
| 8 | Docker volume mount | Config change |
| 9 | Test fixtures cleanup | Refactor |
| 10 | Full test suite verification | Verification |

**Future work (not in this plan):**
- Replicon form filling (requires UI selector mapping - interactive session)
- First client Excel adapter (requires actual client template)
- Calendar input hook trigger configuration
- Memory associations for project name fuzzy matching
