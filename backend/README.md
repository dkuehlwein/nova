# Nova Data Server

## Overview

This is Nova's core data server, containing the essential models and API for tasks, people, projects, and chats that power the Nova AI Assistant interface.

**Important**: This directory has been moved from `mcp_servers/kanban/backend-v2` for better organization. Nova's core concepts (tasks, people, projects) deserve to be at the root level as they're fundamental to the entire system.

# Nova Kanban MCP Server v2

A modern FastMCP server providing comprehensive kanban management for the Nova AI assistant. Built with FastAPI, PostgreSQL, and SQLAlchemy, offering both MCP protocol endpoints for the Nova agent and REST API endpoints for the frontend.

## Features

### Core Functionality
- **Task Management**: Full CRUD operations with rich metadata (status, priority, tags, relationships)
- **Person Management**: Contact information, roles, and current focus tracking
- **Project Management**: Client projects with booking codes and summaries
- **Chat Integration**: Conversation management with decision support
- **Artifact Management**: Document and link references with summaries

### Architecture
- **Dual Interface**: MCP protocol (`/mcp/`) for agent + REST API (`/api/`) for frontend
- **PostgreSQL Backend**: Robust relational database with proper schema
- **Modern Python**: Python 3.13+ with SQLAlchemy 2.0 and async support
- **FastMCP Framework**: Seamless integration with LangChain/LangGraph
- **Docker Ready**: Complete containerization with health monitoring

### Data Structures (from High-Level Outline)
- **Tasks**: Status workflow (New → User Input → Needs Review → In Progress → Done/Failed)
- **Persons**: Contact management with role descriptions and current focus
- **Projects**: Client projects with booking codes for billing
- **Chats**: Conversation history with decision support
- **Artifacts**: Email, document, and link references

## Quick Start

### Option 1: Docker Compose (Recommended)
```bash
cd mcp_servers/kanban/backend-v2
docker-compose up -d
```

This will start:
- PostgreSQL database on port 5432
- Kanban MCP server on port 8001

### Option 2: Local Development
```bash
cd mcp_servers/kanban/backend-v2

# Install dependencies
uv venv
uv pip install -e .

# Start PostgreSQL (requires Docker)
docker run -d --name postgres \
  -e POSTGRES_DB=nova_kanban \
  -e POSTGRES_USER=nova \
  -e POSTGRES_PASSWORD=nova_dev_password \
  -p 5432:5432 \
  postgres:16-alpine

# Run the server
uv run python main.py
```

### Sample Data
Populate the database with sample data for testing:
```bash
uv run python sample_data.py
```

## API Endpoints

### Overview Dashboard
- `GET /api/overview` - Dashboard statistics and recent activity
- `GET /api/pending-decisions` - Tasks needing user decisions

### Task Management
- `GET /api/tasks` - List tasks with filtering options
- `GET /api/tasks/by-status` - Tasks organized by status for kanban board
- `POST /api/tasks` - Create new task
- `GET /api/tasks/{id}` - Get specific task
- `PUT /api/tasks/{id}` - Update task
- `DELETE /api/tasks/{id}` - Delete task
- `GET /api/tasks/{id}/comments` - Get task comments
- `POST /api/tasks/{id}/comments` - Add task comment

### Entity Management
- `GET /api/persons` - List all persons
- `POST /api/persons` - Create new person
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create new project
- `GET /api/artifacts` - List all artifacts
- `POST /api/artifacts` - Create new artifact

### Chat Management
- `GET /api/chats` - List all conversations
- `POST /api/chats` - Create new conversation
- `GET /api/chats/{id}/messages` - Get chat messages
- `POST /api/chats/{id}/messages` - Add chat message

### System
- `GET /health` - Health check with database status
- `GET /docs` - Interactive API documentation

## MCP Tools (for Nova Agent)

### Task Operations
- `create_task` - Create task with relationships
- `update_task` - Update task properties and status
- `get_tasks` - Search and filter tasks
- `get_task_by_id` - Get detailed task information
- `add_task_comment` - Add comment and update status
- `get_pending_decisions` - Get tasks needing review

### Entity Management
- `create_person` - Add new person
- `get_persons` - List all persons
- `create_project` - Add new project
- `get_projects` - List all projects

## Data Models

### Task Status Workflow
```
New → User Input Received → Needs Review → In Progress → Done
  ↓                                          ↓
Failed ←─────────────────────────────────────┘
  ↓
Waiting (external factors)
```

### Task Model
```python
{
  "id": "uuid",
  "title": "string",
  "description": "text",
  "summary": "text (optional)",
  "status": "new|user_input_received|needs_review|waiting|in_progress|done|failed",
  "priority": "low|medium|high|urgent",
  "due_date": "datetime (optional)",
  "completed_at": "datetime (optional)",
  "tags": ["string"],
  "persons": [{"name": "string", "email": "string"}],
  "projects": [{"name": "string", "client": "string"}],
  "comments_count": "integer",
  "needs_decision": "boolean"
}
```

### Person Model
```python
{
  "id": "uuid",
  "name": "string",
  "email": "string (unique)",
  "role": "string (optional)",
  "description": "text (optional)",
  "current_focus": "text (optional)"
}
```

