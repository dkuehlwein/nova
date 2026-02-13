# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Coding Principles

### Think Before Coding
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
- Never guess at API field names, model names, or configuration values. Verify by testing or reading docs first.
- When encountering integration issues with external libraries, check GitHub Issues and test API capabilities directly before writing workarounds.

### Simplicity First
- Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

## Essential Development Commands

### Backend Development
```bash
cd backend && uv sync                              # Install dependencies
cd backend && uv run python start_website.py      # Chat agent service (port 8000)
cd backend && uv run python start_core_agent.py   # Core agent service (port 8001)
cd backend && uv run python init_db.py            # Initialize database
```

### Running Tests
```bash
cd backend && uv run pytest ../tests              # All tests
cd backend && uv run pytest ../tests/unit -v     # Unit tests only (fast, no DB)
cd backend && uv run pytest ../tests/integration -v  # Integration tests (requires DB/Redis)
cd backend && uv run pytest ../tests -m "not slow"   # Skip slow tests
```

### Frontend Development
```bash
# Install dependencies
cd frontend && npm install

# Development server
cd frontend && npm run dev

# Build for production
cd frontend && npm run build

# Lint
cd frontend && npm run lint
```

### Docker Services
```bash
# Start dependencies (PostgreSQL, Redis, Neo4j, LiteLLM)
docker-compose up -d postgres redis neo4j litellm

# Full stack with containers (including frontend)
docker-compose up -d

# Frontend only (after backend is running)
docker-compose up -d nova-frontend
```

## Development Notes

### Local Development vs Docker

**For quick debugging and code iteration:**
- Run backend services locally (see Backend Development commands above)
- Docker containers use baked-in code - `docker-compose restart` does NOT load new code
- To update code in Docker containers, you must rebuild: `docker-compose build nova-backend`
- **Best practice**: Ask user to run `start_website.py` in a terminal for faster feedback loops

**When to use Docker:**
- Testing the full stack end-to-end
- Testing container-specific issues (networking, volumes, env vars)
- Final verification before deployment

### Local LLM Setup
- Install LM Studio (or Ollama) on your Mac and load a model
- LM Studio runs on port 1234 by default (configure via `LLM_API_BASE_URL` env var)
- Models are discovered automatically by LiteLLM at startup

### Requirement gathering 
When asked to interview the user or gather requirements, use the AskUserQuestion tool (or equivalent interactive tool) instead of outputting a text-based list of questions.

### Bug Fix Process (Test-Driven)
When the task is to fix a bug:
1. **Reproduce first**: Write a failing test that reproduces the bug before writing any fix. Place the test in the appropriate test directory (`tests/unit/`, `tests/integration/`).
2. **Fix the bug**: Implement the fix, preferably using a subagent (Task tool) for the implementation work.
3. **Verify**: Run the test to confirm it passes. You are done only when the reproducing test is green.

This ensures every bug fix comes with a regression test and the fix is verified.


## Development Workflow

### Git Branch & Commit Conventions

**Branch naming:**
- `feature/<description>` - New features (e.g., `feature/user-auth`)
- `fix/<description>` - Bug fixes (e.g., `fix/memory-leak`)
- `refactor/<description>` - Code refactoring (e.g., `refactor/api-cleanup`)
- `docs/<description>` - Documentation only (e.g., `docs/api-reference`)
- `test/<description>` - Test additions/changes (e.g., `test/memory-unit-tests`)
- `chore/<description>` - Maintenance tasks (e.g., `chore/update-deps`)

**Commit messages** (Conventional Commits):
- `feat: <description>` - New feature
- `fix: <description>` - Bug fix
- `refactor: <description>` - Code refactoring (no behavior change)
- `docs: <description>` - Documentation only
- `test: <description>` - Adding/updating tests
- `chore: <description>` - Maintenance (deps, configs, etc.)

Optional scope for specificity: `feat(memory): Add edge type mapping`

### Implementation Plans

Store implementation plans in `docs/plans/` as Markdown files, named by ticket ID: `{TICKET-ID}-{slug}.md` (e.g., `NOV-123-login-crash-fix.md`).

**Why in-repo, not Linear:** Plans reference code paths, file names, and architectural details that belong next to the code. They give AI agents persistent context across sessions, are version-controlled, and are reviewable before implementation starts.

**What goes in a plan:**
- Link to Linear ticket
- Investigation/analysis notes
- Chosen approach and rationale
- Key files to modify
- Open questions or risks

**What does NOT go in a plan:** Anything that outlives the ticket. If a plan contains an architectural decision worth preserving, extract it into an ADR in `docs/adr/`.

**Lifecycle:** Plans are created during the planning phase (before implementation), live on the feature branch, and are committed with the work. After merge, they can be deleted or left as historical context — they're cheap.

