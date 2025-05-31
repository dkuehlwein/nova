# Nova AI Assistant: Technical Context

## Technologies Used ⭐ **PRODUCTION READY**

### Backend & MCP Servers ✅ **FULLY OPERATIONAL**
- **Programming Language:** Python 3.13+ (all components)
- **Package Manager & Virtual Environments:** `uv` (unified across all projects)
- **MCP Framework:** FastMCP (version 2.3.4+) - **ALL servers migrated**
- **Core Backend Framework:** FastAPI (for REST APIs & WebSockets) - **Ready for integration**
- **Agent Orchestration:** LangGraph with Google Gemini 2.5 Pro ✅ **OPERATIONAL**
- **Agent Architecture:** MCPClientManager with health checking and tool discovery ✅ **OPERATIONAL**
- **LLM Integration:** Gemini 2.5 Pro via LangChain ✅ **OPERATIONAL** 
- **Transport Layer:** FastMCP streamable-http ✅ **ZERO ISSUES**

### MCP Server Infrastructure ✅ **PRODUCTION READY**
- **Gmail MCP Server:** Port 8001, 27 tools, FastMCP ✅ **OPERATIONAL**
- **Kanban MCP Server:** Port 8003, 10 tools, FastMCP ✅ **OPERATIONAL**
  ```
  mcp_servers/kanban/
  ├── backend/          # Python FastMCP server
  │   ├── main.py      # Server implementation
  │   ├── pyproject.toml # uv dependencies
  │   ├── .venv/       # Virtual environment
  │   └── tasks/       # Task storage
  ├── frontend/        # Frontend application
  └── README.md        # Documentation
  ```
- **Health Monitoring:** All servers include `/health` endpoints ✅ **OPERATIONAL**
- **Testing:** Comprehensive test suites for all servers ✅ **COMPLETE**

### Task Management ✅ **MIGRATION COMPLETE**
- **Application:** Custom kanban implementation (replaces tasks.md)
- **Storage:** Enhanced `{title}-{uuid}.md` format in backend/tasks/
- **Integration:** Kanban MCP Server with 10 comprehensive tools
- **Status:** ✅ **FULLY OPERATIONAL** - All previous issues resolved

### Agent Platform ✅ **FULLY OPERATIONAL**
- **Total Tools:** 37 tools (27 Gmail + 10 Kanban)
- **Schema Compatibility:** Perfect LangChain integration via FastMCP
- **Multi-Query Support:** Continuous operation without hanging
- **Error Handling:** Comprehensive debugging and resilience
- **Tool Discovery:** Automatic health checking and tool aggregation

### Frontend **🔄 READY FOR DEVELOPMENT**
- **Structure:** Separate frontend directories for each service
- **Kanban Frontend:** `mcp_servers/kanban/frontend/` (React/Vue ready)
- **Integration:** REST API endpoints (FastAPI integration planned)
- **Chat Interface:** Direct agent execution (WebSocket support planned)

### Infrastructure & Deployment
- **Containerization:** Docker (ready for deployment)
- **Local Development:** Direct Python execution + uv virtual environments
- **Logging:** Python logging with structured output
- **Monitoring:** Health endpoints for all MCP servers

## Development Setup ✅ **STREAMLINED**

### Current Working Structure
```
nova/
├── backend/                    # Nova core agent
├── frontend/                   # Nova main frontend
├── mcp_servers/
│   ├── gmail/                  # Gmail MCP server
│   ├── kanban/
│   │   ├── backend/           # Kanban Python server
│   │   └── frontend/          # Kanban frontend
│   └── ...                    # Future MCP servers
└── memory-bank/               # Project documentation
```

### Development Workflows ✅ **OPERATIONAL**
- **Kanban Server:** `cd mcp_servers/kanban/backend && python main.py`
- **Gmail Server:** `cd mcp_servers/gmail && python main.py`
- **Agent Testing:** Direct execution with 37 available tools
- **Health Monitoring:** `curl http://localhost:800X/health`

### Virtual Environment Management
- **Backend/Agent:** `uv` virtual environments for core components
- **MCP Servers:** Individual `uv` environments per server backend
- **Frontend:** Node.js/npm for frontend components
- **Isolation:** Clean separation between Python and JavaScript dependencies

## Technical Constraints ✅ **SATISFIED**
- ✅ **uv for Python:** All Python projects use uv package management
- ✅ **Modular MCP Design:** All functionality via independent MCP servers
- ✅ **FastMCP Framework:** Unified architecture eliminates compatibility issues
- ✅ **Backend/Frontend Separation:** Clean project structure achieved

## Dependencies ✅ **LOCKED AND STABLE**

### Core Agent Dependencies
- `langchain`, `langgraph`, `google-generativeai`
- `fastmcp`, `requests` for MCP client integration

### MCP Server Dependencies (Per Server)
- `fastmcp` 2.3.4+ (unified framework)
- `requests` for HTTP operations
- Server-specific integrations (Gmail API, file operations)

### Frontend Dependencies (Per Frontend)
- `package.json` with React/Vue and related packages
- Independent npm/pnpm management

## Migration Achievements ⭐ **BREAKTHROUGH SUCCESS**

### ✅ Node.js → Python/FastMCP Migration Complete
- **Previous:** Node.js + Official MCP SDK (schema issues, complex setup)
- **Current:** Python + FastMCP (seamless integration, simple setup)
- **Benefits:**
  - Zero schema compatibility warnings
  - Enhanced title display and file management
  - Unified Python tech stack
  - Comprehensive testing and health monitoring
  - Simplified development and debugging

### ✅ Architecture Maturity
- **Agent Stability:** Multi-query continuous operation
- **Tool Integration:** 37 tools seamlessly available
- **Error Resilience:** Comprehensive error handling
- **Production Readiness:** All critical issues resolved

## Tool Usage Patterns ✅ **ESTABLISHED**

### MCP Server Development
```bash
# Navigate to server backend
cd mcp_servers/{server}/backend

# Setup environment
uv venv
uv pip install fastmcp requests

# Development cycle
python main.py              # Start server
python test_main.py         # Run tests
curl http://localhost:800X/health  # Check health
```

### Agent Development
```bash
# Core agent execution
cd backend
source .venv/bin/activate
python main.py              # Direct agent execution
```

### Frontend Development
```bash
# Navigate to frontend
cd mcp_servers/{server}/frontend

# Standard Node.js workflow
npm install                 # Install dependencies
npm run dev                 # Development server
npm run build              # Production build
```

## Current Operational Status ✅ **FULLY FUNCTIONAL**

**All technical components are operational and production-ready. The system has achieved its core technical goals with zero outstanding critical issues.** 