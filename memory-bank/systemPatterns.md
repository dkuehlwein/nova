# Nova AI Assistant: System Patterns

## Core Architecture

### FastMCP Foundation 🔌
**All Nova capabilities via standardized MCP protocol**
- **Gmail MCP** (Port 8002): 27 email/calendar tools
- **Kanban MCP** (Port 8001): 10 task management tools  
- **Future**: OpenMemory MCP, MarkItDown MCP

### **Clean Project Structure** 🗂️
**Organized by function with clear separation of concerns**
```
nova/
├── backend/                    # Core Nova agent and business logic
│   ├── api/                   # REST endpoints for frontend
│   ├── tools/                 # Tools for agent
│   ├── agent/                 # Agent endpoint
│   ├── models/                # Database schemas and data models
│   ├── database/              # Database management and connections
│   └── main.py                # Backend (APIs + Agent) entry point
├── tests/                     # Integration tests and sample data
│   ├── test_mcp_connection.py # MCP protocol tests
│   ├── test_sample_data.py   # Sample data generation
│   └── README.md             # Testing documentation
├── frontend/                  # Nova main UI
├── mcp_servers/              # Independent MCP servers
│   ├── gmail/                # Gmail MCP server
│   └── ...                   # Future MCP servers
└── memory-bank/              # Project documentation
```

**Key Improvements from Previous Structure:**
- **❌ Previous**: Messy `/data` directory with mixed concerns (tests, MCP definitions, business logic)
- **✅ Current**: Clean separation with `/backend` (organized by function) + `/tests` (dedicated testing)
- **Benefits**: Clear responsibility boundaries, easier navigation, better maintainability

### **Unified Frontend Orchestration** 🎯
**Nova as primary orchestrator with fully integrated components**
```
nova/frontend/
├── app/                    # Next.js 15.1 App Router
│   ├── page.tsx           # Overview dashboard (task counts, agent status)
│   ├── chat/page.tsx      # Agent communication (FULLY INTEGRATED)
│   ├── kanban/page.tsx    # Task management (FULLY INTEGRATED)
│   ├── settings/page.tsx  # System configuration
│   └── api/               # Optional internal API routes
├── components/
│   ├── ui/                # shadcn/ui components
│   ├── Overview.tsx       # Quick overview dashboard
│   ├── Chat.tsx          # Fully integrated agent interface
│   ├── KanbanBoard.tsx   # Fully integrated task management
│   ├── TaskCard.tsx      # Reusable task components
│   ├── Settings.tsx      # Configuration panel
│   └── shared/           # Shared UI components
├── hooks/
│   ├── useTasks.ts       # Kanban API integration
│   ├── useAgentStatus.ts # Agent status and communication
│   └── useNovaConfig.ts  # Configuration management
├── lib/
│   └── api.ts            # API client functions
└── styles/
    └── globals.css       # Tailwind + dark theme
```

### **Backend Organization by Function** ⚙️
**Clean functional separation within backend directory**
```
backend/
├── api/                    # REST endpoints for frontend
│   ├── routes/            # API route handlers
│   ├── middleware/        # Request/response middleware
│   └── validation/        # Input validation schemas
├── tools/                 # MCP tools for agent
│   ├── email_tools.py    # Email-related agent tools
│   ├── task_tools.py     # Task management tools
│   └── util_tools.py     # Utility and helper tools
├── models/                # Database schemas and data models
│   ├── task.py           # Task entity models
│   ├── person.py         # Person entity models
│   ├── project.py        # Project entity models
│   └── base.py           # Base model classes
├── database/              # Database management
│   ├── connection.py     # Database connection handling
│   ├── migrations/       # Schema migrations
│   └── config.py         # Database configuration
└── config/               # Application configuration
    ├── settings.py       # Environment and app settings
    └── logging.py        # Logging configuration
```

### **Frontend Architecture Decisions** ⚙️
**Tech Stack Finalized:**
- **Framework**: Next.js 15.1 + React 19 + TypeScript 5.x
- **UI/Styling**: Tailwind CSS + shadcn/ui (business/clean + dark theme) + Lucide React
- **State Management**: React built-in + API state (SWR/TanStack deferred until needed)
- **HTTP Layer**: fetch() API (direct to MCP servers)
- **Real-time**: Simple polling for overview dashboard

**API Integration Pattern:**
```typescript
// Direct connection to MCP servers (no proxy needed)
// Each MCP server exposes both /mcp/ (protocol) and /api/ (REST) endpoints

// lib/api.ts - Direct MCP server communication
export async function getTasks() {
  const response = await fetch('http://localhost:8001/api/cards');
  return response.json();
}

export async function getEmails() {
  const response = await fetch('http://localhost:8002/api/messages');
  return response.json();
}

// MCP Server Structure (existing pattern):
// localhost:8001/mcp/  → LangGraph/agent communication
// localhost:8001/api/  → Frontend REST API
// localhost:8001/health → Health check
```

