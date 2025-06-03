# Nova AI Assistant: Technical Context

## Technologies Used ⭐ **UPDATED ARCHITECTURE WITH CHAT AGENT**

### Backend & Core Tools ✅ **STREAMLINED ARCHITECTURE + CHAT**
- **Programming Language:** Python 3.13+ (all components)
- **Package Manager & Virtual Environments:** `uv` (unified across all projects)
- **Core Backend Framework:** FastAPI (for REST APIs & WebSockets) ✅ **OPERATIONAL**
- **Chat Agent:** LangGraph with Google Gemini 2.5 Pro ✅ **NEW - OPERATIONAL**
- **Agent Tools:** Native LangChain tools (replaced MCP for core functionality) ✅ **OPERATIONAL**
- **Tool Framework:** LangChain StructuredTool (direct Nova integration) ✅ **SIMPLIFIED**
- **Agent Orchestration:** LangGraph with conversation flow management ✅ **NEW**
- **LLM Integration:** Gemini 2.5 Pro via LangChain ✅ **OPERATIONAL** 
- **Chat Endpoints:** FastAPI with streaming support via SSE ✅ **NEW**
- **Testing Framework:** pytest + pytest-asyncio ✅ **COMPREHENSIVE COVERAGE**

### Database & Persistence ✅ **ROBUST WITH ASYNC FIXES**
- **Database:** PostgreSQL with Docker Compose
- **ORM:** SQLAlchemy 2.0+ with async support ✅ **GREENLET ISSUE FIXED**
- **Migrations:** Alembic for schema management
- **Connection:** asyncpg for PostgreSQL async driver
- **Session Management:** Async context managers for database sessions
- **Async Fixes:** Proper handling of relationships and lazy loading ✅ **CRITICAL FIX**

### Chat Agent Architecture ✅ **MAJOR NEW COMPONENT**

**🔥 LANGGRAPH CHAT AGENT IMPLEMENTATION:**
- **Framework:** LangGraph for state-based conversation management
- **Pattern:** Following agent-chat-ui best practices for compatibility
- **State Management:** MessagesState for conversation history
- **Tool Integration:** Seamless integration with 10 native LangChain tools
- **Streaming:** Real-time responses via Server-Sent Events (SSE)

### Chat Agent Implementation ✅ **TECHNICAL DETAILS**
```python
# Current LangGraph Implementation
from langgraph.graph import StateGraph
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode
from langchain_google_genai import ChatGoogleGenerativeAI

class Configuration(TypedDict):
    model_name: str
    temperature: float

# State-based conversation flow
workflow = StateGraph(MessagesState, config_schema=Configuration)
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode(tools))

# Conditional routing
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END,
    }
)

# Compile for execution
graph = workflow.compile()
```

### Chat API Endpoints ✅ **FASTAPI INTEGRATION**
```python
# Streaming chat endpoint
@router.post("/chat/stream")
async def stream_chat(request: ChatRequest):
    async def generate_response():
        async for chunk in graph.astream({"messages": messages}, config=config):
            for node_name, node_output in chunk.items():
                if "messages" in node_output:
                    for message in node_output["messages"]:
                        if isinstance(message, AIMessage):
                            yield f"data: {json.dumps(event)}\n\n"

# Non-streaming chat endpoint
@router.post("/chat/")
async def chat(request: ChatRequest):
    result = await graph.ainvoke({"messages": messages}, config=config)
    return ChatResponse(message=result["messages"][-1])
```

### Architectural Decision: LangChain Tools ✅ **MAJOR SIMPLIFICATION + CHAT**

**🔥 BREAKING CHANGE - MCP REMOVED FOR CORE FUNCTIONALITY:**
- **Previous:** FastMCP server for kanban tools (external protocol)
- **Current:** Native LangChain tools (direct Nova integration)
- **New Addition:** LangGraph chat agent for conversational interface ✅ **MAJOR FEATURE**
- **Rationale:** Kanban is core Nova functionality, not external integration
- **Benefits:**
  - **Simplified Stack:** No MCP protocol overhead
  - **Direct Integration:** Nova uses tools directly via LangChain
  - **Chat Integration:** Tools work seamlessly with conversational AI ✅ **NEW**
  - **Better Performance:** No serialization/protocol translation
  - **Easier Testing:** Direct function calls for testing
  - **Cleaner Code:** Tools are async Python functions

