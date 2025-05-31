# Nova AI Assistant: System Patterns

## System Architecture Diagram

```mermaid
graph TD
    subgraph User Interface (Frontend)
        UI_Kanban[Kanban View (Displays task content)]
        UI_Chat_Collaborate[Chat & Collaboration (Agent Interface)]
        UI_Kanban -- REST API --> B_API
        UI_Chat_Collaborate -- REST API / WebSockets --> B_API
    end

    subgraph Nova_Backend_Core [Nova Backend Core (Python, FastAPI, `uv`)]
        B_API[API Gateway (FastAPI) - Future]
        B_Agent[Core Agent Executor (Gemini LLM, LangGraph + MCPClientManager)]

        B_API -- Future: Handles HTTP/WS --> B_Agent
        B_Agent -- Direct agent execution --> B_Agent
        B_Agent -- Uses LLM --> Ext_LLM
        B_Agent -- Makes MCP Calls --> MCP_Network
    end

    subgraph MCP_Network [MCP Network (FastMCP Communication)]
        %% Unified FastMCP network for all MCP servers
        B_Agent --> MCP_Gmail_Server
        B_Agent --> MCP_Kanban_Server
        B_Agent --> MCP_Future_Servers["Future MCP Servers<br>(Mem0, Calendar, etc.)"]
    end

    subgraph MCP_Servers_Unified [Unified FastMCP Servers (Python, `uv`)]
        MCP_Gmail_Server["Gmail MCP Server<br>Port 8001 | 27 tools<br>FastMCP framework"]
        MCP_Kanban_Server["Kanban MCP Server<br>Port 8003 | 10 tools<br>FastMCP framework<br>**NEW: Backend/Frontend Structure**"]
        MCP_Future_Servers_Detail["Future servers following<br>FastMCP pattern"]
    end

    subgraph Data_Stores_External_Services [Data Stores & External Services]
        Data_TasksMD_Files["Task Markdown Files<br>{title}-{uuid}.md format<br>Lane-based organization<br>**NEW: In backend/tasks/**"]
        Data_Logs["Application Logs<br>(Python logging)"]
        Ext_LLM["LLM API (Gemini 2.5 Pro)"]
        Ext_Gmail_API["Gmail API<br>(OAuth integration)"]

        MCP_Kanban_Server -- Manages --> Data_TasksMD_Files
        MCP_Gmail_Server -- Integrates with --> Ext_Gmail_API
    end

    style Nova_Backend_Core fill:#ddeeff,stroke:#333,stroke-width:2px
    style MCP_Servers_Unified fill:#ddffdd,stroke:#333,stroke-width:2px
    style User_Interface fill:#ffffdd,stroke:#333,stroke-width:2px
```

## Key Technical Decisions ⭐ **UPDATED**
- **Primary Language & Package Management:** Python + `uv` for ALL backend and MCP server development 
- **MCP Framework:** **FastMCP** for ALL MCP servers (unified architecture)
- **Schema Compatibility:** Native LangChain integration via FastMCP (zero warnings)
- **Agent Framework:** LangGraph ReAct agent with Google Gemini LLM
- **MCP Client:** Custom MCPClientManager with health checking and tool discovery
- **File Management:** Enhanced `{title}-{uuid}.md` naming strategy for proper title display
- **Testing:** Comprehensive test coverage for all MCP operations
- **Health Monitoring:** Built-in `/health` endpoints for all MCP servers

## Design Patterns ⭐ **ENHANCED**
- **Monorepo:** All project code in single repository with organized structure
- **Model-Context-Protocol (MCP):** **Unified FastMCP pattern** for all tool services
- **Service-Oriented Architecture:** Independent MCP servers with FastMCP transport
- **Agent-Based System:** Central agent orchestrates 37 tools across multiple servers
- **Test-Driven Integration:** Comprehensive test suites validate all MCP operations
- **Health-First Architecture:** All services include health monitoring and status endpoints

## Component Relationships ⭐ **SIMPLIFIED**
- **Frontend** interacts with **Agent** via direct execution (FastAPI integration planned)
- **Agent** uses **MCPClientManager** for automatic server discovery and tool aggregation
- **MCPClientManager** performs health checks and manages connections to **FastMCP Servers**
- **FastMCP Servers** operate independently with streamable-http transport
- Each **MCP Server** manages its own data stores and external service integrations
- **Unified Python Stack:** All components use Python + `uv` for consistency

## MCP Server Specifications ⭐ **PRODUCTION READY**

### Gmail MCP Server (Port 8001) ✅
- **Framework:** FastMCP with streamable-http transport
- **Tools:** 27 comprehensive email management tools
- **Status:** Production ready, fully operational
- **Integration:** Perfect LangChain compatibility
- **Features:** Send, read, organize, search emails

