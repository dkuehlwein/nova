# NOV-128: Implement Core Skill Tools

**Linear ticket:** https://linear.app/nova-development/issue/NOV-128/implement-core-skill-tools-log-hours-get-logged-hours-list-projects

## Investigation/Analysis

- The `time_tracking` skill already has a skeleton: `manifest.yaml`, `config.yaml.example`, `instructions.md`, `excel_manager.py`, and `__init__.py`.
- `excel_manager.py` provides `log_entries()` and `read_entries()` -- these are the workhorses that `tools.py` wraps.
- The existing `add_user_to_coe_gitlab/tools.py` establishes the pattern: async tools decorated with `@tool`, JSON string returns with `next_action`, `_load_skill_config()` / `_save_skill_config()` helpers, `_import_skill_module()` for sibling imports, and a `get_tools()` export.
- `test_time_tracking_discovery.py` verifies that SkillManager discovers the skill -- it must keep passing after adding tools.py.
- `test_time_tracking_excel.py` tests the lower-level excel_manager functions directly.

## Approach

Follow TDD (Red-Green-Refactor):

1. Write `tests/unit/skills/test_time_tracking_tools.py` with tests for all four core tools and the `get_tools()` function.
2. Verify tests fail (import error, since `tools.py` doesn't exist).
3. Implement `backend/skills/time_tracking/tools.py` following the reference plan closely:
   - `_load_skill_config()`, `_save_skill_config()`, `_import_skill_module()` helpers
   - `log_hours` tool: parses JSON entries, delegates to `excel_manager.log_entries()`
   - `get_logged_hours` tool: delegates to `excel_manager.read_entries()`, computes totals
   - `list_projects` tool: reads projects from config
   - `configure_project` tool: adds/updates a project in config, saves
   - Placeholder stubs: `suggest_hours_from_calendar`, `push_to_replicon`, `fill_client_timesheet`
   - `get_tools()`: returns all 7 tools
4. Verify all tests pass.
5. Run full skill test suite to ensure no regressions.

## Key Files

| Action | File |
|--------|------|
| Create | `backend/skills/time_tracking/tools.py` |
| Create | `tests/unit/skills/test_time_tracking_tools.py` |
| Reference | `backend/skills/add_user_to_coe_gitlab/tools.py` |
| Reference | `backend/skills/time_tracking/excel_manager.py` |
| Must keep passing | `tests/unit/skills/test_time_tracking_discovery.py` |

## Open Questions / Risks

- The `configure_project` tool's "added" vs "updated" action detection in the reference plan has a subtle bug: after updating `projects[i]`, the `any()` check on `projects[:-1]` would always find the match (since update happened in-place before the `else` branch). The for/else pattern handles this correctly -- the `else` only runs if `break` was never hit. The `action` field computation needs care; will use a flag variable for clarity.
- Tests use a real `config.yaml` written by the `mock_config` fixture. Need to ensure cleanup happens even if tests fail (fixture uses yield + unlink).
