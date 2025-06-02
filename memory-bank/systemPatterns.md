# Nova AI Assistant: System Patterns

## Core Architecture

### FastMCP Foundation 🔌
**All Nova capabilities via standardized MCP protocol**
- **Gmail MCP** (Port 8002): 27 email/calendar tools
- **Kanban MCP** (Port 8001): 10 task management tools  
- **Future**: OpenMemory MCP, MarkItDown MCP

### **Unified Frontend Orchestration** 🎯
**Nova as primary orchestrator with embedded MCP frontends**
```
nova/frontend/
├── components/
│   ├── Overview.tsx        # Task dashboard
│   ├── Chat.tsx           # Agent communication  
│   ├── Settings.tsx       # System configuration
│   └── kanban/            # Embedded MCP frontend
├── api/
│   ├── agent.ts           # LangGraph loop
│   ├── mcp-proxy.ts       # MCP routing
│   └── context.ts         # Context aggregation
└── hooks/
    └── useAgentState.ts   # Real-time status
```

**Modularity**: API-based isolation enables independent MCP frontend evolution

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
**Component embedding for modularity**
```typescript
const NovaApp = () => (
  <Layout>
    <Overview />
    <Chat />
    <KanbanMCPFrontend />  {/* Embedded MCP frontend */}
    <Settings />
  </Layout>
);
```

## Current Status

### **Production Ready Infrastructure** ✅
- **Gmail MCP**: 27 tools, FastMCP, Port 8002
- **Kanban MCP**: 10 tools, FastMCP, Port 8001
- **Agent Core**: LangGraph + 37 tools + Gemini 2.5 Pro
- **Docker Environment**: Complete orchestration operational
- **Testing**: Comprehensive pytest suite with health monitoring

### **Technology Stack** ⚙️
- **Language**: Python 3.13+ unified across components
- **Package Manager**: `uv` for all dependency management
- **MCP Framework**: FastMCP for all server implementations
- **Agent**: LangGraph with Gemini 2.5 Pro
- **Transport**: Streamable-HTTP for MCP communications
- **Testing**: pytest with async support

**Architecture provides robust foundation for Nova's evolution while maintaining modularity and testability.** 