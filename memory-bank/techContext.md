# Nova AI Assistant: Technical Context

## Technologies Used ⭐ **UPDATED ARCHITECTURE**

### Backend & Core Tools ✅ **STREAMLINED ARCHITECTURE**
- **Programming Language:** Python 3.13+ (all components)
- **Package Manager & Virtual Environments:** `uv` (unified across all projects)
- **Core Backend Framework:** FastAPI (for REST APIs & WebSockets) ✅ **OPERATIONAL**
- **Agent Tools:** Native LangChain tools (replaced MCP for core functionality) ✅ **NEW**
- **Tool Framework:** LangChain StructuredTool (direct Nova integration) ✅ **SIMPLIFIED**
- **Agent Orchestration:** LangGraph with Google Gemini 2.5 Pro ✅ **OPERATIONAL**
- **LLM Integration:** Gemini 2.5 Pro via LangChain ✅ **OPERATIONAL** 
- **Testing Framework:** pytest + pytest-asyncio ✅ **COMPREHENSIVE COVERAGE**

### Database & Persistence ✅ **ROBUST**
- **Database:** PostgreSQL with Docker Compose
- **ORM:** SQLAlchemy 2.0+ with async support
- **Migrations:** Alembic for schema management
- **Connection:** asyncpg for PostgreSQL async driver
- **Session Management:** Async context managers for database sessions

### Architectural Decision: LangChain Tools ✅ **MAJOR SIMPLIFICATION**

**🔥 BREAKING CHANGE - MCP REMOVED FOR CORE FUNCTIONALITY:**
- **Previous:** FastMCP server for kanban tools (external protocol)
- **Current:** Native LangChain tools (direct Nova integration)
- **Rationale:** Kanban is core Nova functionality, not external integration
- **Benefits:**
  - **Simplified Stack:** No MCP protocol overhead
  - **Direct Integration:** Nova uses tools directly via LangChain
  - **Better Performance:** No serialization/protocol translation
  - **Easier Testing:** Direct function calls for testing
  - **Cleaner Code:** Tools are async Python functions

### Tool Architecture ✅ **NATIVE LANGCHAIN**
```python
# Current Implementation
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

class CreateTaskParams(BaseModel):
    title: str = Field(description="Task title")
    description: str = Field(description="Task description")

async def create_task_tool(params: CreateTaskParams) -> str:
    # Direct database operations
    async with db_manager.get_session() as session:
        # ... implementation ...
        return result

# Tool registration
StructuredTool.from_function(
    func=create_task_tool,
    name="create_task",
    description="Create a new task",
    args_schema=CreateTaskParams,
    coroutine=create_task_tool
)
```

### Current Tool Inventory ✅ **10 NATIVE LANGCHAIN TOOLS**
```python
# Task Management (6 tools)
- create_task: Create new tasks with relationships
- update_task: Update existing task fields and status
- get_tasks: Search and filter tasks
- get_task_by_id: Get detailed task information
- add_task_comment: Add comments and update status
- get_pending_decisions: Get tasks needing user decisions

# Person Management (2 tools)  
- create_person: Create new person records
- get_persons: List all persons

# Project Management (2 tools)
- create_project: Create new projects
- get_projects: List all projects
```

### Backend Structure ✅ **CLEAN ARCHITECTURE**
```
backend/
├── main.py              # FastAPI server (REST API only)
├── pyproject.toml       # LangChain + FastAPI dependencies
├── api/
│   └── api_endpoints.py # REST endpoints for frontend
├── tools/
│   ├── __init__.py      # Tool aggregation
│   ├── task_tools.py    # Task management LangChain tools
│   ├── person_tools.py  # Person management tools
│   ├── project_tools.py # Project management tools
│   └── helpers.py       # Database utilities
├── models/
│   └── models.py        # SQLAlchemy models
├── database/
│   └── database.py      # Database session management
└── example_usage.py     # Tool usage demonstration
```

### External Services ✅ **MCP WHERE APPROPRIATE**
- **Gmail MCP Server:** Port 8001, 27 tools, FastMCP ✅ **OPERATIONAL**
  - **Rationale:** External service integration via MCP protocol
  - **Usage:** Email management for Nova agent
- **Future External Services:** Will use MCP for external integrations

### Testing Infrastructure ✅ **PROFESSIONAL GRADE**
- **Test Framework:** pytest with async support
- **Backend Tests:** Direct tool function testing
- **API Tests:** FastAPI endpoint testing
- **Database Tests:** PostgreSQL integration testing
- **Tool Validation:** LangChain tool schema validation

## Development Setup ✅ **STREAMLINED**

### Current Working Structure
```
nova/
├── backend/                    # Kanban backend (FastAPI + LangChain tools)
├── frontend/                   # Nova main frontend
├── tests/                      # Testing infrastructure
├── mcp_servers/
│   ├── gmail/                  # Gmail MCP server (external integration)
│   └── ...                     # Future external services
├── memory-bank/               # Project documentation
└── docker-compose.yml         # PostgreSQL + services
```

