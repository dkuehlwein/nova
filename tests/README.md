# MCP Connection Tests

This directory contains pytest-based tests for verifying MCP (Model Context Protocol) server connectivity and functionality.

## Test Structure

The test suite is organized into several test classes:

- **`TestMCPServerHealth`**: Tests health endpoints of MCP servers
- **`TestMCPProtocol`**: Tests raw MCP JSON-RPC protocol compliance
- **`TestLangChainMCPClient`**: Tests integration using LangChain MCP client (same as agent.py)
- **`TestMCPToolExecution`**: Tests actual tool execution (marked as slow)

## Quick Start

### Using the Convenience Script (Recommended)

```bash
# From project root
./tests/test-mcp.sh fast

# Or from tests directory
cd tests
./test-mcp.sh fast
```

**Script Options:**
- `all` - Run all tests (default)
- `fast` - Run all tests except slow ones
- `health` - Run only health check tests
- `langchain` - Run only LangChain integration tests
- `protocol` - Run only raw MCP protocol tests
- `slow` - Run only slow tests
- `verbose` - Run all tests with detailed output

### Manual pytest Commands

#### From Backend Directory

```bash
cd backend
uv run pytest ../tests/test_mcp_connection.py -v
```

#### Run Specific Test Classes

```bash
# Health checks only
cd backend
uv run pytest ../tests/test_mcp_connection.py::TestMCPServerHealth -v

# LangChain integration tests only
cd backend
uv run pytest ../tests/test_mcp_connection.py::TestLangChainMCPClient -v
```

#### Run Without Slow Tests

```bash
cd backend
uv run pytest ../tests/test_mcp_connection.py -m "not slow" -v
```

#### Run with Detailed Output

```bash
cd backend
uv run pytest ../tests/test_mcp_connection.py -v -s
```

## Prerequisites

- MCP servers must be running (usually via `docker-compose up`)
- Backend dependencies must be installed (`uv install` in backend directory)
- pytest and pytest-asyncio are available as dev dependencies

## Configuration

The tests use fixtures to:
- Automatically skip if no MCP servers are configured
- Skip LangChain tests if `langchain-mcp-adapters` is not available
- Provide server configuration from settings

## Test Results

A successful test run should show:
- All servers responding to health checks
- MCP protocol compliance (may show expected 406 errors)
- Tool discovery and validation via LangChain client
- Basic tool execution (if not skipped with slow marker)

## Files in this Directory

- `test_mcp_connection.py` - Main pytest test suite
- `test-mcp.sh` - Convenience script for running tests
- `README.md` - This documentation

## Troubleshooting

1. **ModuleNotFoundError for src.nova.config**: Make sure you're running from the backend directory or using the convenience script
2. **No servers configured**: Check your `.env` file has MCP_SERVERS configured
3. **Connection refused**: Ensure MCP servers are running via Docker Compose
4. **Import errors**: Run `uv install` in the backend directory to install dependencies
5. **Script permission denied**: Run `chmod +x tests/test-mcp.sh` to make script executable

# Nova Core Agent Tests

## Integration Testing Approach

The core agent tests use integration testing with the main database for POC simplicity.

### Running Tests

```bash
# Run all core agent tests
python -m pytest tests/agent/test_core_agent.py -v

# Run specific test
python -m pytest tests/agent/test_core_agent.py::TestCoreAgentTaskProcessing::test_get_next_task_prioritizes_user_input_received -v
```

### How It Works

The tests:
- Use the main database (same as dev environment)
- Create test tasks/persons/projects with "Test" in names/emails
- Clean up only test data before/after each test
- Mock only the AI agent to avoid external API calls
- Test real database queries and task processing flow

This provides reliable integration testing while keeping it simple for POC phase. 