### Critical Technical Fixes ✅ **BREAKTHROUGH SOLUTIONS**

**🔥 TOOL PARAMETER FIX:**
- **Issue:** LangChain StructuredTool expected individual parameters, got Pydantic models
- **Error:** `TypeError: create_task_tool() got an unexpected keyword argument 'title'`
- **Root Cause:** Tool functions used `params: CreateTaskParams` instead of individual parameters
- **Solution:** Refactored all tool functions to accept individual parameters
- **Result:** All 10 tools now work seamlessly with LangGraph agent

```python
# Before (broken)
async def create_task_tool(params: CreateTaskParams) -> str:
    task = Task(title=params.title, description=params.description)

# After (working)
async def create_task_tool(
    title: str,
    description: str,
    due_date: str = None,
    tags: List[str] = None
) -> str:
    task = Task(title=title, description=description)
```

**🔥 SQLALCHEMY ASYNC SESSION FIX:**
- **Issue:** `MissingGreenlet` error when accessing `task.comments` outside session
- **Error:** `greenlet_spawn has not been called; can't call await_only() here`
- **Root Cause:** Lazy loading of relationships outside async session context
- **Solution:** Calculate counts within session, pass to formatter
- **Result:** All database operations work in LangGraph async context

```python
# Before (broken)
async def format_task_for_agent(task: Task) -> Dict:
    return {
        "comments_count": len(task.comments),  # Lazy loading issue
    }

# After (working)
async def format_task_for_agent(task: Task, comments_count: int = 0) -> Dict:
    return {
        "comments_count": comments_count,  # Passed from session
    }

# In tool functions
comments_count = await session.scalar(
    select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
)
formatted_task = await format_task_for_agent(task, comments_count or 0)
```

### Tool Architecture ✅ **NATIVE LANGCHAIN WITH CHAT INTEGRATION**
```python
# Current Implementation (fixed)
from langchain.tools import StructuredTool

async def create_task_tool(
    title: str,
    description: str,
    due_date: str = None,
    tags: List[str] = None,
    person_emails: List[str] = None,
    project_names: List[str] = None
) -> str:
    # Direct database operations with proper async handling
    async with db_manager.get_session() as session:
        # ... implementation with greenlet fix ...
        comments_count = await session.scalar(
            select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)
        )
        formatted_task = await format_task_for_agent(task, comments_count)
        return result

# Tool registration (simplified)
StructuredTool.from_function(
    func=create_task_tool,
    name="create_task",
    description="Create a new task with optional person and project relationships",
    coroutine=create_task_tool  # No args_schema needed
)
```

### Current Tool Inventory ✅ **10 NATIVE LANGCHAIN TOOLS (CHAT COMPATIBLE)**
```python
# Task Management (6 tools) - ALL WORKING WITH CHAT
- create_task: Create new tasks with relationships via conversation
- update_task: Update existing task fields and status through natural language
- get_tasks: Search and filter tasks conversationally
- get_task_by_id: Get detailed task information via chat
- add_task_comment: Add comments and update status through conversation
- get_pending_decisions: Get tasks needing user decisions via chat

# Person Management (2 tools) - CHAT INTEGRATED
- create_person: Create new person records via conversation
- get_persons: List all persons through chat

# Project Management (2 tools) - CHAT INTEGRATED
- create_project: Create new projects via conversation
- get_projects: List all projects through chat
```

### Backend Structure ✅ **CLEAN ARCHITECTURE + CHAT**
```
backend/
├── main.py                     # FastAPI server (REST API + Chat endpoints)
├── pyproject.toml              # LangChain + FastAPI + LangGraph dependencies
├── agent/
│   └── chat_agent.py           # LangGraph chat agent implementation ✅ NEW
├── api/
│   ├── api_endpoints.py        # REST endpoints for frontend
│   └── chat_endpoints.py       # Chat endpoints for conversational AI ✅ NEW
├── tools/
│   ├── __init__.py             # Tool aggregation
│   ├── task_tools.py           # Task management LangChain tools (fixed)
│   ├── person_tools.py         # Person management tools
│   ├── project_tools.py        # Project management tools
│   └── helpers.py              # Database utilities (async fixes)
├── models/
│   └── models.py               # SQLAlchemy models
├── database/
│   └── database.py             # Database session management
└── example_usage.py            # Tool usage demonstration
```