### Development Workflows ✅ **SIMPLIFIED**
```bash
# Start database
docker-compose up postgres

# Start kanban backend
cd backend
uv run main.py               # FastAPI server on :8001

# Test tools directly
cd backend  
uv run example_usage.py      # Test LangChain tools

# Start frontend
cd frontend
npm run dev                  # Next.js on :3000

# External services (when needed)
cd mcp_servers/gmail
python main.py               # Gmail MCP on :8001
```

### Dependencies ✅ **UPDATED**

#### Backend Dependencies (pyproject.toml)
```toml
dependencies = [
    "fastapi>=0.104.1",
    "uvicorn>=0.24.0", 
    "sqlalchemy>=2.0.23",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic>=2.5.0",
    "python-multipart>=0.0.6",
    "python-dateutil>=2.8.2",
    "uuid6>=2023.5.2",
    "python-dotenv>=1.0.0",
    "langchain>=0.1.0",        # NEW: Native LangChain tools
    "langchain-core>=0.1.0",   # NEW: Core LangChain functionality
]
```

#### Removed Dependencies
```toml
# REMOVED - No longer needed for core functionality
- "fastmcp>=2.3.4"  # Only for external services now
```

### Database Configuration ✅ **POSTGRESQL**
```bash
# Environment variables
DATABASE_URL=postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova_kanban
POSTGRES_DB=nova_kanban
POSTGRES_USER=nova
POSTGRES_PASSWORD=nova_dev_password

# Docker setup
docker-compose up postgres    # Start PostgreSQL
```

## Technical Constraints ✅ **UPDATED**
- ✅ **uv for Python:** All Python projects use uv package management
- ✅ **LangChain for Core Tools:** Native tools for core Nova functionality
- ✅ **MCP for External Services:** MCP only for external integrations
- ✅ **FastAPI for REST:** Clean REST API for frontend integration
- ✅ **PostgreSQL for Persistence:** Robust database backend
- ✅ **Backend/Frontend Separation:** Clean project structure maintained

## Tool Usage Patterns ✅ **UPDATED**

### Nova Agent Tool Usage
```python
# How Nova will use native LangChain tools
from backend.tools import get_all_tools

async def nova_workflow():
    tools = get_all_tools()
    
    # Find specific tool
    create_task_tool = next(t for t in tools if t.name == "create_task")
    
    # Execute with parameters
    result = await create_task_tool.arun({
        "title": "Review quarterly reports",
        "description": "Analyze Q4 performance metrics",
        "tags": ["reports", "analysis"]
    })
    
    return result
```

### Backend Development
```bash
# Backend tool development
cd backend

# Setup environment
uv venv
uv sync                      # Install dependencies

# Development cycle
uv run main.py              # Start FastAPI server
uv run example_usage.py     # Test tools
pytest                      # Run tests

# Database operations
alembic upgrade head        # Apply migrations
```

### Frontend API Integration
```typescript
// Frontend will use REST API
const response = await fetch('http://localhost:8001/api/tasks');
const tasks = await response.json();

// No direct tool usage - goes through REST API
```

## Migration Achievements ⭐ **ARCHITECTURAL SIMPLIFICATION**

### ✅ MCP → LangChain Tools Migration Complete
- **Previous:** FastMCP server for kanban functionality (protocol overhead)
- **Current:** Native LangChain tools (direct integration)
- **Benefits:**
  - **Simplified Architecture:** Removed unnecessary MCP layer
  - **Better Performance:** No protocol serialization overhead
  - **Direct Integration:** Nova uses tools directly via LangChain
  - **Easier Testing:** Direct function calls for testing
  - **Cleaner Dependencies:** Removed FastMCP for core functionality

### ✅ Dual-Purpose Backend
- **REST API:** FastAPI endpoints for frontend integration
- **LangChain Tools:** Native tools for Nova agent integration
- **Clean Separation:** Frontend uses REST, Nova uses tools directly

### ✅ Maintained External Integration Pattern
- **Gmail:** Still uses MCP (appropriate for external service)
- **Future Services:** Will use MCP for external integrations
- **Core vs External:** Clear distinction in architecture

## API Endpoints ✅ **FRONTEND INTEGRATION**

### REST API for Frontend
```typescript
// Task Management
GET /api/overview → OverviewStats
GET /api/tasks/by-status → Record<TaskStatus, TaskResponse[]>
GET /api/tasks → TaskResponse[]
POST /api/tasks → TaskResponse
PUT /api/tasks/{id} → TaskResponse

// Entity Management
GET /api/persons → PersonResponse[]
POST /api/persons → PersonResponse
GET /api/projects → ProjectResponse[]
POST /api/projects → ProjectResponse

// Health & Status
GET /health → Health status
```

### LangChain Tools for Nova Agent
```python
# Direct tool access for Nova
tools = get_all_tools()
result = await tool.arun(parameters)
```

**Status**: ✅ **ARCHITECTURE SIMPLIFIED - LANGCHAIN TOOLS OPERATIONAL** 