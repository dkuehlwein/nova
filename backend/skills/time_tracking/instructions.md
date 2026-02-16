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

### Tools

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
