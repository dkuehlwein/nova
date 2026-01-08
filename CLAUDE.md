# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Development Commands

### Backend Development
```bash
# Install dependencies
cd backend && uv sync

# Run all tests
cd backend && uv run pytest ../tests

# Run unit tests only (fast, no DB required)
cd backend && uv run pytest ../tests/unit -v

# Run specific test
cd backend && uv run pytest ../tests/unit/api/test_api_endpoints.py -v

# Start chat agent service (port 8000)
cd backend && uv run python start_website.py

# Start core agent service (port 8001)
cd backend && uv run python start_core_agent.py

# Initialize database
cd backend && uv run python init_db.py
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

### Local LLM Setup
- Install LM Studio (or Ollama) on your Mac and load a model
- LM Studio runs on port 1234 by default (configure via `LLM_API_BASE_URL` env var)
- Models are discovered automatically by LiteLLM at startup

## Development Workflow

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
5. **MCP Servers** - External tool integrations (Google Workspace, Feature Requests)

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

### Code Smells to Flag

When working on the codebase, **proactively inform the user** if you notice any signs for bad code. e.g.:

1. **Large files (>500 lines)**: Component/module files exceeding 500 lines should be split into smaller, focused modules
2. **Mixed concerns**: Files containing multiple unrelated components or mixing UI with business logic
3. **Duplicate code**: Similar patterns repeated across multiple files that could be abstracted
4. **Deep nesting**: Components or functions with excessive nesting levels (>3-4 levels)
5. **God components**: React components doing too many things - should be split by responsibility

### Directory Structure & Responsibilities

```
backend/
├── agent/                  # AI Agent Core
│   ├── chat_agent.py      # LangGraph chat agent (streaming, tools)
│   ├── core_agent.py      # Autonomous task processor
│   └── prompts/           # Prompt files (.md) with hot-reload
├── api/                   # FastAPI Endpoints (single responsibility)
│   ├── api_endpoints.py   # Task/Person/Project CRUD
│   ├── chat_endpoints.py  # Chat/agent interaction
│   ├── config_endpoints.py # Configuration management
│   ├── mcp_endpoints.py   # MCP server management
│   ├── memory_endpoints.py # Memory system endpoints
│   ├── prompt_endpoints.py # Prompt management
│   ├── settings_endpoints.py # User settings
│   ├── system_endpoints.py # System status and health
│   └── websocket_endpoints.py # Real-time connections
├── database/              # Database layer
├── models/                # Pydantic models
├── email_processing/      # Email fetching and processing
├── memory/               # Graph memory system (Graphiti)
├── tasks/                # Celery background tasks
├── tools/                # LangChain tools for agents
├── utils/                # Shared utilities (service management, logging, etc.)
└── start_*.py            # Service entry points
```

### Testing Strategy

Nova uses a 3-tier test structure based on isolation level:

| Type | Directory | Requirements | Speed |
|------|-----------|--------------|-------|
| **Unit** | `tests/unit/` | None (isolated, all mocked) | Fast (ms) |
| **Integration** | `tests/integration/` | PostgreSQL, Redis, config files | Medium (s) |
| **End-to-End** | `tests/end2end/` | Full Docker stack | Slowest |

#### Running Tests
```bash
# Run all tests
cd backend && uv run pytest ../tests

# Run only fast unit tests (no DB required)
cd backend && uv run pytest ../tests/unit -v

# Run integration tests (requires DB/Redis)
cd backend && uv run pytest ../tests/integration -v

# Run specific test file
cd backend && uv run pytest ../tests/unit/utils/test_logging.py -v

# Skip slow tests
cd backend && uv run pytest ../tests -m "not slow"
```

#### Test Directory Structure
```
tests/
├── unit/           # Isolated tests (NOVA_SKIP_DB=1, all mocks)
│   ├── agent/
│   ├── api/
│   ├── input_hooks/
│   ├── memory/
│   ├── skills/
│   └── utils/
├── integration/    # Tests requiring real services (DB, Redis, config)
│   └── agent/
└── end2end/        # Full Docker stack tests
```

#### Notes
- **Async support**: All tests use pytest-asyncio
- **End2End tests**: Rebuild Docker images before running (changes only propagate after rebuild)

### Configuration Management
- **Environment variables**: Defined in `config.py` (never access directly)
- **Database connections**: 
  - `DATABASE_URL`: Plain PostgreSQL URL for LangChain checkpointer
  - `SQLALCHEMY_DATABASE_URL`: PostgreSQL+asyncpg URL for SQLAlchemy
  - `POSTGRES_HOST`: Database host (defaults to "localhost", Docker sets to "postgres")
- **MCP servers**: Configured in `configs/mcp_servers.yaml`
- **User profile**: `configs/user_profile.yaml`
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

### Common Patterns to Follow
1. Use existing service infrastructure (ServiceManager, db_manager, etc.)
2. Add structured logging with context to all operations
3. Follow single responsibility principle for API endpoints
4. Use async/await throughout for better performance
5. Leverage hot-reload for prompts and configuration changes

### Research Before Implementing
When encountering integration issues with external libraries:
1. **Check GitHub Issues first** - Search the library's issue tracker for similar problems before writing custom workarounds
2. **Test API capabilities directly** - Use `curl` or simple test scripts to verify what the external service actually supports (e.g., test LM Studio's `response_format` support directly)
3. **Understand the library's architecture** - Read the source code to understand where your override needs to hook in (e.g., graphiti-core's `_create_structured_completion` vs `_handle_structured_response`)
4. **Avoid hardcoded fixes** - If a hack is needed, make it configurable or at least document why the proper solution doesn't work

### Architecture Decision Records (ADRs)
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

## Testing Chat and Tool Calling

### Quick Chat Test
After starting Nova with `docker-compose up -d`, test the chat endpoint:

```bash
# Test basic chat with Phi-4 model
curl -X POST "http://localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello! What time is it?"}]}'
```

### Tool Calling Test
Test Nova's tool calling capabilities:

```bash
# Test tool calling (task creation and time lookup)
curl -X POST "http://localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Create a task called Test Task and tell me the current time"}]}'
```

### Update Model Settings
Change the LLM model via API:

```bash
# Update user settings to use Phi-4 model (default)
curl -X PATCH "http://localhost:8000/api/user-settings/" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_llm_model": "phi-4-Q4_K_M",
    "chat_llm_temperature": 0.1,
    "chat_llm_max_tokens": 2048
  }'

# Update user settings to use SmolLM3-3B model
curl -X PATCH "http://localhost:8000/api/user-settings/" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_llm_model": "smollm3-3b-Q4_K_M",
    "chat_llm_temperature": 0.6,
    "chat_llm_max_tokens": 2048
  }'
```

### Service Health Checks
Verify all services are running:

```bash
# Check Nova backend
curl http://localhost:8000/health

# Check LM Studio (or your local LLM)
curl http://localhost:1234/v1/models

# Check LiteLLM gateway
curl http://localhost:4000/health/readiness

# Check user settings
curl http://localhost:8000/api/user-settings/
```

### Common Issues
- **Tool calling fails**: Ensure your local LLM supports function calling (check model capabilities)

- **Settings not persisting**: Restart Nova backend after changing LLM settings
- Use uv run to run python code, uv run pytest for tests. The venv is in the backend folder!