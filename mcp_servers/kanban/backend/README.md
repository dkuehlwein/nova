# Kanban MCP Server - Backend

Python FastMCP server implementation for kanban task management.

## Quick Start

```bash
# Install dependencies
uv venv
uv pip install fastmcp requests

# Start server
source .venv/bin/activate
python main.py
```

## Development

### Running Tests
```bash
# Start server (in one terminal)
python main.py

# Run tests (in another terminal)
python test_main.py
```

### Server Configuration
- **Default Port**: 8003
- **Tasks Directory**: `./tasks/`
- **Health Endpoint**: `http://127.0.0.1:8003/health`
- **MCP Endpoint**: `http://127.0.0.1:8003/mcp/`

### Available Tools

**Lane Management:**
- `list_lanes()`, `create_lane()`, `delete_lane()`

**Task Management:**
- `list_all_tasks()`, `get_lane_tasks()`, `add_task()`
- `get_task()`, `update_task()`, `delete_task()`, `move_task()`

### File Structure
```
./tasks/
├── Backlog/
├── Todo/
├── In Progress/
└── Done/
```

Tasks stored as: `{title-slug}-{uuid}.md` 