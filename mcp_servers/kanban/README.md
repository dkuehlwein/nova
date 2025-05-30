# Kanban MCP Server

A FastMCP server for kanban task management, providing a complete solution for managing tasks in lanes (columns) through the Model Context Protocol.

## Project Structure

```
mcp_servers/kanban/
├── backend/             # Python FastMCP server
│   ├── main.py         # Main server implementation
│   ├── test_main.py    # Comprehensive test suite
│   ├── pyproject.toml  # Python dependencies
│   ├── uv.lock         # Locked dependencies
│   ├── .venv/          # Virtual environment
│   ├── tasks/          # Task storage directory
│   └── test-tasks/     # Test task storage
├── frontend/           # React/Vue frontend application
│   ├── src/            # Frontend source code
│   ├── public/         # Static assets
│   ├── package.json    # Node.js dependencies
│   └── ...             # Other frontend files
└── README.md           # This file
```

## Features

- **Lane Management**: Create, list, and delete kanban lanes
- **Task Operations**: Add, update, move, and delete tasks 
- **Rich Task Data**: Support for titles, content, tags, and unique IDs
- **File-Based Storage**: Tasks stored as markdown files with title-UUID naming
- **Health Monitoring**: Built-in health check endpoint
- **MCP Compatible**: Full MCP protocol support for AI agent integration

## Backend Installation

### Prerequisites
- Python 3.13+
- `uv` package manager

### Setup

1. **Navigate to the backend directory:**
   ```bash
   cd mcp_servers/kanban/backend
   ```

2. **Create virtual environment:**
   ```bash
   uv venv
   ```

3. **Install dependencies:**
   ```bash
   uv pip install fastmcp requests
   ```

## Backend Usage

### Starting the Server

```bash
# Navigate to backend directory
cd mcp_servers/kanban/backend

# Activate virtual environment
source .venv/bin/activate

# Start server on default port 8003
python main.py

# Or specify custom options
python main.py --port 8004 --tasks-dir ./my-tasks
```

### Command Line Options

- `--port`: Server port (default: 8003)
- `--tasks-dir`: Tasks directory path (default: ./tasks)

### Health Check

The server provides a health check endpoint:
```bash
curl http://127.0.0.1:8003/health
```

## Testing

Run the comprehensive test suite:

```bash
# Navigate to backend directory
cd mcp_servers/kanban/backend

# Make sure server is running first
python main.py --port 8003

# In another terminal, run tests
source .venv/bin/activate
python test_main.py
```

The test suite covers:
- Health check verification
- MCP session initialization
- All tool operations (CRUD for lanes and tasks)
- Complete workflow testing
- Cleanup verification

## Available Tools

### Lane Management
- `list_lanes()`: Get all available lanes
- `create_lane(lane_name)`: Create a new lane
- `delete_lane(lane_name)`: Delete a lane and all its tasks

### Task Management
- `list_all_tasks()`: Get all tasks across all lanes
- `get_lane_tasks(lane)`: Get tasks from a specific lane
- `add_task(title, lane, content?, tags?)`: Add a new task
- `get_task(task_id, lane?)`: Get specific task details
- `update_task(task_id, content?, new_lane?, lane?)`: Update task content or move
- `delete_task(task_id, lane?)`: Delete a task
- `move_task(task_id, from_lane, to_lane)`: Move task between lanes

## File Structure

Tasks are stored as markdown files in the backend directory structure:

```
./backend/tasks/
├── Backlog/
│   ├── Fix-login-bug-a1b2c3d4-...md
│   └── Add-dark-mode-e5f6g7h8-...md
├── Todo/
│   └── Review-PR-123-i9j0k1l2-...md
└── Done/
    └── Setup-CI-CD-m3n4o5p6-...md
```

Each file contains:
- Filename: `{sanitized-title}-{uuid}.md`
- Content: Task description and any tags
- Tags: Hashtags within content (e.g., `#urgent #frontend`)

## Integration with Nova Agent

### Adding to Agent Configuration

Update your agent's MCP client configuration to include:

```python
# In your agent config
KANBAN_SERVER_URL = "http://127.0.0.1:8003/mcp/"
KANBAN_HEALTH_URL = "http://127.0.0.1:8003/health"
```

### Example Agent Usage

```python
# Create a task
agent_response = await agent.run("Create a new task 'Review documentation' in the Todo lane")

# List tasks  
agent_response = await agent.run("Show me all tasks in the In Progress lane")

# Move tasks
agent_response = await agent.run("Move the task about documentation review to Done")
```

## File Naming Strategy

The server uses a title-UUID naming strategy to solve the frontend display issues:

- **Filename**: `{title-slug}-{uuid}.md`
- **Title Extraction**: Removes UUID and converts dashes back to spaces
- **UUID Extraction**: Finds UUID pattern for operations
- **Benefits**: 
  - Human-readable filenames
  - Unique identification
  - Easy title extraction for frontend display

## API Endpoints

- **MCP Endpoint**: `http://127.0.0.1:8003/mcp/`
- **Health Check**: `http://127.0.0.1:8003/health`

## Troubleshooting

### Server Won't Start
- Check if port 8003 is available
- Verify Python 3.13+ and dependencies installed
- Check tasks directory permissions

### Agent Integration Issues  
- Verify server is running and accessible
- Check health endpoint returns 200 status
- Ensure MCP session initialization completes

### File Permission Issues
- Ensure write permissions to tasks directory
- Check file system supports the naming strategy

## Migration from Node.js Tasks Server

This Python server replaces the Node.js implementation and provides:

✅ **Fixed Issues:**
- No more schema compatibility warnings
- Eliminated UUID display bug (shows proper titles)
- Cleaner error handling and logging
- Consistent Python tech stack

✅ **Enhanced Features:**
- Comprehensive test suite
- Better error messages
- Health monitoring
- Simplified deployment

## Development

### Backend Development
```
mcp_servers/kanban/backend/
├── main.py              # Main server implementation
├── test_main.py         # Comprehensive test suite  
├── pyproject.toml       # Python dependencies
├── tasks/               # Task storage directory
└── .venv/               # Virtual environment
```

### Frontend Development
```
mcp_servers/kanban/frontend/
├── src/                 # Frontend source code
├── public/              # Static assets
├── package.json         # Node.js dependencies
└── node_modules/        # Installed packages
```

### Key Classes
- `KanbanService`: Core business logic for task/lane operations
- `FastMCP`: MCP protocol server framework
- Tool functions: MCP-exposed functions for agent interaction

## License

Part of the Nova AI Assistant project. 