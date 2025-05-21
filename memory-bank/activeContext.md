# Nova AI Assistant: Active Context

## Current Work Focus
- Continued refinement of agent-MCP interactions.
- Begin development of the `tasks_md_mcp_server`.

## Recent Changes
- **Basic Monorepo Structure Established:** Created the main directories (`frontend`, `backend`, `mcp_servers`, `docs`, `infrastructure`, `tests`, `scripts`, `memory-bank`) and placeholder files (e.g., `README.md`, `pyproject.toml`, `.gitignore`, `.editorconfig`).
- **Backend Configuration (`config.py`):**
    - Implemented Pydantic `Settings` for environment variable management.
    - Added LangSmith configuration variables (`USE_LANGSMITH`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`).
    - Corrected `.env` file path in `SettingsConfigDict` to `../../.env` for proper loading from the project root.
- **Agent Implementation (`agent.py`):**
    - Integrated LangSmith: Added logic to respect `USE_LANGSMITH` setting and configure necessary LangSmith environment variables (`LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`) at runtime if enabled.
    - Initial agent test script connects to Google LLM and GMail MCP server.
- **GMail MCP Server (`mcp_servers/gmail/main.py`):**
    - Debugged and resolved `AttributeError` related to tool definitions calling incorrectly named methods on the `GmailService` instance (e.g., `create_draft_email` tool now correctly calls `create_draft` service method). This was a widespread correction across multiple tool definitions.
- **Troubleshooting:**
    - Resolved Pydantic `Settings` configuration issues related to field validators and `.env` file path.
    - Corrected `NameError` for `GOOGLE_MODEL_NAME` by accessing it via the `settings` object.
    - Addressed `AttributeError` for `client.close()` by removing the call.
    - Successfully debugged `AttributeError` in GMail MCP server tool calls.

## Next Steps
- **Develop `tasks_md_mcp_server`:** Begin implementation of the `tasks_md_mcp_server` as the first custom MCP server.
- **Refine Agent-MCP Interaction:** Further develop and test the communication flow between the core agent and the GMail MCP server, utilizing LangSmith for observability.
- **Backend Core Development:** Continue building out the FastAPI application, Celery integration.
- **Documentation:** Start drafting ADRs for key decisions.

## Active Decisions and Considerations
- **Package Manager:** `uv` confirmed for all Python projects.
- **Monorepo Structure:** Adopted as outlined and largely implemented.
- **Core Technologies:** Python, FastAPI, Celery, Redis, Gemini 2.5 Pro, LangChain/LlamaIndex, `langchain-mcp-adapters` (for `MultiServerMCPClient`), `fastmcp`, Docker.
- **`.env` File Location:** Standardized to the project root (`nova-assistant/.env`).
- **LangSmith Usage:** Actively used for tracing and debugging agent-MCP interactions.

## Important Patterns and Preferences
- **Modularity:** Achieved through MCP servers and a well-defined monorepo structure.
- **AI-First:** Core agent and LLM integration are central.
- **Configuration Management:** Pydantic `BaseSettings` with an `.env` file.
- **Iterative Development & Debugging:** Utilizing LangSmith for observability.

## Learnings and Project Insights
- Pydantic\'s `env_file` path is relative to the config file\'s location.
- `model_validator(mode=\'after\')` is useful for Pydantic fields dependent on others.
- Verifying library APIs for resource management (e.g., `close()` methods) is crucial.
- Correct environment variable loading and precise method name matching between tool definitions and service implementations are vital for MCP server functionality.
- LangSmith provides valuable insights for debugging distributed agent systems. 