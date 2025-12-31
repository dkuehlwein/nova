# ADR-013: Human Oversight Tool Approval System

**Status**: Accepted - Implemented
**Date**: 2025-09-03
**Updated**: 2025-12-31

> **Implementation Notes**: LangGraph interrupt-based approval system fully operational. Tools wrapped: `create_task`, `update_task`, `add_memory`. Pre-approved: `get_tasks`, `get_task_by_id`, `search_memory`. Config: `configs/tool_permissions.yaml`. Frontend: EscalationBox component handles approvals.

---

## Context

Nova's AI agents had unrestricted tool access, creating risks:
- No human review before tool execution
- EU AI Act compliance gap (Article 14 requires human oversight)
- No audit trail for critical actions
- Users couldn't control agent autonomy

## Decision

Implement a **Unified Interrupt-Based Tool Approval System** that:
- Uses official LangGraph `interrupt()` pattern for tool approval requests
- Integrates with existing `ask_user` escalation flow
- Provides three-value approval: `approve`, `always_allow`, `deny`
- Stores permissions in YAML with hot-reload support

## Architecture

```
User Request → Agent → Tool Call
                         │
                         ▼
              ┌──────────────────┐
              │ Permission Check │
              └────────┬─────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
    Pre-approved               Needs Approval
         │                           │
         ▼                           ▼
    Execute Tool            interrupt() → UI
         │                           │
         │                    User Response
         │                           │
         │              ┌────────────┴────────────┐
         │              │            │            │
         │           approve    always_allow    deny
         │              │            │            │
         │              ▼            ▼            ▼
         │         Execute     Add to config   Return
         │                     + Execute       denial
         │                           │
         └───────────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Tool Wrapper | `backend/tools/tool_approval_helper.py` | `add_human_in_the_loop()` wrapper |
| Permission Config | `backend/utils/tool_permissions_manager.py` | YAML config with pattern matching |
| Config File | `configs/tool_permissions.yaml` | Permission rules |
| Interrupt Handler | `backend/agent/core_agent.py` | Unified handling in `_handle_interrupt()` |
| API Endpoint | `backend/api/chat_endpoints.py` | `/escalation-response` endpoint |
| Frontend | `frontend/src/components/EscalationBox.tsx` | Approval UI component |

## Permission Configuration

```yaml
# configs/tool_permissions.yaml
permissions:
  allow:
    - get_tasks
    - search_memory
    - get_task_by_id
  deny:
    - "mcp_tool(*)"  # External tools require approval

settings:
  default_secure: true  # Unknown tools require approval
  audit_enabled: true
```

### Pattern Syntax

- `ToolName` - Allow all calls to tool
- `ToolName(*)` - Allow any arguments
- `ToolName(arg=value)` - Allow specific argument patterns
- Deny rules override allow rules

## Integration

### Unified Interrupt Handling

Both `ask_user` questions and tool approvals:
- Move tasks to `NEEDS_REVIEW` status
- Display in the same UI section
- Use the same EscalationBox component (with different styling)
- Resume via LangGraph `Command(resume=response)`

### Frontend Flow

1. Agent requests tool approval via `interrupt()`
2. Task moves to "needs_review" kanban column
3. EscalationBox shows tool name, arguments, and approval buttons
4. User clicks Approve/Always Allow/Deny
5. Response sent to `/escalation-response` endpoint
6. Agent resumes with decision

## Consequences

### Positive

- EU AI Act Article 14 compliant
- Consistent UX with existing escalation system
- Granular permission control via patterns
- Hot-reload configuration updates
- Audit trail via LangGraph checkpoints

### Negative

- Adds latency for unapproved tools
- Users must manage permission configuration
- Initial setup requires approval for most actions

### Risks

- **Permission creep**: Users may over-allow. Mitigated by audit dashboard.
- **Config corruption**: Invalid YAML breaks system. Mitigated by validation and backups.

## Related ADRs

- **ADR-002**: Human-in-the-loop architecture (ask_user tool)
- **ADR-004**: Configuration management (YAML hot-reload)

---
*Last reviewed: 2025-12-31*