### Feature Implementation Process
1. **Pre-work**: Review relevant Architecture Decision Records (ADRs) in `docs/adr/`.
2. **Implementation**:
    - Follow established patterns (ServiceManager, db_manager, etc).
    - Ensure tests are added or adapted to cover new changes.
3. **Post-work**:
    - Run relevant tests to verify changes (`uv run pytest ...`).
    - **Update ADRs** if architectural decisions changed.
    - Create new ADRs for significant new decisions.

## Architecture Overview

Nova is an AI-powered kanban task management system with a dual-agent architecture:

### Core Components
1. **Chat Agent Service** (`start_website.py:8000`) - User-facing chat interface and API endpoints
2. **Core Agent Service** (`start_core_agent.py:8001`) - Autonomous task processing loop
3. **Frontend** (`Next.js:3000`) - Web interface for task management (containerized)
4. **Local LLM Infrastructure** - External LLM API (e.g., LM Studio on `1234`) + LiteLLM gateway (`4000`)
5. **MCP Servers** - External tool integrations (Google Workspace, MS Graph, Feature Requests)

### Key Architectural Patterns

#### Service Lifecycle Management
- **Always use** `utils/service_manager.py` ServiceManager class for service startup/shutdown
- **Never create** custom startup logic in start scripts
- Pattern: `ServiceManager("service-name")` handles logging, Redis, prompt watching, cleanup

#### Database Operations
- **Always use** `database/database.py` db_manager
- **Never create** direct SQLAlchemy sessions
- Pattern: `async with db_manager.get_session() as session:`

#### Agent Creation
- **Always use** `agent/chat_agent.py` create_chat_agent() function
- **Never create** direct LangGraph agents
- Pattern: `await create_chat_agent(reload_tools=True)` for hot-reloading

#### Structured Logging
- **Always use** `utils/logging.py` structured logging with JSON output
- **Required fields**: timestamp, level, service, message, request_id
- Pattern: `logger.info("message", extra={"data": {...}})`

### Directory Structure & Responsibilities

```
backend/
├── agent/                  # AI Agent Core
│   ├── chat_agent.py      # LangGraph chat agent (streaming, tools)
│   ├── core_agent.py      # Autonomous task processor
│   └── prompts/           # Prompt files (.md) with hot-reload
├── api/                   # FastAPI Endpoints (single responsibility)
│   ├── api_endpoints.py   # Task/Person/Project CRUD
│   ├── api_key_endpoints.py # API key management
│   ├── chat_endpoints.py  # Chat/agent interaction
│   ├── config_endpoints.py # Configuration management
│   ├── hooks_endpoints.py # Input hooks management
│   ├── llm_endpoints.py   # LLM model management
│   ├── mcp_endpoints.py   # MCP server management
│   ├── memory_endpoints.py # Memory system endpoints
│   ├── prompt_endpoints.py # Prompt management
│   ├── settings_endpoints.py # User settings
│   ├── skill_endpoints.py # Skill management
│   ├── system_endpoints.py # System status and health
│   ├── tool_permissions_endpoints.py # Tool approval permissions
│   └── websocket_endpoints.py # Real-time connections
├── database/              # Database layer
├── models/                # Pydantic models
├── input_hooks/           # Input hooks (email, calendar processing)
├── memory/               # Graph memory system (Graphiti)
├── services/             # Service layer (health, chat, LLM, etc.)
├── skills/               # Pluggable skills system
├── tasks/                # Celery background tasks
├── tools/                # LangChain tools for agents
├── utils/                # Shared utilities (service management, logging, etc.)
└── start_*.py            # Service entry points
```

### Testing Strategy

Nova uses a 3-tier test structure (see "Running Tests" commands above):

| Type | Directory | Requirements | Speed |
|------|-----------|--------------|-------|
| **Unit** | `tests/unit/` | None (isolated, all mocked) | Fast |
| **Integration** | `tests/integration/` | PostgreSQL, Redis | Medium |
| **End-to-End** | `tests/end2end/` | Full Docker stack | Slow |
| **Evals** | `tests/evals/` | Eval framework | Varies |

Notes: All tests use pytest-asyncio. Rebuild Docker images before E2E tests.

**Cross-system changes require integration tests:**
- If a task touches multiple systems (e.g., API + database, agent + LiteLLM, tools + MCP), write integration tests that test real interactions — not just mocks.
- Unit tests with mocks verify logic in isolation; they do NOT verify that systems work together. Both are needed.
- Place integration tests in `tests/integration/`. Require real PostgreSQL/Redis via Docker.

