# NOV-135: Adopt Structured Logging Pattern Across Backend

**Linear ticket:** NOV-135
**Branch:** refactor/NOV-135-adopt-structured-logging

## Investigation

### Current State

The codebase has two logging problems:

1. **Wrong logger initialization** -- 8 files use `import logging` + `logging.getLogger(__name__)` instead of the project's `get_logger()` from `utils/logging.py`. These bypass the structlog pipeline entirely.

2. **F-string log messages** -- ~350 instances across ~45 files use `logger.info(f"...")` instead of `logger.info("static message", extra={"data": {...}})`. This embeds dynamic data into the message string rather than structured fields.

3. **Plain string logs without extra** -- ~167 instances use plain strings like `logger.info("Something happened")` without `extra={}` context where variables are available. Many of these are fine (truly static messages), but some embed no structured data when they could.

### Files Using Wrong Logger (logging.getLogger instead of get_logger)

- `backend/init_db.py`
- `backend/agent/core_agent.py`
- `backend/api/api_endpoints.py` (inline `logging.getLogger` calls)
- `backend/api/memory_endpoints.py`
- `backend/memory/memory_functions.py`
- `backend/utils/tool_permissions_manager.py`
- `backend/tools/human_escalation_tool.py`
- `backend/tools/memory_tools.py`

### Files With Most F-String Logging (top offenders)

- `backend/agent/core_agent.py` (~25 instances)
- `backend/skills/add_user_to_coe_gitlab/gitlab_client.py` (~20 instances)
- `backend/skills/add_user_to_coe_gitlab/lam_automation.py` (~18 instances)
- `backend/services/llm_service.py` (~18 instances)
- `backend/services/chat_service.py` (~17 instances)
- `backend/services/conversation_service.py` (~16 instances)
- `backend/tools/tool_approval_helper.py` (~15 instances)
- `backend/utils/tool_permissions_manager.py` (~14 instances)
- `backend/services/health_monitor.py` (~7 instances)
- `backend/mcp_client.py` (~16 instances)
- `backend/utils/service_manager.py` (~10 instances)
- `backend/api/api_endpoints.py` (~12 instances)
- `backend/api/chat_endpoints.py` (~10 instances)
- Plus ~30 other files with 1-6 instances each

### The Structured Logging Pattern (from utils/logging.py)

The project uses `structlog` with a `get_logger()` factory. The expected pattern:

```python
from utils.logging import get_logger
logger = get_logger(__name__)

# Good: static message + structured data
logger.info("Model added to LiteLLM", extra={"data": {"model_name": model_name}})

# Bad: f-string embeds data in message
logger.info(f"Added new model: {model_name}")
```

The `extra={"data": {...}}` convention nests all contextual data under a `data` key. The structlog pipeline adds timestamp, level, service, and request_id automatically via context variables.

## Approach

### Strategy: Mechanical conversion, file by file

1. **Fix logger imports first** (Task 2): Replace `import logging` / `logging.getLogger(__name__)` with `from utils.logging import get_logger` / `get_logger(__name__)`. Only remove `import logging` if no other usage remains.

2. **Convert f-string logging** (Task 3): For each `logger.xxx(f"...")` call:
   - Extract a static message describing the event
   - Move dynamic values into `extra={"data": {...}}`
   - Keep messages concise and human-readable

3. **Enrich plain log calls** (Task 4): For calls that already use static strings but lack `extra` where contextual data is available, add it. Skip truly static messages ("Server started", etc.) -- those are fine without extra data.

### Conversion Rules

| Before | After |
|--------|-------|
| `logger.info(f"Added model: {name}")` | `logger.info("Added model", extra={"data": {"model_name": name}})` |
| `logger.error(f"Failed to add {name}: {e}")` | `logger.error("Failed to add model", extra={"data": {"model_name": name, "error": str(e)}})` |
| `logger.debug(f"[{ns}] Reusing context")` | `logger.debug("Reusing browser context", extra={"data": {"namespace": ns}})` |
| `logger.warning(f"Error: {e}")` | `logger.warning("Operation failed", extra={"data": {"error": str(e)}})` |

### What NOT to change

- `utils/logging.py` itself (except the one f-string in `log_timing`)
- Test files
- Files that already use the correct pattern
- The `logging.getLogger()` calls in `utils/service_manager.py` that suppress third-party library log levels (those are correct usage of stdlib logging)

## Key Files to Modify

Every backend .py file that has logging. The full list (~50 files) is too long for this plan -- see Investigation section for the breakdown by category. The work will proceed directory by directory:

1. `backend/*.py` (init_db.py, start_website.py, start_core_agent.py, mcp_client.py)
2. `backend/agent/` (chat_agent.py, core_agent.py)
3. `backend/api/` (all endpoint files)
4. `backend/services/` (all service files)
5. `backend/utils/` (all utility files)
6. `backend/tools/` (all tool files)
7. `backend/memory/` (memory_functions.py)
8. `backend/input_hooks/` (all hook and processing files)
9. `backend/skills/` (all skill files)
10. `backend/tasks/` (hook_tasks.py)

## Open Questions / Risks

- **No functional changes**: This is purely a logging format change. All assertions, return values, and control flow must remain identical.
- **Some f-strings in log_timing (utils/logging.py)**: The `log_timing` helper itself uses an f-string. I will convert this too for consistency, but it already includes `extra={"data": data}`.
- **exc_info parameter**: Some error logs use `exc_info=True`. This parameter should be preserved alongside the new `extra` parameter.