### External Services ✅ **MCP WHERE APPROPRIATE**
- **Gmail MCP Server:** Port 8001, 27 tools, FastMCP ✅ **OPERATIONAL**
  - **Rationale:** External service integration via MCP protocol
  - **Usage:** Email management for Nova agent
- **Future External Services:** Will use MCP for external integrations

### Testing Infrastructure ✅ **PROFESSIONAL GRADE**
- **Test Framework:** pytest with async support
- **Backend Tests:** Direct tool function testing
- **API Tests:** FastAPI endpoint testing (REST + Chat)
- **Database Tests:** PostgreSQL integration testing with async fixes
- **Tool Validation:** LangChain tool schema validation
- **Chat Testing:** LangGraph agent conversation flow testing ✅ **NEW**

## Development Setup ✅ **STREAMLINED + CHAT**

### Current Working Structure
```
nova/
├── backend/                    # Kanban backend (FastAPI + LangChain tools + Chat)
├── frontend/                   # Nova main frontend (chat UI ready)
├── tests/                      # Testing infrastructure
├── mcp_servers/
│   ├── gmail/                  # Gmail MCP server (external integration)
│   └── ...                     # Future external services
├── memory-bank/               # Project documentation
└── docker-compose.yml         # PostgreSQL + services
```

### Development Workflows ✅ **SIMPLIFIED + CHAT TESTING**
```bash
# Start database
docker-compose up postgres

# Start kanban backend with chat
cd backend
uv run main.py               # FastAPI server on :8000 (REST + Chat)

# Test tools directly
cd backend  
uv run example_usage.py      # Test LangChain tools

# Test chat agent
cd backend
python -c "from agent.chat_agent import test_graph; import asyncio; asyncio.run(test_graph())"

# Start frontend
cd frontend
npm run dev                  # Next.js on :3000 (ready for chat integration)

# External services (when needed)
cd mcp_servers/gmail
python main.py               # Gmail MCP on :8001
```

### Dependencies ✅ **UPDATED WITH CHAT**

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
    "langchain>=0.1.0",           # Native LangChain tools
    "langchain-core>=0.1.0",      # Core LangChain functionality
    "langchain-google-genai",     # Google Gemini integration ✅ NEW
    "langgraph>=0.1.0",          # LangGraph for chat agent ✅ NEW
]
```

#### Removed Dependencies
```toml
# REMOVED - No longer needed for core functionality
- "fastmcp>=2.3.4"  # Only for external services now
```

### Database Configuration ✅ **POSTGRESQL WITH ASYNC FIXES**
```bash
# Environment variables
DATABASE_URL=postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova_kanban
POSTGRES_DB=nova_kanban
POSTGRES_USER=nova
POSTGRES_PASSWORD=nova_dev_password

# Docker setup
docker-compose up postgres    # Start PostgreSQL
```

## Technical Constraints ✅ **UPDATED WITH CHAT**
- ✅ **uv for Python:** All Python projects use uv package management
- ✅ **LangChain for Core Tools:** Native tools for core Nova functionality
- ✅ **LangGraph for Chat:** Conversational AI with state management ✅ **NEW**
- ✅ **MCP for External Services:** MCP only for external integrations
- ✅ **FastAPI for REST + Chat:** Clean API for frontend integration
- ✅ **PostgreSQL for Persistence:** Robust database backend with async fixes
- ✅ **Backend/Frontend Separation:** Clean project structure maintained

## Chat Usage Patterns ✅ **NEW CONVERSATIONAL INTERFACE**

### Nova Chat Agent Usage
```python
# How users interact with Nova via chat
from backend.agent.chat_agent import graph

