# Nova AI Assistant: Active Context

## Current Work Focus
- Refining the initial agent implementation (`backend/src/nova/agent/agent.py`).
- Setting up LangSmith for improved debugging and tracing of agent-MCP server interactions.

## Recent Changes
- **Basic Monorepo Structure Established:** Created the main directories (`frontend`, `backend`, `mcp_servers`, `docs`, `infrastructure`, `tests`, `scripts`, `memory-bank`) and placeholder files (e.g., `README.md`, `pyproject.toml`, `.gitignore`, `.editorconfig`).
- **Backend Configuration:** Implemented `backend/src/nova/config.py` to manage settings using Pydantic and an `.env` file.
- **Initial Agent Test:** Successfully ran a basic agent script (`backend/src/nova/agent/agent.py`) that initializes a Google LLM (Gemini) and connects to an example MCP server (GMail MCP Server).
- **Troubleshooting:**
    - Resolved Pydantic `Settings` configuration issues related to field validators and `.env` file path.
    - Corrected `NameError` for `GOOGLE_MODEL_NAME` by accessing it via the `settings` object.
    - Addressed `AttributeError` for `client.close()` by removing the call, as `MultiServerMCPClient` from `langchain_mcp_adapters` might not require/support it directly.
- **GMail MCP Server:** An example GMail MCP server was added and is being used for initial agent interaction tests.

## Next Steps
- **Integrate LangSmith:** Set up LangSmith for comprehensive tracing and debugging of the agent and its interactions with MCP servers.
- **Refine Agent-MCP Interaction:** Further develop and debug the communication flow between the core agent and the GMail MCP server (and other future MCPs).
- **Develop `tasks_md_mcp_server`:** Begin implementation of the `tasks_md_mcp_server` as the first custom MCP server.
- **Backend Core Development:** Continue building out the FastAPI application, Celery integration.
- **Documentation:** Start drafting ADRs for key decisions.

## Active Decisions and Considerations
- **Package Manager:** `uv` confirmed for all Python projects.
- **Monorepo Structure:** Adopted as outlined and largely implemented.
- **Core Technologies:** Python, FastAPI, Celery, Redis, Gemini 2.5 Pro, LangChain/LlamaIndex, `langchain-mcp-adapters` (for `MultiServerMCPClient`), Docker.
- **`.env` File Location:** Standardized to the project root (`nova-assistant/.env`).
- **Agent-MCP Client Cleanup:** Current understanding is that `MultiServerMCPClient` may not need an explicit top-level `close()` call; session management seems to be handled internally or per specific server session context.

## Important Patterns and Preferences
- **Modularity:** Achieved through MCP servers and a well-defined monorepo structure.
- **AI-First:** Core agent and LLM integration are central.
- **Configuration Management:** Pydantic `BaseSettings` with an `.env` file for managing application settings.
- **Iterative Development & Debugging:** Using print statements and planning to integrate LangSmith for better observability.

## Learnings and Project Insights
- Pydantic's `env_file` path is relative to the config file's location.
- `field_validator` vs. `model_validator`: `model_validator(mode='after')` is useful for fields that depend on other fields already processed from environment or defaults.
- Always verify library APIs for resource management (e.g., `close()` methods); direct calls might not exist on wrapper/aggregator clients.
- Environment variable loading is crucial; ensure `.env` files are correctly placed and referenced. 