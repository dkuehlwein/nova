# DRAFT: Hierarchical Agent Architecture

**Status**: Proposed
**Date**: 2025-07

---

## Context

The current `chat_agent` is a simple reactive agent (LangGraph `create_react_agent`). It struggles with complex, multi-step instructions because it lacks:
- Formal planning mechanism
- Step-by-step execution tracking
- Self-verification against an initial plan

Note: The `chat_agent` and `core_agent` are independent peers, not a hierarchy. This proposal introduces hierarchy *within* the chat agent.

## Decision

Refactor the `chat_agent` into a **Hierarchical Agent** with:
- **Supervisor Agent**: Plans, delegates, tracks progress, synthesizes results
- **Worker Agent**: Executes single well-defined tasks

## Architecture

```
User Request
      │
      ▼
┌─────────────────┐
│   Supervisor    │
│   (Planner)     │
└────────┬────────┘
         │ Creates plan
         ▼
┌─────────────────┐
│   Supervisor    │
│   (Delegator)   │──────────┐
└────────┬────────┘          │
         │                   │
    ┌────┴────┐         ┌────┴────┐
    ▼         ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│Worker │ │Worker │ │Worker │ │Worker │
│ Task1 │ │ Task2 │ │ Task3 │ │ Task4 │
└───────┘ └───────┘ └───────┘ └───────┘
         │
         ▼
┌─────────────────┐
│   Supervisor    │
│  (Synthesizer)  │
└─────────────────┘
         │
         ▼
   Final Response
```

### Supervisor Responsibilities
- Analyze user request and create todo list
- Store plan in `AgentState` (persisted via checkpointer)
- Invoke Worker for each step
- Stream progress updates to UI
- Synthesize final response

### Worker Responsibilities
- Execute single, focused task
- Use Nova's full toolset (MCP, memory, etc.)
- Report result to Supervisor

## Workflow

1. User submits complex request
2. Supervisor creates plan, streams to UI
3. For each plan item:
   - Supervisor invokes Worker as tool
   - Worker executes single task
   - Supervisor updates state, streams progress
4. Supervisor synthesizes final answer

## Consequences

### Positive

- Improved reliability for complex tasks
- Visible execution plan increases transparency
- Standard agentic pattern, well-documented

### Negative

- Added latency from planning step
- Increased implementation complexity

## Next Steps

1. Create `backend/agent/worker_agent.py`
2. Refactor `backend/agent/chat_agent.py` for Supervisor pattern
3. Update `create_chat_agent()` to compose both graphs
4. Add tests for hierarchical interaction

---
*Draft - Not yet implemented*
