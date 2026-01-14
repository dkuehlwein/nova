# ADR-003: Graphiti Integration Architecture

**Status**: Accepted - Implemented
**Date**: 2025-06
**Updated**: 2026-01-14

> **Implementation Notes**: GraphitiManager singleton implemented in `backend/memory/graphiti_manager.py`. Memory tools (`search_memory`, `add_memory`) available to agents. Neo4j integrated via docker-compose. Uses LiteLLM routing per ADR-011. Entity types aligned with schema.org vocabulary for semantic interoperability.

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
| Entity Types | `backend/memory/entity_types.py` | Schema.org-aligned entity types with extraction guidance |
| Pydantic Models | `backend/models/memory.py` | Request/response schemas |

### Entity Types (Schema.org Aligned)

Entity types follow [schema.org](https://schema.org/) vocabulary for semantic clarity. These are **suggested types** — Graphiti can dynamically create additional types as needed.

| Type | Schema.org | Key Attributes | Purpose |
|------|------------|----------------|---------|
| **Organization** | [schema:Organization](https://schema.org/Organization) | name, organization_type, industry, url | Companies, departments, teams |
| **Person** | [schema:Person](https://schema.org/Person) | name, email, job_title, telephone | Individuals in the knowledge graph |
| **Project** | [schema:Project](https://schema.org/Project) | name, status, start_date, end_date | Work items and engagements |
| **CourseInstance** | [schema:CourseInstance](https://schema.org/CourseInstance) | name, start_date, end_date, location, course_mode | Specific training/course offerings |
| **Event** | [schema:Event](https://schema.org/Event) | name, event_type, start_date, end_date, location | Meetings, conferences, workshops |
| **CreativeWork** | [schema:CreativeWork](https://schema.org/CreativeWork) | name, content_type, topics, audience, url | Presentations, demos, documents, videos |
| **Identifier** | Custom | value, identifier_type | Project codes, booking codes, cost centers |

### Relationship Types (Edge Constraints)

Edge types follow schema.org properties where possible. Defined in `NOVA_EDGE_TYPE_MAP`:

| Source → Target | Allowed Edge Types |
|-----------------|-------------------|
| Person → Organization | `WORKS_FOR`, `MEMBER_OF`, `AFFILIATED_WITH` |
| Person → Person | `REPORTS_TO`, `KNOWS`, `COLLEAGUE_OF` |
| CourseInstance → Person | `ATTENDEE`, `INSTRUCTOR` |
| Identifier → Project/CourseInstance | `IDENTIFIES` |
| CreativeWork → Person | `AUTHOR`, `CONTRIBUTOR` |
| CreativeWork → Organization | `ABOUT`, `PUBLISHER` |
| CreativeWork → Project | `PART_OF`, `DOCUMENTS` |

### Custom Extraction Instructions

`NOVA_EXTRACTION_INSTRUCTIONS` provides LLM guidance for entity extraction from emails and documents, including rules for identifying people, organizations, training courses, identifiers, and inferring relationships from context.

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
| `/api/system/system-health/neo4j` | GET | Check memory system health (unified endpoint) |

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
*Last reviewed: 2026-01-14*