### Kanban MCP Server (Port 8003) ✅ **NEW - RESTRUCTURED**
- **Framework:** FastMCP with streamable-http transport  
- **Tools:** 10 comprehensive task management tools
- **Status:** Production ready, replaces Node.js implementation
- **Structure:** **NEW** - Separated backend/frontend directories:
  ```
  mcp_servers/kanban/
  ├── backend/          # Python FastMCP server
  │   ├── main.py      # Server implementation
  │   ├── tasks/       # Task storage directory
  │   └── .venv/       # Virtual environment
  ├── frontend/        # Frontend application
  └── README.md        # Main documentation
  ```
- **Migration Benefits:**
  - ✅ Eliminated schema compatibility warnings
  - ✅ Fixed UUID display bug with enhanced filename strategy
  - ✅ Unified Python + uv tech stack
  - ✅ Comprehensive test coverage
  - ✅ Built-in health monitoring
  - ✅ **NEW**: Clean separation of backend/frontend concerns
- **Features:** Create, read, update, delete, move tasks across lanes

### Future MCP Servers (FastMCP Pattern)
- **Mem0 MCP Server:** Memory management and persistence
- **Calendar MCP Server:** Calendar integration and scheduling  
- **Document MCP Server:** File and document management
- **All following unified FastMCP architecture**

## Critical Implementation Paths ✅ **COMPLETED**
1. **✅ Agent Architecture:** LangGraph + MCPClientManager fully operational
2. **✅ MCP Framework:** FastMCP pattern established and proven
3. **✅ Gmail MCP Server:** 27 tools operational and production ready
4. **✅ Kanban MCP Server:** Migration complete, 10 tools operational, backend/frontend structured
5. **✅ Agent-MCP Integration:** 37 tools seamlessly integrated via MCPClientManager
6. **✅ Schema Compatibility:** Perfect LangChain integration achieved
7. **✅ Directory Structure:** Backend/frontend separation for kanban server
8. **🔄 FastAPI Integration:** Ready for implementation (all MCP issues resolved)

## Migration Achievements ⭐ **BREAKTHROUGH SUCCESS**

### Node.js → Python/FastMCP Migration
- **Challenge:** Complex Node.js MCP server with schema incompatibility
- **Solution:** Complete rewrite using FastMCP framework
- **Results:**
  - ✅ **Zero Schema Warnings:** Perfect LangChain integration
  - ✅ **Fixed UUID Display:** Enhanced `{title}-{uuid}.md` naming
  - ✅ **Unified Tech Stack:** All Python + uv environment
  - ✅ **Enhanced Testing:** Comprehensive test suite (17 test scenarios)
  - ✅ **Better Monitoring:** Built-in health endpoints
  - ✅ **Improved Tools:** 10 tools vs 8 previously

### System-Wide Benefits
- **Development Simplicity:** Single language across all components
- **Debugging Clarity:** Unified Python stack traces and error handling
- **Maintenance Efficiency:** Consistent patterns across all MCP servers
- **Schema Reliability:** Native FastMCP + LangChain compatibility
- **Operational Stability:** Comprehensive health monitoring and testing

## Current Operational Status ✅ **FULLY FUNCTIONAL**

### Health Dashboard
```
🟢 Gmail MCP Server     | Port 8001 | 27 tools | FastMCP | Status: OPERATIONAL
🟢 Kanban MCP Server    | Port 8003 | 10 tools | FastMCP | Status: OPERATIONAL ⭐
🟢 Nova Agent           | LangGraph | 37 tools | Gemini  | Status: OPERATIONAL
🟢 MCP Client Manager   | Health Discovery & Tool Aggregation  | Status: OPERATIONAL
```

### Technology Stack ⭐ **UNIFIED**
- **Language:** Python 3.13+ across all components
- **Package Manager:** `uv` for all dependency management
- **MCP Framework:** FastMCP for all server implementations
- **Agent Framework:** LangGraph with Gemini 2.5 Pro
- **Transport:** Streamable-HTTP for all MCP communications
- **Testing:** Python unittest with comprehensive coverage
- **Monitoring:** Built-in health endpoints for all services

## Architecture Evolution ⭐ **MATURITY ACHIEVED**

### Version 1.0: Mixed Architecture (Deprecated)
- Gmail: FastMCP (working)
- Tasks: Node.js + Official MCP SDK (issues)
- Schema warnings and compatibility problems

### Version 2.0: Unified FastMCP Architecture (Current) ✅
- **All servers:** FastMCP framework
- **Zero issues:** No schema warnings or compatibility problems  
- **Enhanced functionality:** Better tools and testing
- **Operational excellence:** Health monitoring and comprehensive testing
- **Ready for production:** All critical issues resolved 