**Mock tests can hide real bugs:**
- Never mock the module you're testing. Mock only external dependencies at the boundary.
- If you mock an import (e.g., `patch("module.some_dependency")`), you won't catch breakage when the real dependency changes signature, return type, or behavior.
- Prefer calling real code paths and only mocking at the outermost edges (DB, network, external APIs).
- If a mock-only test passes but the feature is broken, the test is worthless — add an integration test.

### Configuration Management
- **Environment variables**: Defined in `config.py` (never access directly)
- **Database connections**: 
  - `DATABASE_URL`: Plain PostgreSQL URL for LangChain checkpointer
  - `SQLALCHEMY_DATABASE_URL`: PostgreSQL+asyncpg URL for SQLAlchemy
  - `POSTGRES_HOST`: Database host (defaults to "localhost", Docker sets to "postgres")
- **MCP servers**: Configured in `configs/mcp_servers.yaml`
- **Tool permissions**: `configs/tool_permissions.yaml`
- **Input hooks**: `configs/input_hooks.yaml`
- **Prompts**: `backend/agent/prompts/*.md` with hot-reload

### Key Technologies
- **Backend**: FastAPI, LangChain, LangGraph, SQLAlchemy, Redis, PostgreSQL
- **Frontend**: Next.js, React, TailwindCSS, Radix UI
- **Local LLM**: LM Studio/Ollama (external) + LiteLLM (OpenAI-compatible gateway)
- **Memory**: Graphiti (Neo4j graph memory system)
- **Task Queue**: Celery with Redis broker
- **Tools**: MCP (Model Context Protocol) servers

### Development Notes
- **Python version**: 3.13+ required
- **Package manager**: uv (not pip)
- **MVP approach**: Single admin user, no authentication needed
- **Hot-reload**: Prompts and MCP configs reload automatically
- **Logging**: JSON structured logs in production, readable in development

### Integration Points
- **WebSocket**: Real-time updates via `utils/websocket_manager.py`
- **Redis Events**: Pub/sub for service coordination via `utils/redis_manager.py`
- **MCP Integration**: External tools via `mcp_client.py`
- **Memory System**: Graph-based memory via `memory/graphiti_manager.py`

### Architecture Decision Records (ADRs)

**ADR Format Requirements:**
- Header: Status, Date, Updated, Supersedes (if applicable)
- Implementation Notes block
- Sections: Context, Decision, Architecture, Key Components table, Consequences, Related ADRs
- Footer: Last reviewed date
- Target length: 100-200 lines, under 10KB
- No full code blocks (reference file paths instead)
- No emojis in documentation
- No work packages or implementation diaries
- Diagrams: simple ASCII, max 15-20 lines
- Status must be one of: Proposed, Accepted, Implemented, Partial, Superseded
- Update `docs/adr/README.md` index when adding a new ADR

Detailed architectural decisions are documented in `docs/adr/`. Key ADRs:
- **ADR-002**: Human-in-the-loop via `ask_user` tool and LangGraph interrupts
- **ADR-003**: Graphiti memory system with Neo4j (`memory/graphiti_manager.py`)
- **ADR-004**: 3-tier configuration with BaseConfigManager pattern
- **ADR-005**: Real-time infrastructure (hot-reload, Redis pub/sub, WebSocket)
- **ADR-007**: User context injection into system prompts
- **ADR-010**: Unified health monitoring with caching (`services/health_monitor.py`)
- **ADR-011**: LiteLLM-first architecture for all LLM operations
- **ADR-012**: Multi-input hooks for email/calendar (`input_hooks/`)
- **ADR-013**: Tool approval system for human oversight (`tools/tool_approval_helper.py`)
- **ADR-014**: Pluggable skills system (`skills/`)
- **ADR-015**: LiteLLM-MCP gateway migration
- **ADR-016**: Memory management UI
- **ADR-017**: Phoenix observability migration
- **ADR-018**: Service layer architecture (`services/`)
- **ADR-019**: Email thread consolidation

## Troubleshooting

When debugging, do not guess at the root cause. Start by reproducing the issue, then trace the actual code path. If your first hypothesis is wrong, acknowledge it and investigate systematically rather than trying another guess.

### Key Endpoints for Debugging
| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Backend health check |
| `GET /api/user-settings/` | Current user settings |
| `PATCH /api/user-settings/` | Update LLM model/settings |
| `POST /chat/stream` | Chat with streaming response |
| `GET /api/system/status` | Full system status |
| `GET :4000/health/readiness` | LiteLLM gateway health |

### Common Issues
- **Tool calling fails**: Ensure the LLM model supports function calling
- **Settings not persisting**: Restart Nova backend after changing LLM settings
- **Container code outdated**: Remember `docker-compose restart` doesn't reload code - rebuild with `docker-compose build`