**Integration Strategy (FULLY INTEGRATED):**
- **✅ Chat Component**: Native Nova component with direct LangGraph communication
- **✅ Kanban Component**: Native Nova component using kanban MCP API endpoints
- **Benefits**: Consistent architecture, seamless UX, shared state, unified theming, single codebase

**Modularity**: MCP servers remain independent backends, frontend unified for optimal UX

### **Memory Architecture** 🧠
**Three-tier context system**
```python
async def get_enriched_context(task):
    return {
        'memory': await openmemory_mcp.get_context(task.people, task.projects),
        'workflow': await kanban_mcp.get_related_data(task.id),
        'project_data': await project_db.get_metadata(task.projects)
    }
```

**Separation**: OpenMemory (relationships), Kanban (workflow), Project DB (metadata)

### **Agent Loop Pattern** 🔄
**Permanent processing with context enrichment**
```python
class NovaAgent:
    async def main_loop(self):
        while True:
            task = await self.kanban.get_next_task()
            if task:
                context = await self.get_enriched_context(task)
                result = await self.process_with_tools(task, context)
                await self.update_all_systems(task, result)
            await asyncio.sleep(5)
```

**Key Principles**: Sequential processing, context enrichment, state coordination

### **Enhanced Task Processing** 📋
**Rich metadata beyond simple markdown**
```python
@dataclass
class Task:
    id: str
    status: TaskStatus  # New/UserInput/NeedsReview/Waiting/InProgress/Done/Failed
    title: str
    description: str
    comments: List[Comment]
    summary: str
    entities: TaskEntities  # people, projects, chats, artifacts
```

### **Celery Integration** 🔗
**External triggers without agent coupling**
```python
@app.task
def process_new_email(email_data):
    task = create_kanban_task(
        title=f"Process email from {email_data.sender}",
        entities=extract_entities(email_data)
    )
    # Agent picks up in next loop iteration
```

## Service Patterns

### **Docker Orchestration** 🐳
- **Multi-Service**: 4 containers with networking
- **Persistent Storage**: Task data survives restarts
- **Health Monitoring**: Automated status checks
- **Development**: Hot reloading, volume mounts

### **Testing Infrastructure** 🧪
- **Health Checks**: Service availability monitoring
- **Protocol Testing**: MCP JSON-RPC compliance
- **Integration**: LangChain MCP client validation
- **Pytest Structure**: Professional async test organization

### **Configuration Management** ⚙️
- **Docker**: Service discovery via container names
- **Development**: Localhost with configurable ports
- **Environment Variables**: Runtime configuration
- **Security**: `.env` files for sensitive data

### **Error Handling** ⚠️
**Graceful degradation with clear user communication**
```python
async def process_task_safely(task):
    try:
        context = await get_enriched_context(task)
        result = await agent.process(task, context)
        await update_systems(task, result)
    except Exception as e:
        await task.update_status("Failed", f"Error: {e}")
```

### **Frontend Integration** 🖥️
**Fully integrated component architecture**
```typescript
const NovaApp = () => (
  <Layout>
    <Overview />      {/* Task counts, agent status */}
    <Chat />          {/* Fully integrated agent communication */}
    <KanbanBoard />   {/* Fully integrated task management */}
    <Settings />      {/* System configuration */}
  </Layout>
);
```

**Shared State Management:**
```typescript
// Unified hooks for consistent state across components
const useTasks = () => { /* Direct kanban API integration */ }
const useAgentStatus = () => { /* Agent communication status */ }
const useNovaConfig = () => { /* System configuration */ }
```

## Current Status

### **Production Ready Infrastructure** ✅
- **Gmail MCP**: 27 tools, FastMCP, Port 8002 (`/mcp/` + `/api/`)
- **Kanban MCP**: 10 tools, FastMCP, Port 8001 (`/mcp/` + `/api/`)
- **Agent Core**: LangGraph + 37 tools + Gemini 2.5 Pro
- **Docker Environment**: Complete orchestration operational
- **Testing**: Comprehensive pytest suite with health monitoring

### **Frontend Architecture Defined** 🎯
- **Tech Stack**: Next.js 15.1 + React 19 + TypeScript + Tailwind + shadcn/ui
- **Integration Pattern**: Direct fetch() to MCP server `/api/` endpoints
- **State Strategy**: React built-in + deferred API state management
- **Chat Strategy**: ✅ Fully integrated Nova component (decision finalized)
- **Modularity**: Clean separation via direct API connections

### **Technology Stack** ⚙️
- **Language**: Python 3.13+ unified across components
- **Package Manager**: `uv` for all dependency management
- **MCP Framework**: FastMCP for all server implementations
- **Agent**: LangGraph with Gemini 2.5 Pro
- **Transport**: Streamable-HTTP for MCP communications
- **Frontend**: Next.js 15.1 + React 19 + TypeScript + Tailwind CSS
- **Testing**: pytest with async support

**Architecture provides robust foundation for Nova's evolution while maintaining modularity and testability.** 