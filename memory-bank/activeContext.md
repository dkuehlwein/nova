# Nova AI Assistant: Active Context

## Current Work Focus
- **Gmail MCP Server Fixed:** ✅ Successfully resolved FastMCP async/sync integration issues
- **MCP Server Integration:** Gmail server now responding correctly with 27 tools available
- **Centralized MCP Configuration:** Dynamic server discovery and connection testing for both Gmail (8001) and Tasks (8002) servers

## Recent Changes
- **Fixed Gmail MCP Server Critical Issues:**
  - **Resolved "Already running asyncio in this thread" error**: Removed nested asyncio.run() and used synchronous mcp.run() pattern
  - **Corrected FastMCP Structure**: Followed proper FastMCP pattern from working example with tool definitions in main block
  - **Fixed HTTP 406 Errors**: Updated test script to handle FastMCP's streamable-http transport with SSE responses and session management
  - **Working Server**: Gmail server now responds with 27 available tools through proper MCP protocol
- **Enhanced MCP Testing (`test_mcp_connection.py`):**
  - Added FastMCP-specific SSE headers: `Accept: application/json, text/event-stream`
  - Implemented proper session management with `Mcp-Session-Id` headers
  - Added multi-step protocol: initialize → notifications/initialized → tools/list
  - Added URL normalization (trailing slash requirement for FastMCP)
- **Previous Tasks.md MCP Server Fixes:**
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

## Next Steps
- **Test Gmail Agent Integration:** Verify tool discovery and functionality in full agent workflow
- **Run Full Agent Workflow:** Test end-to-end functionality with Gmail tools
- **Deploy and Monitor:** Ensure server stability and performance in production environment
- **Documentation Updates:** Document the FastMCP fixes and proper streamable-http implementation patterns

## Active Decisions and Considerations
- **Package Manager:** `uv` confirmed - all Python commands use `uv run python` pattern
- **MCP Server Ports:** Gmail=8001, Tasks=8002, future servers will increment
- **MCP URL Standard:** All servers MUST use `host:port/mcp` format (no variations)
- **Centralized Configuration:** All MCP servers managed through `settings.active_mcp_servers`
- **Transport Protocol:** Using `streamable_http` for all MCP servers (FastMCP-based)
- **Error Handling:** Graceful degradation when individual servers are unavailable

## Important Patterns and Preferences
- **Python Execution:** Always use `uv run python` instead of `python` or `python3`
- **MCP Server Testing:** Use `uv run python -m src.nova.agent.test_mcp_connection` for diagnostics
- **Modular Architecture:** Each MCP server runs independently on its own port
- **Configuration-Driven:** Server discovery and connection managed through Pydantic settings

## Learnings and Project Insights
- **FastMCP Pattern:** 
  - Never use `asyncio.run()` wrapper - FastMCP manages its own event loop
  - Use synchronous `mcp.run()` directly in `if __name__ == "__main__":` block
  - Tool definitions must be inside main block after service initialization
  - Streamable-http transport requires SSE-compatible headers and session management
- **FastMCP Session Protocol:**
  - URL must end with trailing slash (`/mcp/` not `/mcp`)
  - Requires `Accept: application/json, text/event-stream` header
  - Three-step initialization: initialize → notifications/initialized → actual requests
  - Session ID passed via `Mcp-Session-Id` header for subsequent requests
- **uv Integration:** Project uses `uv` for all Python package management and execution
- **MCP URL Standardization:** Consistent `/mcp` endpoint across all servers is critical
- **MCP SDK Proper Usage:** 
  - Use `McpServer` class with `server.tool(name, paramSchema, handler)` syntax (Tasks server pattern)
  - Use `FastMCP` class with `@mcp.tool()` decorators (Gmail server pattern)
  - Never use `handleRequest` method (doesn't exist in SDK)
  - Transport setup requires proper configuration with StreamableHTTPServerTransport
- **Server Health Checks:** Not all MCP servers implement `/health` endpoints (404 expected for FastMCP)
- **Connection Testing:** Direct MCP protocol testing more reliable than health checks
- **Port Management:** Clear port allocation strategy prevents conflicts (8001-Gmail, 8002-Tasks)
- **Error Resolution:** SDK documentation is critical for proper implementation
- **Routing Standards:** MCP endpoints should be served directly at `/mcp`, not nested under `/api`
- Pydantic's `env_file` path is relative to the config file's location.
- `model_validator(mode='after')` is useful for Pydantic fields dependent on others.
- Verifying library APIs for resource management (e.g., `close()` methods) is crucial.
- Correct environment variable loading and precise method name matching between tool definitions and service implementations are vital for MCP server functionality.
- LangSmith provides valuable insights for debugging distributed agent systems. 