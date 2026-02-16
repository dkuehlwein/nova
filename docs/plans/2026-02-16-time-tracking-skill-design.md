# Time Tracking Skill Design

**Date**: 2026-02-16
**Status**: Approved

## Problem

Time tracking across multiple systems is painful:
- 3-5 active projects per week
- Hours must be entered into: personal Excel, Replicon (company), and client-provided Excel templates
- Each system has a different format
- Remembering what you worked on days later is unreliable
- Duplicate manual entry is tedious and error-prone
- Result: procrastination until deadlines

## Solution

A Nova skill that uses a **master Excel as source of truth** with **pluggable output adapters** for each target system.

## Architecture

```
Calendar Trigger (daily/weekly)
        |
        v
  Core Agent activates time_tracking skill
        |
        v
  suggest_hours_from_calendar  -->  Calendar + Email data
        |
        v
  User confirms/adjusts via chat
        |
        v
  log_hours  -->  Master Excel (source of truth)
        |
        v  (on demand or weekly trigger)
  push_to_replicon  -->  Replicon (browser automation + SSO)
  fill_client_timesheet  -->  Client Excel templates (per-client adapter)
```

## Data Model: Master Excel

One file per month: `YYYY-MM-timesheet.xlsx` (e.g., `2026-02-timesheet.xlsx`).

Ledger format (one row per entry):

| Date | Project | Project ID | Start | End | Hours | Description |
|------|---------|-----------|-------|-----|-------|-------------|
| 2026-02-03 | ClientA - Dev | PRJA-001 | 09:00 | 13:00 | 4.0 | Feature X |
| 2026-02-03 | Internal | INT-001 | 14:00 | 16:00 | 2.0 | Sprint planning |

- **Date**: Required. ISO format.
- **Project**: Human-readable name.
- **Project ID**: Canonical identifier for mapping to external systems.
- **Start/End**: Optional. Required by some clients for detailed time-of-day reporting.
- **Hours**: Always present. Primary field for all systems.
- **Description**: Optional. Used for client reporting and memory.

## Daily Workflow

**Trigger**: Recurring calendar event (e.g., "Log Hours" at 17:00) picked up by Nova's calendar input hook, activating the core agent.

1. **Gather context**: Nova reads calendar events and recent emails to identify projects worked on.
2. **Propose breakdown**: Nova presents a suggested time allocation with project mappings.
3. **User confirms/adjusts**: Natural language corrections via chat.
4. **Write to master**: Confirmed entries appended to the current month's Excel file.

## Weekly Workflow

**Trigger**: Recurring calendar event (e.g., "Submit Timesheet" on Friday) picked up by the same calendar input hook.

1. **Read master Excel**: Pull all entries for the current week.
2. **Push to Replicon**: Browser automation fills the Replicon timesheet.
3. **Fill client sheets**: Per-client adapters populate their respective templates.
4. **Report status**: Nova confirms what was pushed and flags any issues.

## Output Adapters

### Personal Master Excel (always active)
- Appends rows to `{timesheet_dir}/YYYY-MM-timesheet.xlsx`
- Creates new file on first entry of each month
- Uses `openpyxl` for Excel read/write

### Replicon Adapter
- **Browser automation** via Playwright (same pattern as LAM automation in the GitLab skill)
- Opens Replicon web UI, handles SSO/MFA with persistent browser session
- Fills timesheet form based on master Excel data
- Reuses SSO cookies across sessions (persistent Chromium profile)
- Uses shared browser automation utility (refactored from `lam_automation.py`)
- Fallback: if API access is later confirmed, add direct API path via `replicon-handler` PyPI package

### Client Excel Adapters
- **Per-client Python modules**: `adapters/client_a.py`, `adapters/client_b.py`, etc.
- Each adapter knows how to read and fill that client's specific template
- Common base for shared logic (reading master Excel, date range filtering)
- Adding a new client = writing a small adapter module
- Client templates stored in `{templates_dir}/`
- Filled output saved to `{output_dir}/`

## Shared Browser Automation Utility (Refactor)

Extract from `backend/skills/add_user_to_coe_gitlab/lam_automation.py` into a shared module.

**New location**: `backend/utils/browser_automation.py` (or `backend/tools/browser_automation.py`)

**Provides**:
- Persistent browser context management (cache across tool calls)
- SSO cookie save/restore
- MFA wait handling with configurable timeout
- Profile directory management

**Consumers**: GitLab skill (LAM automation), Time tracking skill (Replicon automation), future skills needing browser automation.

## Skill Tools

| Tool | Purpose |
|------|---------|
| `log_hours` | Add time entries to the master Excel from chat confirmation |
| `suggest_hours_from_calendar` | Read calendar events, propose time breakdown for a given day |
| `get_logged_hours` | Read back entries from master Excel for a date range |
| `push_to_replicon` | Sync entries to Replicon via browser automation |
| `fill_client_timesheet` | Fill a specific client's Excel template from master data |
| `list_projects` | Show configured projects with their IDs and mappings |
| `configure_project` | Add/update a project mapping in skill config |

## Project Data Storage

- **Skill config.yaml**: Authoritative project list (IDs, names, Replicon mappings, client adapter associations). Structured reference data that must be exact.
- **Nova's Graphiti memory**: Learned fuzzy associations and habits (e.g., "when I say 'client meeting' I mean PRJA-001", "I usually do 2h internal on Mondays"). Context and intelligence layer.

## Configuration

### Skill Config (`config.yaml`)

```yaml
# File paths (mounted via Docker volume)
timesheet_dir: "/data/timesheets"
templates_dir: "/data/timesheets/templates"
output_dir: "/data/timesheets/output"

# Projects
projects:
  - id: "PRJA-001"
    name: "ClientA - Development"
    replicon_project: "Project A"
    client_adapter: "client_a"
  - id: "INT-001"
    name: "Internal - Meetings"
    replicon_project: "Internal"
    client_adapter: null

# Replicon
replicon:
  url: "https://na2.replicon.com/yourcompany"
  sso_domains: ["your-sso-provider.com"]

# Browser (shared with other skills)
browser:
  profile_dir: "~/.nova/browser-profile"
```

### Docker Volume Mount

Add to `docker-compose.yaml`:
```yaml
volumes:
  - ~/timesheets:/data/timesheets
```

## File Structure

```
backend/skills/time_tracking/
  manifest.yaml          # Skill metadata
  instructions.md        # Agent workflow documentation
  tools.py              # Skill tool implementations
  config.yaml           # Skill configuration
  config.yaml.example   # Example config for setup
  adapters/
    base.py             # Base adapter class
    replicon.py         # Replicon browser automation adapter
    client_a.py         # ClientA Excel template adapter
    client_b.py         # ClientB Excel template adapter
```

## Dependencies

- `openpyxl` - Excel read/write
- `playwright` - Browser automation (already used by GitLab skill)
- Calendar/email access via existing Nova MCP servers (MS Graph / Google Workspace)

## Open Questions

- Replicon API availability: Need to verify with company IT if API access is enabled. Browser automation is the assumed primary path.
- Client template specifics: Each client adapter will need to be built when the template is provided. Start with one client to establish the pattern.
