# ADR-003: Graphiti Integration Architecture

**Status**: Accepted - Implemented
**Date**: 2025-06
**Updated**: 2025-12-31

> **Implementation Notes**: GraphitiManager singleton implemented in `backend/memory/graphiti_manager.py`. Memory tools (`search_memory`, `add_memory`) available to agents. Neo4j integrated via docker-compose. Uses LiteLLM routing per ADR-011.

---

## Context

Nova needs a persistent memory layer to remember information across sessions. Without memory, the agent cannot:
- Recall information about people, projects, and relationships
- Leverage historical context for task performance
- Provide semantic search over accumulated knowledge

## Decision

Integrate Graphiti as Nova's knowledge graph memory system with:
- **Neo4j** as the graph database backend
- **Singleton pattern** for the Graphiti client (following `db_manager` pattern)
- **Direct integration** into backend (not MCP) for performance
- **LiteLLM routing** for LLM and embedding operations (per ADR-011)

## Architecture

```
┌─────────────────┐    ┌──────────────────────────────────┐    ┌─────────────────┐
│   Frontend      │    │        Nova Backend              │    │   Neo4j         │
│   (optional)    │────│                                  │────│   Database      │
│   Memory UI     │    │  API ──► Memory Functions        │    │                 │
└─────────────────┘    │              │                   │    └─────────────────┘
                       │       GraphitiManager            │
                       │       (singleton)                │
                       └──────────────────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| GraphitiManager | `backend/memory/graphiti_manager.py` | Singleton client lifecycle management |
| Memory Functions | `backend/memory/memory_functions.py` | Business logic for search/add operations |
| Memory Tools | `backend/tools/memory_tools.py` | LangChain tools for agent access |
| API Endpoints | `backend/api/memory_endpoints.py` | REST API for frontend |
| Entity Types | `backend/memory/entity_types.py` | Custom node types (Person, Project, Email, Artifact) |
| Pydantic Models | `backend/models/memory.py` | Request/response schemas |

### Entity Types

- **Person**: name, email, role, company
- **Project**: name, client, booking_code, status
- **Email**: subject, sender, recipients, date
- **Artifact**: name, type, path, description

### Relationship Types

- `WORKS_ON`, `MANAGES`, `CLIENT_OF` (Person ↔ Project)
- `SENT`, `RECEIVED` (Person ↔ Email)
- `CONTAINS`, `REFERENCES` (Email/Project ↔ Artifact)

## Integration Points

### Core Agent Context Gathering

The core agent automatically searches memory before processing tasks:
- Queries memory with task title, description, and tags
- Injects relevant historical context into task processing
- Stores task completion summaries in memory

### LLM Configuration

Memory operations use LiteLLM routing (ADR-011):
- **LLM Client**: OpenAI-compatible client via LiteLLM proxy
- **Embedder**: OpenAI-compatible embedder for semantic search
- **Model Selection**: Uses user settings for memory model choice

### Docker Infrastructure

Neo4j service added to docker-compose:
- Bolt protocol on port 7687
- Web interface on port 7474
- APOC plugin enabled
- Persistent volume for data

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/memory/search` | POST | Search knowledge graph |
| `/api/memory/add` | POST | Add information to graph |
| `/api/memory/episodes` | GET | List recent memory episodes |
| `/api/memory/health` | GET | Check memory system health |

## Consequences

### Positive

- Persistent memory across sessions
- Semantic search over knowledge
- Automatic relationship extraction
- Follows Nova's singleton patterns
- Graceful degradation when unavailable

### Negative

- Neo4j adds infrastructure complexity
- Graph queries can be slow for large datasets
- Requires LLM calls for entity extraction

### Risks

- **Neo4j unavailable**: System continues without memory context (graceful degradation)
- **Data consistency**: Graphiti handles deduplication and entity resolution
- **Performance**: Singleton pattern prevents connection overhead

## Configuration

Environment variables (add to `.env`):
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
MEMORY_GROUP_ID=nova
MEMORY_SEARCH_LIMIT=10
```

## Related ADRs

- **ADR-004**: Configuration management for memory settings
- **ADR-011**: LiteLLM routing for memory LLM operations

---
*Last reviewed: 2025-12-31*
