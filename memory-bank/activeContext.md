# Nova AI Assistant: Active Context

## Current Work Focus
- **Project Initialization:** Setting up the initial Memory Bank files and the base monorepo folder structure as per the defined architecture.
- Preparing for `uv` environment setup across Python projects.

## Recent Changes
- This is a new project. The Memory Bank and project structure are being established for the first time based on "Nova AI Assistant: Architecture, Structure, and Tools (v3)" document.

## Next Steps
- Complete the creation of the monorepo file structure.
- Populate placeholder files (e.g., `README.md`, `pyproject.toml`, `.gitignore`).
- Provide instructions for setting up `uv` for Python virtual environments and dependency management.
- Begin development of the Backend Core, starting with API an`d orchestrator setup.
- Develop initial MCP servers, starting with `tasks_md_mcp_server`.

## Active Decisions and Considerations
- **Package Manager:** `uv` confirmed for all Python projects.
- **Monorepo Structure:** Adopted as outlined.
- **Core Technologies:** Python, FastAPI, Celery, Redis, Gemini 2.5 Pro, LangChain/LlamaIndex, `fastmcp`, `tasks.md` (via library), `mem0` (via service/library), Docker.
- **Frontend Exploration:** Open Canvas is the primary candidate for chat and collaboration UI components.
- **MCP Architecture:** Independent, deployable MCP servers are a core architectural principle.
- **Backend Package Name:** `nova_backend` for clarity.

## Important Patterns and Preferences
- **Modularity:** Achieved through MCP servers and a well-defined monorepo structure.
- **AI-First:** Core agent and LLM integration are central to the product.
- **Async Operations:** Leveraging FastAPI and Celery for non-blocking operations.
- **Standardized Communication:** Using `fastmcp` for inter-service communication between the agent and MCP servers.

## Learnings and Project Insights
- N/A (Project just initiated). 