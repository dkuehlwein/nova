# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Development Commands

### Backend Development
```bash
# Install dependencies
cd backend && uv sync

# Run tests
cd backend && uv run pytest ../tests

# Run specific test
cd backend && uv run pytest ../tests/backend/test_specific.py -v

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
# Start dependencies (PostgreSQL, Redis, Neo4j, llama.cpp, LiteLLM)
docker-compose up -d postgres redis neo4j llamacpp litellm

# Full stack with containers (including frontend)
docker-compose up -d

# Frontend only (after backend is running)
docker-compose up -d nova-frontend
```

## Development Notes

### Service Restart Strategies
- Restart llama.cpp with docker compose up/down instead of restart. Otherwise changes will not be picked up

## Architecture Overview

Nova is an AI-powered kanban task management system with a dual-agent architecture:

### Core Components
1. **Chat Agent Service** (`start_website.py:8000`) - User-facing chat interface and API endpoints
2. **Core Agent Service** (`start_core_agent.py:8001`) - Autonomous task processing loop
3. **Frontend** (`Next.js:3000`) - Web interface for task management (containerized)
4. **Local LLM Infrastructure** - llama.cpp (`8080`) + LiteLLM gateway (`4000`) for local AI inference
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
- **Unit tests**: `tests/backend/test_*.py`
- **Integration tests**: `tests/integration/test_*.py`
- **Run from backend dir**: `uv run pytest ../tests`
- **Async support**: All tests use pytest-asyncio
- **End2End tests**: Rebuild the docker images before running the tests. Changes only propagate after rebuilding!

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
- **Local LLM**: llama.cpp (CUDA-accelerated) + LiteLLM (OpenAI-compatible gateway)
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

# Check llama.cpp
curl http://localhost:8080/health

# Check LiteLLM gateway
curl http://localhost:4000/health/readiness

# Check user settings
curl http://localhost:8000/api/user-settings/
```

### Common Issues
- **Tool calling fails**: Ensure llama.cpp has `--jinja` flag (required for function calling)

- **Settings not persisting**: Restart Nova backend after changing LLM settings
- Use uv run to run python code, uv run pytest for tests. The venv is in the backend folder!