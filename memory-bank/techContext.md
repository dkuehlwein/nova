# Nova AI Assistant: Technical Context

## Technologies Used

### Backend & MCP Servers
- **Programming Language:** Python (version TBD, latest stable recommended)
- **Package Manager & Virtual Environments:** `uv`
- **Core Backend Framework:** FastAPI (for REST APIs & WebSockets)
- **Asynchronous Task Processing:** Celery
- **Message Broker/Result Backend for Celery:** Redis (run in Docker)
- **Agent Orchestration/LLM Interaction:** LangChain / LlamaIndex (specific use TBD)
- **LLM:** Gemini 2.5 Pro (Experimental, fallbacks to be considered)
- **MCP Interaction Library:** `fastmcp` (version >2.0)

### Specific Tools/Services & Integration Libraries
- **Task Management:**
    - Application: `tasks.md` (by BaldissaraMatheus)
    - Library: `tasks-md` (Python library for interacting with `tasks.md` files)
    - Integration: Via a dedicated `Tasks.md MCP Server`.
- **Memory:**
    - Service: `mem0`
    - Library: `mem0` Python library/SDK
    - Integration: Via a dedicated `Mem0 MCP Server`.

### Frontend
- **Framework:** TBD (e.g., React, Vue)
- **Chat & Collaboration UI (Exploratory):** Open Canvas
    - Interaction: Frontend components connect to Nova Backend Core (API/WebSockets). Backend functionalities of Open Canvas might be exposed via an MCP server (post-MVP).

### Infrastructure & Deployment
- **Containerization:** Docker
- **Local Development Orchestration:** Docker Compose
- **Logging:**
    - Standard Python logging module, configured for structured output (JSON).
    - Centralized logging solution (e.g., ELK, Loki, CloudWatch, or LangSmith) for production/staging (TBD).

## Development Setup
- **Monorepo:** The project will be structured as a monorepo containing all services and applications.
- **Virtual Environments:** `uv` will be used to create and manage Python virtual environments for the backend and each MCP server project.
- **WSL with Ubuntu LTS 24:** The primary development environment.

## Technical Constraints
- Initial focus on `uv` for Python package management.
- Modular design using MCP servers is a strict requirement.
- Open Canvas integration is currently exploratory; decisions on its full adoption will be made based on investigation.

## Dependencies
- (To be filled as specific libraries and versions are chosen for each component.)

## Tool Usage Patterns
- `uv` for creating virtual environments (`uv venv`) and managing dependencies (`uv pip install`, `uv pip freeze > requirements.txt`, `uv pip sync requirements.txt`) within each Python project (`backend/`, `mcp_servers/*`).
- Docker for containerizing each service for consistent environments and deployment.
- Docker Compose to manage the multi-container setup for local development (Backend, MCP Servers, Redis).
- `scripts/setup_uv_envs.sh` will be used to automate the creation of all `uv` virtual environments. 