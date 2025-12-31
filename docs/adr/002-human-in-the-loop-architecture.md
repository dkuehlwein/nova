# ADR-002: Human-in-the-Loop Architecture

**Status**: Accepted - Partially Implemented
**Date**: 2025-06-06
**Updated**: 2025-12-31

> **Implementation Notes**: Core agent interrupt handling and `ask_user` escalation tool implemented. Task chat integration functional via LangGraph checkpointer. Chat button on task cards pending.

---

## Context

Nova's core agent needed bidirectional human communication:
- Agent should be able to escalate questions to humans
- Humans should be able to interrupt agent processing
- All communication should happen in existing task chat threads
- Agent should continue processing other tasks while waiting

## Decision

Enhance Nova with bidirectional human-in-the-loop capabilities using:
- **Existing LangGraph chat threads** (one per task)
- **LangGraph interrupt mechanism** for pausing agent execution
- **Task status flow** to signal human attention needed
- **Unified chat interface** for all agent-human communication

## Architecture

```
Agent Processing Task
        │
        ▼
┌───────────────────────────────────┐
│  Agent or Human Needs Communication?  │
└───────────────────────────────────┘
        │
   ┌────┴────┐
   │         │
Agent     Human
Escalation  Interruption
   │         │
   ▼         ▼
ask_user   Chat message
tool       on task
   │         │
   ▼         ▼
LangGraph   Task status →
interrupt   USER_INPUT_RECEIVED
   │         │
   ▼         │
Task →      │
NEEDS_REVIEW│
   │         │
   └────┬────┘
        │
        ▼
Agent resumes in next cycle
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| ask_user Tool | `backend/tools/escalation_tools.py` | Agent-initiated escalation |
| Core Agent | `backend/agent/core_agent.py` | Interrupt handling, task prioritization |
| Chat Endpoints | `backend/api/chat_endpoints.py` | Task chat API |
| LangGraph Checkpointer | PostgreSQL | Thread persistence |

### Thread ID Pattern

`f"core_agent_task_{task.id}"` - Each task has a dedicated chat thread.

## Communication Flows

### Agent Escalation
1. Agent calls `ask_user` tool with question
2. LangGraph `interrupt()` triggered
3. Task moves to `NEEDS_REVIEW` status
4. Human responds via task chat
5. Task moves to `USER_INPUT_RECEIVED`
6. Agent resumes conversation

### Human Interruption
1. Human opens task chat and sends message
2. Task moves to `USER_INPUT_RECEIVED`
3. Agent picks up task in next processing cycle
4. Conversation continues naturally

## Task Status Flow

```
NEW → IN_PROGRESS → [escalation] → NEEDS_REVIEW → [human response] → USER_INPUT_RECEIVED → IN_PROGRESS → DONE
```

Tasks with `USER_INPUT_RECEIVED` status are prioritized in the agent's task queue.

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/tasks/{id}/chat` | Get task chat messages |
| `POST /api/tasks/{id}/chat/message` | Post human message |
| `GET /api/tasks?status=needs_review` | Filter tasks needing attention |

## Consequences

### Positive

- Transparent AI reasoning visible to humans
- Non-blocking operation during escalations
- Zero infrastructure changes (uses existing LangGraph)
- Unified interface replaces separate comment systems

### Negative

- Adds complexity to task status management
- Human response latency affects task completion time
- Requires UI changes for chat access on tasks

### Risks

- **LangGraph interrupt failure**: Fallback error handling, manual task restart
- **Users missing escalations**: Visual indicators, future notification system

## Related ADRs

- **ADR-013**: Tool approval system (uses same interrupt pattern)

---
*Last reviewed: 2025-12-31*
