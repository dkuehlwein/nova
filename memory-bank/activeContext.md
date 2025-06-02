# Nova AI Assistant: Active Context

## 🎯 **CURRENT FOCUS: PHASE 1 IMPLEMENTATION** ⭐

### **Architecture Complete** 🏗️
- **Technical Spec**: `docs/high-level-outline.md` contains full requirements
- **Memory Strategy**: OpenMemory MCP for relationships, separate from kanban workflow
- **Frontend Strategy**: Unified Nova frontend orchestrating MCP components via API-based isolation
- **Agent Pattern**: Permanent loop with single-task processing and multi-source context

### **🚀 IMMEDIATE NEXT STEPS**

#### **1. Hello World Unified Frontend + LangGraph Loop** 🎯
**Priority**: Highest - Prove orchestration concept first
- **Create**: `nova/frontend/` with Overview, Chat, Settings components
- **Integrate**: LangGraph permanent loop using existing 37 tools
- **Goal**: Validate unified interface coordinating MCP frontends

#### **2. Kanban System Enhancement** 📋
**After Step 1**: Rewrite for rich data structures
- **Enhanced Tasks**: Support #people, #projects, #chats, #artifacts
- **New States**: New/UserInput/NeedsReview/Waiting/InProgress/Done/Failed
- **API Integration**: Prepare for unified frontend embedding

#### **3. Memory Integration** 🧠
**Final Step**: OpenMemory MCP for context enrichment
- **Context Sources**: OpenMemory + kanban + project DB
- **Implementation**: Multi-source context aggregation pattern

## 📋 **KEY ARCHITECTURAL DECISIONS**

### **Memory Architecture** 🧠
- **OpenMemory MCP**: Cross-application context, relationships, preferences
- **Kanban MCP**: Task workflow state management
- **Integration**: Context enrichment without tight coupling

### **Frontend Modularity** 🖥️
- **Pattern**: API-based isolation for MCP frontend components
- **Structure**: Nova frontend embeds/orchestrates MCP frontends
- **Benefit**: Independent evolution with deep integration

### **Agent Loop Pattern** 🔄
```python
async def nova_main_loop():
    while True:
        tasks = await kanban_mcp.get_new_tasks()
        for task in tasks:
            context = await get_enriched_context(task)  # Multi-source
            result = await agent.process_task_with_tools(task, context)
            await kanban_mcp.update_task(task.id, result)
        await asyncio.sleep(5)
```

### **Technology Stack** ⚙️
- **Backend**: LangGraph + Python 3.13 + UV + FastMCP
- **Memory**: OpenMemory MCP (mem0.ai with Ollama support)
- **Documents**: MarkItDown MCP + API endpoints
- **Frontend**: React with modern business theme
- **Background**: Celery for email monitoring → task creation

## 🎉 **STABLE FOUNDATION** ✅

### **Production Ready**
- **37 Tools**: Gmail MCP (27) + Kanban MCP (10) fully operational
- **Agent Platform**: LangGraph + Gemini 2.5 Pro with continuous operation
- **Testing**: Comprehensive pytest suite with health monitoring
- **Docker**: Full orchestration with persistent storage

### **Implementation Benefits**
- **No Migration Risk**: PoC phase allows clean slate
- **Proven Foundation**: Building on stable 37-tool ecosystem
- **Clear Evolution**: Established FastMCP patterns

## ⚠️ **IMPLEMENTATION NOTES**

### **Race Condition Prevention**
- **Single Task**: Nova processes ONE task at a time
- **Clear States**: Explicit task status transitions
- **Memory Consistency**: Coordinated updates across systems

### **Context Sources for Tasks**
1. **OpenMemory**: People/project relationships, history
2. **Kanban**: Current tasks, related chats, artifacts
3. **Project DB**: Metadata, booking codes, formal data

**Status**: ✅ **READY FOR PHASE 1** - Architecture defined, foundation stable