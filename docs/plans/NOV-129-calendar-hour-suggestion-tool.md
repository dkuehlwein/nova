# NOV-129: Implement calendar-based hour suggestion tool

**Linear ticket:** NOV-129
**Branch:** `feature/NOV-129-calendar-hour-suggestion-tool`
**Date:** 2026-02-19

## Investigation notes

- The placeholder stub is in `backend/skills/time_tracking/tools.py` (lines 216-235). It returns `success: False` with "not yet configured".
- The `call_mcp_tool()` interface is in `backend/mcp_client.py`. It takes `server_name`, `tool_name`, and `arguments` dict. It returns parsed text from MCP response content blocks, handles auth retries for MS Graph.
- The existing test in `test_time_tracking_tools.py` (`TestPlaceholderStubs.test_suggest_hours_returns_not_configured`) expects the stub behavior. This test needs to be updated/removed since we're replacing the stub.
- The `mock_config` fixture in `test_time_tracking_tools.py` needs to be shared. I'll extract it to a `conftest.py` in `tests/unit/skills/`.
- MS Graph calendar events use `subject`, `start.dateTime`, `end.dateTime` format.
- Reference pattern: `backend/skills/add_user_to_coe_gitlab/tools.py` shows how to call MCP tools -- import `mcp_manager` inside the function, call `await mcp_manager.call_mcp_tool(...)`, parse string/dict results.

## Approach

1. **Extract `mock_config` fixture** to `tests/unit/skills/conftest.py` so it's shared between test files. Remove the duplicate from `test_time_tracking_tools.py`.

2. **Write failing tests first** in `tests/unit/skills/test_time_tracking_calendar.py`:
   - `test_suggests_hours_from_calendar_events` -- mock `_get_calendar_events`, verify suggestions are produced with correct structure
   - `test_handles_no_calendar_events` -- mock empty events, verify `success: True` with empty suggestions
   - `test_handles_mcp_not_configured` -- mock `_get_calendar_events` raising an exception, verify graceful fallback
   - `test_matches_events_to_configured_projects` -- verify project matching logic

3. **Add helper function** `_get_calendar_events(target_date)` to `tools.py`:
   - Import `mcp_manager` from `mcp_client`
   - Call MS Graph `list_calendar_events` with date range
   - Parse result (string -> JSON if needed), extract events list
   - Return empty list on any failure

4. **Replace the stub** `suggest_hours_from_calendar` in `tools.py`:
   - Default `target_date` to today if empty
   - Call `_get_calendar_events()`
   - Parse events: subject -> potential project match, start/end -> hours calculation
   - Match events against configured projects (case-insensitive substring match on subject)
   - Return suggestions with `next_action` for user confirmation

5. **Update the old placeholder test** in `test_time_tracking_tools.py` to reflect new behavior (or remove it since calendar tests cover it).

## Key files to modify

- `backend/skills/time_tracking/tools.py` -- add `_get_calendar_events()`, replace `suggest_hours_from_calendar` stub
- `tests/unit/skills/conftest.py` -- new file, extract shared `mock_config` fixture
- `tests/unit/skills/test_time_tracking_calendar.py` -- new test file
- `tests/unit/skills/test_time_tracking_tools.py` -- remove `mock_config` fixture (now in conftest), update placeholder test

## Open questions

- The MS Graph `list_calendar_events` tool name is assumed. The actual tool name depends on what's configured in LiteLLM. The helper catches all exceptions so this is safe.
- Project matching is best-effort (substring match on event subject vs project name). This may need refinement based on user feedback.