### Project Model
```python
{
  "id": "uuid",
  "name": "string",
  "client": "string",
  "booking_code": "string (optional)",
  "summary": "text (optional)"
}
```

## Configuration

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `MCP_SERVER_PORT` - Server port (default: 8001)
- `MCP_SERVER_HOST` - Server host (default: 0.0.0.0)
- `SQL_DEBUG` - Enable SQL query logging (default: false)
- `FORCE_MEMORY_CHECKPOINTER` - Force in-memory checkpointer even when PostgreSQL is available (default: false)

### Checkpointer Configuration

The chat agent uses LangGraph checkpointers to persist conversation state:

- **Production**: Uses PostgreSQL-based checkpointer when `DATABASE_URL` is configured
- **Development**: Can force in-memory checkpointer with `FORCE_MEMORY_CHECKPOINTER=true`
- **Fallback**: Automatically falls back to in-memory if PostgreSQL is unavailable

**Development/Debugging**: Set `FORCE_MEMORY_CHECKPOINTER=true` in your `.env` file to:
- Skip PostgreSQL connection setup complexity
- Use simple in-memory state for faster iteration
- Debug conversation flows without persistence overhead
- Test agent behavior in isolation

### Docker Compose Override
Create `docker-compose.override.yml` for custom settings:
```yaml
version: '3.8'
services:
  postgres:
    ports:
      - "5433:5432"  # Use different port
  kanban-mcp:
    environment:
      SQL_DEBUG: "true"
```

## Frontend Integration

The API is designed to work seamlessly with the Nova frontend:

### Overview Dashboard Data
```javascript
// Get dashboard stats
const overview = await fetch('/api/overview').then(r => r.json());
console.log(overview.pending_decisions); // Number of tasks needing decisions
console.log(overview.tasks_by_status);   // Count by status
console.log(overview.recent_activity);   // Recent changes
```

### Kanban Board Data
```javascript
// Get tasks organized by status
const tasksByStatus = await fetch('/api/tasks/by-status').then(r => r.json());
console.log(tasksByStatus.new);          // Tasks in NEW status
console.log(tasksByStatus.in_progress);  // Tasks in IN_PROGRESS status
```

### Chat Integration
```javascript
// Get conversations with decision indicators
const chats = await fetch('/api/chats').then(r => r.json());
const pendingChats = chats.filter(c => c.has_decision);
```

## Development

### Project Structure
```
backend-v2/
├── main.py              # FastMCP server entry point
├── models.py            # SQLAlchemy models
├── database.py          # Database configuration
├── api_endpoints.py     # REST API routes
├── mcp_tools.py         # MCP tools for agent
├── sample_data.py       # Sample data creation
├── pyproject.toml       # Dependencies
├── docker-compose.yml   # Container orchestration
├── Dockerfile           # Container build
└── README.md           # This file
```

### Adding New Features
1. **Add Model**: Update `models.py` with new SQLAlchemy model
2. **Add API**: Add REST endpoints in `api_endpoints.py`
3. **Add MCP Tool**: Add agent tool in `mcp_tools.py`
4. **Test**: Use sample data and `/docs` for testing

### Database Migration
The server automatically creates tables on startup. For schema changes:
1. Update models in `models.py`
2. Restart the server to apply changes
3. For production, consider using Alembic migrations

## Testing

### Health Check
```bash
curl http://localhost:8001/health
```

### API Testing
Visit http://localhost:8001/docs for interactive API documentation.

### MCP Testing
The server exposes standard MCP protocol endpoints at `/mcp/` for agent integration.

## Integration with Nova

This backend is designed to integrate with:
- **Nova Agent**: Via MCP protocol for task management
- **Nova Frontend**: Via REST API for user interface
- **Gmail MCP**: For email artifact management
- **Future MCPs**: OpenMemory, MarkItDown, etc.

The dual interface approach ensures optimal integration patterns while maintaining the modular MCP architecture.

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running
- Check `DATABASE_URL` environment variable
- Verify network connectivity between containers

### Port Conflicts
- Change ports in `docker-compose.yml`
- Update frontend API calls to match new ports

### Performance Issues
- Monitor database connections and queries
- Consider connection pooling for high load
- Use database indexes for frequently queried fields

For more detailed troubleshooting, check the application logs:
```bash
docker-compose logs kanban-mcp
```

## Testing the Server

### 1. Start the services

From the **project root directory**:

```bash
# Start PostgreSQL and the data server
docker-compose up postgres kanban-mcp
```

### 2. Test the basic endpoints

```bash
# Health check
curl http://localhost:8001/health

# Get overview stats  
curl http://localhost:8001/api/overview

# Get tasks by status (kanban board)
curl http://localhost:8001/api/tasks/by-status
```

### 3. Populate test data

From the **data directory**:

```bash
cd data
uv run python test_sample_data.py
```

### 4. Test with sample data

```bash
# Should now return real data
curl http://localhost:8001/api/overview
curl http://localhost:8001/api/tasks/by-status
curl http://localhost:8001/api/pending-decisions
``` 