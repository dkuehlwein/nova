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
# Start dependencies (PostgreSQL, Redis, Neo4j)
docker-compose up -d postgres redis neo4j

# Full stack with containers
docker-compose up -d
```

## Architecture Overview

Nova is an AI-powered kanban task management system with a dual-agent architecture:

### Core Components
1. **Chat Agent Service** (`start_website.py:8000`) - User-facing chat interface and API endpoints
2. **Core Agent Service** (`start_core_agent.py:8001`) - Autonomous task processing loop
3. **Frontend** (`Next.js:3000`) - Web interface for task management
4. **MCP Servers** - External tool integrations (Google Workspace, Feature Requests)

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

### Configuration Management
- **Environment variables**: Defined in `config.py` (never access directly)
- **MCP servers**: Configured in `configs/mcp_servers.yaml`
- **User profile**: `configs/user_profile.yaml`
- **Prompts**: `backend/agent/prompts/*.md` with hot-reload

### Key Technologies
- **Backend**: FastAPI, LangChain, LangGraph, SQLAlchemy, Redis, PostgreSQL
- **Frontend**: Next.js, React, TailwindCSS, Radix UI
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