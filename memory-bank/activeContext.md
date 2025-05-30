# Nova AI Assistant: Active Context

## Current Work Focus
- **Tasks.md MCP Server Fixes:** Fixed critical implementation issues with MCP SDK usage and routing
- **MCP Server Integration:** Successfully resolved connection and tool discovery problems 
- **Centralized MCP Configuration:** Dynamic server discovery and connection testing for both Gmail (8001) and Tasks (8002) servers

## Recent Changes
- **Fixed Tasks.md MCP Server Implementation:**
  - **Resolved `mcpServer.handleRequest is not a function` error**: Removed incorrect usage of non-existent handleRequest method
  - **Fixed MCP SDK Integration**: Properly implemented McpServer with correct tool definition syntax using `server.tool(name, paramSchema, handler)`
  - **Corrected Routing**: Fixed server to serve MCP directly at `/mcp` instead of mounting at `/api/mcp`
  - **Added Proper Tool Definitions**: Implemented `list_lanes`, `get_lane_tasks`, and `create_task` tools with correct schemas
  - **Improved Error Handling**: Added proper JSON-RPC error responses and better exception handling
- **Enhanced MCP Configuration (`config.py`):**
  - Added `TASKS_MCP_SERVER_*` configuration variables for port 8002
  - Created `active_mcp_servers` property for centralized server management
  - **Standardized URL Format**: All MCP servers use `host:port/mcp` pattern
- **Agent Integration (`agent.py`):**
  - Updated `MultiServerMCPClient` to loop through all configured servers
  - Added comprehensive logging for server discovery and connection status
  - Improved error handling for non-responding servers
- **Connection Testing (`test_mcp_connection.py`):**
  - Created test script for MCP server health checks and endpoint validation
  - Tests both `/health` endpoints and MCP protocol initialization

## Next Steps
- **Test Fixed Tasks Server Integration:** Verify tool discovery and functionality after implementation fixes
- **Run Full Agent Workflow:** Test end-to-end functionality with both Gmail and Tasks tools
- **Deploy and Monitor:** Ensure server stability and performance in production environment
- **Documentation Updates:** Document the fixes and proper MCP server implementation patterns

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
- **MCP SDK Proper Usage:** 
  - Use `McpServer` class with `server.tool(name, paramSchema, handler)` syntax
  - Never use `handleRequest` method (doesn't exist in SDK)
  - Transport setup requires proper configuration with StreamableHTTPServerTransport
- **Server Health Checks:** Not all MCP servers implement `/health` endpoints (404 expected)
- **Connection Testing:** Direct MCP protocol testing more reliable than health checks
- **Port Management:** Clear port allocation strategy prevents conflicts (8001-Gmail, 8002-Tasks)
- **Error Resolution:** SDK documentation is critical for proper implementation
- **Routing Standards:** MCP endpoints should be served directly at `/mcp`, not nested under `/api`
- Pydantic's `env_file` path is relative to the config file's location.
- `model_validator(mode='after')` is useful for Pydantic fields dependent on others.
- Verifying library APIs for resource management (e.g., `close()` methods) is crucial.
- Correct environment variable loading and precise method name matching between tool definitions and service implementations are vital for MCP server functionality.
- LangSmith provides valuable insights for debugging distributed agent systems. 