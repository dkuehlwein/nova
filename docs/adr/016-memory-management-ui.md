# ADR-016: Memory Management UI

**Status**: Implemented
**Date**: 2025-01-08
**Updated**: 2025-01-08

> **Implementation Notes**: Memory Management tab added to Settings page. React Query hooks in `useNovaQueries.ts`. Component in `settings/page.tsx`. Backend endpoints already existed in `memory_endpoints.py`.

---

## Context

Nova uses Graphiti (Neo4j-based knowledge graph) to store and retrieve contextual memory/facts about users and conversations. The memory system was accessible only via:
- API endpoints (`/api/memory/*`)
- Direct Neo4j Browser queries (localhost:7474)
- `curl` commands

This created several issues:
- No user-friendly way to view stored memories
- Corrupted or test data ("garbage facts") could poison LLM context
- Users couldn't easily clean up incorrect information
- No visibility into what Nova "knows" about them

## Decision

Add a **Memory Management tab** to the existing Settings page with functionality to:
1. **View** - List stored memory facts with search capability
2. **Add** - Manually add new memories/facts to the knowledge graph
3. **Delete** - Remove individual facts or clear all memories
4. **Monitor** - Display memory system health status

### Why Settings Tab vs Other Approaches

| Option | Pros | Cons |
|--------|------|------|
| **Settings Tab** (chosen) | Consistent with existing admin features, no new routes, quick to implement | Limited space for future graph visualization |
| Dedicated `/memories` page | More space, could add graph visualization later | Another route to maintain, feels separate from other settings |
| Sidebar/Modal | Non-intrusive, accessible from anywhere | Limited space, UX complexity |

The Settings tab approach was chosen because:
- Memory management is an admin/configuration concern, fitting with other settings
- MVP approach - simple list view is sufficient for initial needs
- Can evolve to dedicated page later if graph visualization is needed

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Settings Page                             │
├─────────────────────────────────────────────────────────────┤
│ [Personal] [AI Models] [API Keys] [Automation]              │
│ [Memory] [System Prompt] [MCP Servers] [Skills] [Status]    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Memory Tab                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────┐  [Health: ●]       │
│  │ Add Memory                           │                    │
│  │ Content: [________________]          │                    │
│  │ Source:  [________________]          │                    │
│  │                         [Add Memory] │                    │
│  └─────────────────────────────────────┘                    │
│                                                              │
│  Search: [__________________] 🔍                             │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ "Daniel loves pizza"                          [🗑 Delete]││
│  │ Created: 2025-01-08                                      ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ "Project Nova uses LangGraph"                 [🗑 Delete]││
│  │ Created: 2025-01-07                                      ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Clear All Memories]                                        │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Frontend (React)                    Backend (FastAPI)              Graphiti/Neo4j
       │                                   │                            │
       │── useMemorySearch(query) ────────►│                            │
       │                                   │── search_memory() ────────►│
       │◄── MemorySearchResponse ─────────│◄── results ────────────────│
       │                                   │                            │
       │── useAddMemory(content) ─────────►│                            │
       │                                   │── add_memory() ───────────►│
       │◄── MemoryAddResponse ────────────│◄── episode/nodes ─────────│
       │                                   │                            │
       │── useDeleteMemoryFact(uuid) ─────►│                            │
       │                                   │── delete_fact() ──────────►│
       │◄── MemoryDeleteResponse ─────────│◄── success ────────────────│
```

## Implementation

### Files Modified

| File | Changes |
|------|---------|
| `frontend/src/hooks/useNovaQueries.ts` | Add `useMemorySearch`, `useMemoryHealth`, `useAddMemory`, `useDeleteMemoryFact` hooks |
| `frontend/src/app/settings/page.tsx` | Add Memory tab trigger and `MemoryTab` component |
| `docs/adr/016-memory-management-ui.md` | This document |

### API Endpoints (Already Exist)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/memory/search` | POST | Search facts by query |
| `/api/memory/add` | POST | Add new memory content |
| `/api/memory/health` | GET | Check system health |
| `/api/memory/facts/{uuid}` | DELETE | Delete specific fact |
| `/api/memory/episodes/{uuid}` | DELETE | Delete episode and related data |

### React Query Hooks

```typescript
// Search/list memories
useMemorySearch(query: string) → { results: MemoryResult[], count: number }

// Add new memory
useAddMemory() → mutation({ content: string, source_description: string })

// Delete single fact
useDeleteMemoryFact() → mutation(factUuid: string)

// Health check
useMemoryHealth() → { status: string, neo4j_connected: boolean }
```

## Consequences

### Positive
- Users can now see and manage what Nova "remembers"
- Easy cleanup of corrupted or test data
- Transparent AI - users understand what context is being used
- Follows existing UI patterns - consistent experience

### Negative
- Limited to list view - no graph visualization
- Fact-level deletion only - no entity/node management yet
- "Clear all" is destructive with no undo

### Future Considerations
- Graph visualization component (react-force-graph or similar)
- Entity/node browser (view nodes, not just edges/facts)
- Bulk import/export of memories
- Memory categories/partitions management
- Undo/restore deleted memories

## Related ADRs

- ADR-003: Graphiti Integration Architecture
- ADR-005: Settings Realization Work Packages

## Key Files

- `frontend/src/hooks/useNovaQueries.ts` - React Query hooks for memory operations
- `frontend/src/app/settings/page.tsx` - MemoryTab component
- `backend/memory/memory_functions.py` - Memory business logic
- `backend/api/memory_endpoints.py` - REST API endpoints
- `backend/models/memory.py` - Pydantic request/response models

---
*Last reviewed: 2025-01-08*
