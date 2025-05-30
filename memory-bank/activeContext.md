# Nova AI Assistant: Active Context

## Current Work Focus
- **MCP Server Integration:** Adding tasks.md MCP server (port 8002) to agent configuration
- **Centralized MCP Configuration:** Implemented dynamic server discovery and connection testing
- **Agent-MCP Debugging:** Testing connections and tool discovery across multiple MCP servers

## Recent Changes
- **Enhanced MCP Configuration (`config.py`):**
    - Added `TASKS_MCP_SERVER_*` configuration variables for port 8002
    - Created `active_mcp_servers` property for centralized server management
    - Added `enabled_mcp_servers` property for conditional logic
    - Implemented dynamic URL assembly for both Gmail (8001) and Tasks (8002) servers
    - **Standardized URL Format**: All MCP servers use `host:port/mcp` pattern
- **Agent Refactoring (`agent.py`):**
    - Updated `MultiServerMCPClient` to loop through all configured servers instead of hardcoded Gmail
    - Added comprehensive logging for server discovery and connection status
    - Improved error handling for when servers are not responding
- **Connection Testing (`test_mcp_connection.py`):**
    - Created standalone test script for MCP server health checks and endpoint validation
    - Tests both `/health` endpoints and MCP protocol initialization
    - Provides detailed diagnostics for troubleshooting server connectivity
- **Tasks.md MCP Server Integration:**
    - Identified routing issue: server mounts router at `/api` but needs direct `/mcp` endpoint
    - Discovered `mcpServer.handleRequest is not a function` error in Tasks.md implementation
    - Tasks.md server needs MCP protocol implementation fixes

## Next Steps
- **Fix Tasks.md MCP Implementation:** Resolve `handleRequest` method error in server
- **Standardize MCP Routing:** Ensure Tasks.md server serves MCP at `/mcp` not `/api/mcp`
- **Complete Tasks Server Integration:** Verify tool discovery and functionality after fixes
- **Test Full Agent Workflow:** Run end-to-end test with both Gmail and Tasks tools
- **Update Documentation:** Document the centralized MCP server management approach

## Active Decisions and Considerations
- **Package Manager:** `uv` confirmed - all Python commands use `uv run python` pattern
- **MCP Server Ports:** Gmail=8001, Tasks=8002, future servers will increment
- **MCP URL Standard:** All servers MUST use `host:port/mcp` format (no variations)
- **Centralized Configuration:** All MCP servers managed through `settings.active_mcp_servers`
- **Transport Protocol:** Using `streamable_http` for all MCP servers
- **Error Handling:** Graceful degradation when individual servers are unavailable

## Important Patterns and Preferences
- **Python Execution:** Always use `uv run python` instead of `python` or `python3`
- **MCP Server Testing:** Use `uv run python -m src.nova.agent.test_mcp_connection` for diagnostics
- **Modular Architecture:** Each MCP server runs independently on its own port
- **Configuration-Driven:** Server discovery and connection managed through Pydantic settings

## Learnings and Project Insights
- **uv Integration:** Project uses `uv` for all Python package management and execution
- **MCP URL Standardization:** Consistent `/mcp` endpoint across all servers is critical
- **Tasks.md MCP Issues:** Server routing at `/api/mcp` + missing `handleRequest` method
- **Server Health Checks:** Not all MCP servers implement `/health` endpoints (404 expected)
- **Connection Testing:** Direct MCP protocol testing more reliable than health checks
- **Port Management:** Clear port allocation strategy prevents conflicts (8001-Gmail, 8002-Tasks)
- **MCP Implementation:** Need to verify proper MCP SDK usage in third-party servers
- Pydantic\'s `env_file` path is relative to the config file\'s location.
- `model_validator(mode=\'after\')` is useful for Pydantic fields dependent on others.
- Verifying library APIs for resource management (e.g., `close()` methods) is crucial.
- Correct environment variable loading and precise method name matching between tool definitions and service implementations are vital for MCP server functionality.
- LangSmith provides valuable insights for debugging distributed agent systems. 