async def chat_workflow():
    # User sends message
    user_message = "Create a task called 'Review quarterly reports' with tags analysis and reports"
    
    # LangGraph processes conversation
    result = await graph.ainvoke({
        "messages": [HumanMessage(content=user_message)]
    })
    
    # Agent selects and executes tools, returns response
    return result["messages"][-1].content
    # "Task created successfully: Review quarterly reports"
```

### Tool Usage Patterns ✅ **UPDATED FOR CHAT**

### Nova Agent Tool Usage (via Chat)
```python
# How Nova uses native LangChain tools through conversation
from backend.tools import get_all_tools

async def nova_workflow():
    tools = get_all_tools()
    
    # LangGraph automatically selects and executes tools based on conversation
    # Example: User says "Create a task for reviewing reports"
    # LangGraph calls create_task_tool with:
    result = await create_task_tool(
        title="Review quarterly reports",
        description="Analyze Q4 performance metrics",
        tags=["reports", "analysis"]
    )
    
    return result
```

### Backend Development
```bash
# Backend tool development with chat
cd backend

# Setup environment
uv venv
uv sync                      # Install dependencies (including LangGraph)

# Development cycle
uv run main.py              # Start FastAPI server (REST + Chat)
uv run example_usage.py     # Test tools
pytest                      # Run tests

# Test chat agent
python -c "from agent.chat_agent import test_graph; import asyncio; asyncio.run(test_graph())"

# Database operations
alembic upgrade head        # Apply migrations
```

### Frontend API Integration
```typescript
// Frontend uses both REST API and Chat API
// REST API for direct operations
const response = await fetch('http://localhost:8000/api/tasks');
const tasks = await response.json();

// Chat API for conversational interface
const chatResponse = await fetch('http://localhost:8000/chat/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [{ role: 'user', content: 'Create a new task for testing' }]
  })
});

// Streaming chat for real-time responses
const eventSource = new EventSource('http://localhost:8000/chat/stream');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle streaming chat response
};
```

## Migration Achievements ⭐ **ARCHITECTURAL SIMPLIFICATION + CHAT**

### ✅ MCP → LangChain Tools Migration Complete
- **Previous:** FastMCP server for kanban functionality (protocol overhead)
- **Current:** Native LangChain tools (direct integration)
- **New Addition:** LangGraph chat agent for conversational interface ✅ **MAJOR FEATURE**
- **Benefits:**
  - **Simplified Architecture:** Removed unnecessary MCP layer
  - **Better Performance:** No protocol serialization overhead
  - **Direct Integration:** Nova uses tools directly via LangChain
  - **Chat Integration:** Tools work seamlessly with conversational AI ✅ **NEW**
  - **Easier Testing:** Direct function calls for testing
  - **Cleaner Dependencies:** Removed FastMCP for core functionality

### ✅ Dual-Purpose Backend + Chat
- **REST API:** FastAPI endpoints for frontend integration
- **Chat API:** LangGraph agent endpoints for conversational interface ✅ **NEW**
- **LangChain Tools:** Native tools for both REST and Chat integration
- **Clean Separation:** Frontend uses REST, Chat uses LangGraph, tools shared

### ✅ Maintained External Integration Pattern
- **Gmail:** Still uses MCP (appropriate for external service)
- **Future Services:** Will use MCP for external integrations
- **Core vs External:** Clear distinction in architecture

## API Endpoints ✅ **FRONTEND + CHAT INTEGRATION**

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

### Chat API for Conversational Interface ✅ **NEW**
```typescript
// Chat endpoints
POST /chat/ → ChatResponse (non-streaming)
POST /chat/stream → StreamingResponse (SSE)

// Chat request/response format
interface ChatRequest {
  messages: ChatMessage[]
  thread_id?: string
}

interface ChatResponse {
  message: ChatMessage
  thread_id: string
}
```

### LangChain Tools for Nova Agent (Both REST and Chat)
```python
# Direct tool access for Nova via both interfaces
tools = get_all_tools()
result = await tool.arun(parameters)
```

**Status**: ✅ **ARCHITECTURE SIMPLIFIED + CHAT INTEGRATION COMPLETE - LANGCHAIN TOOLS + LANGGRAPH OPERATIONAL** 