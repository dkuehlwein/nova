# ADR-018: Service Layer Architecture

**Status**: Implemented
**Date**: 2026-01-09

> **Implementation Notes**: ChatService in `backend/services/chat_service.py`, ConversationService in `backend/services/conversation_service.py`. Utility functions in `backend/utils/langgraph_utils.py` and `backend/utils/checkpointer_utils.py`.

---

## Context

Nova's `chat_endpoints.py` had grown to 1,220+ lines, mixing HTTP handling with business logic:
- **Tight coupling**: Endpoint handlers contained streaming logic, message conversion, and memory injection
- **Hard to test**: Testing required mocking HTTP layers to test business logic
- **Code duplication**: Similar patterns repeated across endpoints
- **Maintenance burden**: Changes to core logic required understanding HTTP context

## Decision

Implement a **Service Layer Pattern** that separates HTTP concerns from business logic:
- **Thin endpoints**: FastAPI routes handle only HTTP concerns (validation, response formatting)
- **Service classes**: Encapsulate business logic, state management, and external integrations
- **Utility modules**: Shared constants and helper functions

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Endpoints                         │
│  chat_endpoints.py (~250 lines) - HTTP handlers only        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                            │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │   ChatService       │    │  ConversationService        │ │
│  │   (~550 lines)      │    │  (~520 lines)               │ │
│  │                     │    │                             │ │
│  │   - stream_chat()   │    │  - list_threads()           │ │
│  │   - check_interrupts│    │  - get_history()            │ │
│  │   - resume_interrupt│    │  - get_summary()            │ │
│  │   - is_first_turn() │    │  - delete()                 │ │
│  │   - inject_memory() │    │  - cleanup_task_chat_data() │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Utility Modules                           │
│  langgraph_utils.py - Config helpers, constants              │
│  checkpointer_utils.py - PostgreSQL checkpointer access      │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| ChatService | `backend/services/chat_service.py` | Chat streaming, LangGraph interaction, memory injection |
| ConversationService | `backend/services/conversation_service.py` | Thread management, history retrieval, CRUD |
| langgraph_utils | `backend/utils/langgraph_utils.py` | Shared constants, config creation |
| checkpointer_utils | `backend/utils/checkpointer_utils.py` | ServiceManager checkpointer access |

## Design Patterns

### Type-Safe Checkpointer Protocol

Services use a Protocol to type-hint checkpointer parameters without importing AsyncPostgresSaver directly:

```python
@runtime_checkable
class CheckpointerProtocol(Protocol):
    async def aget(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]: ...
    def alist(self, config: Optional[Dict[str, Any]]) -> AsyncIterator: ...
```

This avoids circular imports and allows testing with any checkpointer implementation.

### Lazy Imports for Circular Dependency Prevention

Imports that would cause circular dependencies are done inside function bodies:

```python
async def get_title(self, thread_id: str, messages: List) -> str:
    if thread_id.startswith(TASK_THREAD_PREFIX):
        # Import inside function to avoid circular dependency
        from database.database import db_manager
        from models.models import Task
```

### Global Service Instances

Services are instantiated as module-level singletons for consistent access:

```python
# At end of chat_service.py
chat_service = ChatService()
```

Endpoints import and use these instances directly.

## Testing Strategy

| Level | Directory | What's Tested |
|-------|-----------|---------------|
| Unit | `tests/unit/test_services/` | Service methods with mocked checkpointers |
| Integration | `tests/integration/test_chat_services.py` | Services with real checkpointers (InMemory, PostgreSQL) |

## Consequences

### Positive

- **Testability**: Services can be tested independently of HTTP layer
- **Maintainability**: Clear separation of concerns, smaller files
- **Reusability**: Services can be used by multiple endpoints or background tasks
- **Type safety**: Protocol-based typing catches errors at development time

### Negative

- **Indirection**: Additional layer between endpoints and logic
- **Import complexity**: Lazy imports required for circular dependency prevention

### Risks

- **Service growth**: Services could grow large again; split further if needed
- **Singleton state**: Global instances could cause issues in concurrent tests (mitigated by using separate checkpointers)

## Related ADRs

- **ADR-010**: Health monitoring (unified health endpoint pattern)
- **ADR-004**: Configuration management (similar layered approach)

---
*Last reviewed: 2026-01-09*
