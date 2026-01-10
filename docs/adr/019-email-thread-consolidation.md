# ADR-019: Email Thread Consolidation

**Status**: Accepted
**Date**: 2026-01
**Related**: [ADR-012](012-multi-input-hook-architecture-design.md)

---

## Context

When email conversations have multiple rapid replies (e.g., 3 people responding within 5 minutes), Nova's current email processing creates separate tasks for each email. This leads to:

1. **Fragmented AI responses**: The AI processes each email independently without full thread context
2. **Duplicate work**: Similar responses generated for related emails

### Current Behavior
```
Thread: "Project Discussion"
├─ Email 1 (9:00 AM) → Task 1: "Read Email: Project Discussion"
├─ Email 2 (9:05 AM) → Task 2: "Read Email: Re: Project Discussion"
└─ Email 3 (9:10 AM) → Task 3: "Read Email: Re: Project Discussion"
```

### Desired Behavior
```
Thread: "Project Discussion"
├─ Email 1 (9:00 AM) ─┐
├─ Email 2 (9:05 AM) ─┼→ Single Task: "Email Thread: Project Discussion (3 messages)"
└─ Email 3 (9:10 AM) ─┘   [waits for thread to stabilize before processing]
```

## Decision

Implement a **Hybrid Thread Consolidation** system with:

1. **Thread-based task grouping**: Emails with the same `thread_id` consolidate into a single task
2. **Stabilization window**: Wait N minutes after last email before processing (configurable, default 15 min). Window resets each time a new email arrives in the thread.
3. **State-dependent behavior**: Different handling based on whether Nova has already worked on the task

## Architecture

### Thread Handling by Task State

| Task Status | New Email Arrives | Action |
|-------------|-------------------|--------|
| **No task exists** | First email | Create new task with stabilization window |
| **NEW / USER_INPUT_RECEIVED** | More replies | Mark old task DONE (with superseded_by metadata), create new task with all emails consolidated |
| **DONE / FAILED** | Reply after completion | Create new task with LLM summary of old context |
| **IN_PROGRESS** | Reply during processing | Skip, handle on next poll after processing completes |

**Key insight**: If Nova hasn't started work yet, simply replace the task with a complete version. Only use LLM summarization when preserving actual AI work/decisions.

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                  EmailThreadConsolidator                        │
│  find_existing_thread_task() / supersede_unprocessed_task()    │
│  create_continuation_task() / summarize_completed_task()        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EmailProcessor                               │
│  _process_with_thread_consolidation()                          │
└─────────────────────────────────────────────────────────────────┘
```

| Component | Location | Purpose |
|-----------|----------|---------|
| EmailThreadConsolidator | `backend/input_hooks/email_processing/thread_consolidator.py` | Thread-based task management |
| EmailProcessor | `backend/input_hooks/email_processing/processor.py` | Integration point |

## Configuration

Add these new settings to the email hook configurations in `configs/input_hooks.yaml`:

```yaml
# configs/input_hooks.yaml
hooks:
  gmail:
    hook_settings:
      # ... existing settings ...
      thread_consolidation_enabled: true
      thread_stabilization_minutes: 15  # Wait 15 min after last email

  outlook_email:
    hook_settings:
      # ... existing settings ...
      thread_consolidation_enabled: true
      thread_stabilization_minutes: 15
```

**Note**: The hook config models in `backend/input_hooks/models.py` will need corresponding schema updates to validate these new fields.

## Task Metadata

Tasks with thread consolidation store additional metadata:

```json
{
  "email_thread_id": "thread_abc123",
  "email_count": 3,
  "is_thread_stabilizing": true,
  "thread_stabilization_ends_at": "2026-01-15T10:45:00Z",
  "previous_task_id": "uuid-of-completed-task",
  "previous_task_summary": "LLM-generated summary of previous conversation",
  "superseded_by_task_id": "uuid-of-new-task",
  "superseded_reason": "thread_consolidation"
}
```

## Core Agent Integration

The Core Agent's `_get_next_task()` method in `backend/agent/core_agent.py` must be updated to skip tasks still in stabilization. Add this filter to both the `USER_INPUT_RECEIVED` and `NEW` task queries:

```python
from sqlalchemy import or_
from datetime import datetime

now = datetime.utcnow()

# Filter out stabilizing tasks
not_stabilizing = or_(
    Task.task_metadata['is_thread_stabilizing'].astext.is_(None),
    Task.task_metadata['is_thread_stabilizing'].astext == 'false',
    Task.task_metadata['thread_stabilization_ends_at'].astext < now.isoformat()
)

# Add .where(not_stabilizing) to existing queries in _get_next_task()
result = await session.execute(
    select(Task)
    .options(selectinload(Task.comments))
    .where(Task.status == TaskStatus.NEW)
    .where(not_stabilizing)  # NEW: Skip stabilizing tasks
    .order_by(Task.updated_at.asc())
    .limit(1)
)
```

## Consequences

### Positive

- **Better AI responses**: Full thread context available before processing
- **Reduced task noise**: One task per conversation instead of many
- **Mirrors human behavior**: Humans wait for conversation to settle before responding

### Negative

- **Added latency**: Stabilization window delays processing by N minutes
- **Complexity**: More logic for state-dependent behavior
- **LLM cost**: Summarization for continuation tasks requires extra API call

### Risks

- **Race conditions**: Two emails arriving simultaneously could conflict. Low probability given typical email volumes (~100/day); acceptable for MVP.
- **Large threads**: Threads with 20+ emails could create very long task descriptions. Consider truncating to most recent N emails with summary of older ones.

## Data Integrity

- **ProcessedItem records**: Remain pointing to original task (now marked DONE with superseded_by metadata). When querying "which task handles this email?", follow `superseded_by_task_id` chain to find the active task.
- **Email content storage**: Full content stored in ProcessedItem.source_metadata for reconstruction
- **Superseded tasks**: Marked DONE with `superseded_by_task_id` and `superseded_reason` in metadata, preserving full audit trail
- **New consolidated task**: Stores `supersedes_task_ids: [uuid1, uuid2, ...]` array in metadata to link back to all replaced tasks

## API Visibility

The `TaskResponse` model in `backend/models/tasks.py` needs to expose thread consolidation fields so the frontend can display appropriate UI states (e.g., "Waiting for more emails...").

### Required TaskResponse Updates

```python
# Add to TaskResponse in backend/models/tasks.py

# Thread consolidation fields (from task_metadata)
email_thread_id: Optional[str] = Field(None, description="Email thread ID for consolidated tasks")
email_count: Optional[int] = Field(None, description="Number of emails in consolidated thread")
is_thread_stabilizing: bool = Field(False, description="Whether task is waiting for thread to stabilize")
thread_stabilization_ends_at: Optional[datetime] = Field(None, description="When stabilization window ends")
superseded_by_task_id: Optional[UUID] = Field(None, description="ID of task that superseded this one")
```

### Frontend UI States

| Condition | UI Display |
|-----------|------------|
| `is_thread_stabilizing=true` | "Waiting for more emails..." with countdown |
| `email_count > 1` | Badge showing "3 emails" |
| `superseded_by_task_id` set | Dim task, show "Superseded" label with link |

### Serialization

The API endpoint that returns `TaskResponse` must extract these fields from `task_metadata` JSON and map them to the response model fields.

## Related ADRs

- **ADR-012**: Multi-input hook architecture (base infrastructure)
- **ADR-002**: Human-in-the-loop (USER_INPUT_RECEIVED state handling)

---
*Last reviewed: 2026-01*
