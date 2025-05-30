# MCP Servers

This directory contains independent MCP (Model Context Protocol) Server Applications.
Each server is a self-contained Python application, managed with `uv` and designed to be Dockerized for production deployment.

## Available Servers

- **`fast_mcp_example/`**: Example MCP server demonstrating basic FastMCP functionality
- **`gmail/`**: Gmail integration server for email operations via Google API
- **`tasks_md_mcp_server/`**: Manages interactions with a `tasks.md` file *(planned)*
- **`mem0_mcp_server/`**: Wraps the `mem0` service for agent memory *(planned)*
- **`email_mcp_server/`**: General email functionalities (IMAP/SMTP/API) *(planned)*
- **`messaging_mcp_server/`**: User messaging with WebSocket communication *(planned)*

## Prerequisites

- **Python 3.13+**: Required for all MCP servers
- **uv**: Modern Python package manager ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
- **Docker & Docker Compose**: For containerized deployment *(recommended for production)*

## Local Development Setup

### Quick Start (Any Server)

1. **Navigate to server directory**:
   ```bash
   cd mcp_servers/<server_name>
   # Example: cd mcp_servers/gmail
   ```

2. **Create and activate virtual environment**:
   ```bash
   uv venv
   source .venv/bin/activate  # Linux/macOS
   # or
   .venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**:
   ```bash
   uv pip sync pyproject.toml
   # or alternatively
   uv pip install -e .
   ```

4. **Run the server**:
   ```bash
   python main.py
   ```

### Development Workflow

Each server follows the same structure:
```
server_name/
├── main.py              # Server entry point
├── pyproject.toml       # Dependencies and metadata
├── README.md            # Server-specific documentation
├── .python-version      # Python version specification
├── uv.lock             # Lock file for reproducible builds
└── ...                 # Additional server files
```

## Docker Deployment

### Individual Server (Development)

Each server can be containerized individually for testing:

```bash
# Navigate to server directory
cd mcp_servers/<server_name>

# Build Docker image
docker build -t nova-mcp-<server_name> .

# Run container
docker run -p 8000:8000 nova-mcp-<server_name>
```

### Docker Compose (Production)

For full system deployment, all MCP servers will be orchestrated with Docker Compose:

```bash
# From project root
docker-compose up -d
```

This will start:
- **Nova backend**: Main application server
- **MCP servers**: Each in its own container
- **Shared services**: Database, cache, etc.

#### Docker Compose Structure (Planned)
```yaml
services:
  nova-backend:
    build: ./backend
    ports:
      - "8000:8000"
    
  mcp-gmail:
    build: ./mcp_servers/gmail
    ports:
      - "8001:8000"
    
  mcp-tasks:
    build: ./mcp_servers/tasks_md_mcp_server
    ports:
      - "8002:8000"
    
  # Additional MCP servers...
```

## Configuration

### Environment Variables

Each MCP server may require specific environment variables:

- **Gmail Server**: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- **Email Server**: `SMTP_HOST`, `SMTP_PORT`, `EMAIL_PASSWORD`
- **Messaging Server**: `WEBSOCKET_URL`, `API_KEY`

Create `.env` files in each server directory or use Docker Compose environment configuration.

### MCP Client Configuration

To connect Nova backend to MCP servers, configure the MCP client in your main application:

```python
# Example configuration
MCP_SERVERS = {
    "gmail": "http://localhost:8001",
    "tasks": "http://localhost:8002",
    # ...
}
```

## Development Guidelines

### Adding a New MCP Server

1. **Create server directory**:
   ```bash
   mkdir mcp_servers/new_server_name
   cd mcp_servers/new_server_name
   ```

2. **Initialize with uv**:
   ```bash
   uv init
   echo "3.13" > .python-version
   ```

3. **Add FastMCP dependency**:
   ```bash
   uv add fastmcp
   ```

4. **Create basic structure**:
   - `main.py`: Server implementation
   - `README.md`: Server-specific documentation
   - `Dockerfile`: Container configuration

5. **Update this README**: Add server to the list above

### Testing

Each server should include comprehensive tests:

```bash
# Run tests for a specific server
cd mcp_servers/<server_name>
uv run pytest

# Run tests for all servers
# (from project root)
./scripts/test-mcp-servers.sh
```

## Monitoring and Logging

In Docker Compose deployment:
- **Logs**: `docker-compose logs mcp-<server_name>`
- **Health checks**: Each server exposes `/health` endpoint
- **Metrics**: Prometheus metrics at `/metrics` *(planned)*

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure each MCP server uses a unique port
2. **Python version**: All servers require Python 3.13+
3. **Dependencies**: Use `uv pip sync` to ensure consistent environments
4. **Docker builds**: Clear Docker cache if builds fail: `docker system prune`

### Getting Help

- Check server-specific README files for detailed configuration
- Review logs: `docker-compose logs <service_name>`
- Verify health endpoints: `curl http://localhost:800X/health`

## Roadmap

- [ ] Complete Docker Compose configuration
- [ ] Add health check endpoints to all servers
- [ ] Implement centralized logging
- [ ] Add Prometheus metrics
- [ ] Create deployment scripts
- [ ] Add CI/CD pipeline for server builds 