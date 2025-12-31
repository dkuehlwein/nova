# ADR-012: Multi-Input Hook Architecture

**Status**: Accepted - Implemented
**Date**: 2025-10
**Updated**: 2025-12-31
**Supersedes**: [ADR-006](archive/006-email-integration-architecture.md)

> **Implementation Notes**: Registry-based hook architecture implemented. `BaseInputHook` and `InputHookRegistry` in `backend/input_hooks/`. EmailInputHook and CalendarInputHook operational. Configuration via `configs/input_hooks.yaml` with hot-reload. Celery integration with dynamic beat scheduling.

---

## Context

Nova's email processing system needed to support multiple input sources (calendar, IMAP, Outlook, etc.) with a flexible hook system. Each input type needs:
- Custom polling sequences
- Ability to create new tasks OR update existing ones
- Independent configuration and scheduling

The existing email system demonstrated solid patterns but was hardcoded for email only.

## Decision

Implement a **Registry-Based Hook Architecture** extending Nova's proven `ConfigRegistry` pattern:
- `BaseInputHook` abstract class for all input sources
- `InputHookRegistry` for centralized hook management
- YAML configuration with hot-reload support
- Generic Celery tasks with dynamic scheduling

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      InputHookRegistry                          │
│  register_hook() / start_all_polling() / process_hook_items()  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BaseInputHook (ABC)                          │
│  fetch_items() / normalize_item() / should_create_task()       │
│  should_update_task() / process_items()                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────────┐
                    ▼                       ▼
        ┌───────────────────┐    ┌──────────────────────┐
        │   EmailInputHook  │    │   CalendarInputHook  │
        └───────────────────┘    └──────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| BaseInputHook | `backend/input_hooks/base_hook.py` | Abstract class for all hooks |
| InputHookRegistry | `backend/input_hooks/hook_registry.py` | Centralized hook management |
| EmailInputHook | `backend/input_hooks/email_hook.py` | Email → Task conversion |
| CalendarInputHook | `backend/input_hooks/calendar_hook.py` | Calendar events processing |
| Hook Tasks | `backend/tasks/hook_tasks.py` | Generic Celery task |
| Config | `configs/input_hooks.yaml` | Per-hook configuration |

## Hook Configuration

```yaml
# configs/input_hooks.yaml
hooks:
  email:
    name: "email"
    hook_type: "email"
    enabled: true
    polling_interval: 300
    queue_name: "email"
    create_tasks: true
    update_existing_tasks: false
    hook_settings:
      max_per_fetch: 50

  calendar:
    name: "calendar"
    hook_type: "calendar"
    enabled: true
    polling_interval: 600
    queue_name: "calendar"
    create_tasks: true
    update_existing_tasks: true
    hook_settings:
      look_ahead_days: 7
```

## Processing Pipeline

All hooks follow a common pipeline:
1. **Fetch**: Get new items from source
2. **Normalize**: Convert to standard `NormalizedItem` format
3. **Decide**: Should create task? Should update existing?
4. **Execute**: Create/update tasks as needed
5. **Record**: Track processed items to prevent duplicates

### Celery Integration

Dynamic beat scheduling based on hook configuration:
- Each enabled hook gets its own scheduled task
- Polling intervals configurable per hook
- Separate queues for isolation

## Capabilities

### Task Creation
Hooks can create tasks from input items (e.g., email → "Read Email: {subject}")

### Task Updates
Hooks can update existing tasks (e.g., calendar event changes update linked task)

### Scheduled Actions
Calendar hook example: Schedule prep documents 15 minutes before meetings using Celery `eta` parameter.

## Consequences

### Positive

- Extensible design for unlimited input sources
- Zero-risk migration (existing email system unchanged)
- Consistent processing patterns across all hooks
- Per-hook configuration with hot-reload
- Incremental development (add one hook at a time)

### Negative

- Additional abstraction layer complexity
- Need to maintain hook registry
- Each new hook requires implementation

### Risks

- **Queue overload**: Many hooks polling simultaneously. Mitigated by separate queues.
- **Deduplication complexity**: Different sources have different ID schemes. Mitigated by `source_type + source_id` composite key.

## Database Schema

```sql
-- Generalized table for all hooks
CREATE TABLE processed_items (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR NOT NULL,  -- 'email', 'calendar', etc.
    source_id VARCHAR NOT NULL,
    source_metadata JSONB,
    task_id VARCHAR,
    processed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_type, source_id)
);
```

## Related ADRs

- **ADR-004**: Configuration management (hot-reload for hook configs)
- **ADR-005**: Real-time settings (Celery beat scheduling)

---
*Last reviewed: 2025-12-31*
