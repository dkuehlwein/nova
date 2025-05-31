# MCP Servers Docker Setup

This Docker setup allows you to run all your MCP servers with a single command, eliminating the need for multiple terminal windows.

## Quick Start

### Start All Services
```bash
./scripts/mcp-docker.sh start
```

### Stop All Services
```bash
./scripts/mcp-docker.sh stop
```

### Check Status
```bash
./scripts/mcp-docker.sh status
```

## Services & Ports

| Service | Port | URL | Description |
|---------|------|-----|-------------|
| Kanban MCP | 8001 | http://localhost:8001 | Task management MCP server |
| Gmail MCP | 8002 | http://localhost:8002 | Gmail integration MCP server |
| Example MCP | 8003 | http://localhost:8003 | Example FastMCP server |
| Kanban Frontend | 3000 | http://localhost:3000 | Kanban web interface |

## Available Commands

```bash
./scripts/mcp-docker.sh [COMMAND]
```

### Commands:
- `start` - Start all MCP servers
- `stop` - Stop all MCP servers  
- `restart` - Restart all MCP servers
- `status` - Show status of all services
- `logs` - Show logs for all services
- `logs <service>` - Show logs for a specific service
- `build` - Build all Docker images
- `clean` - Stop and remove all containers and images
- `health` - Check health of all services
- `help` - Show help message

## Examples

### Start everything:
```bash
./scripts/mcp-docker.sh start
```

### Watch logs for all services:
```bash
./scripts/mcp-docker.sh logs
```

### Watch logs for just the kanban server:
```bash
./scripts/mcp-docker.sh logs kanban-mcp
```

### Check if all services are healthy:
```bash
./scripts/mcp-docker.sh health
```

### Rebuild everything from scratch:
```bash
./scripts/mcp-docker.sh build
```

## Configuration

### Environment Variables

Each service can be configured through environment variables in the `docker-compose.yml` file:

- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)

### Volumes

- `tasks/` directory is mounted for the kanban server to persist task data
- Gmail credentials are mounted read-only

## Development

### Using with Cursor/VS Code

After starting the services with Docker, you can configure your Claude Desktop or other MCP clients to connect to:
- http://localhost:8001 (Kanban MCP)
- http://localhost:8002 (Gmail MCP) 
- http://localhost:8003 (Example MCP)

### Hot Reloading

For development, you might want to run individual services outside Docker for faster iteration while keeping others in Docker. You can modify the `docker-compose.yml` to exclude specific services.

## Troubleshooting

### Services not starting?
```bash
./scripts/mcp-docker.sh logs
```

### Port conflicts?
Edit the port mappings in `docker-compose.yml` if you have conflicts with other services.

### Clean slate?
```bash
./scripts/mcp-docker.sh clean
./scripts/mcp-docker.sh build
./scripts/mcp-docker.sh start
```

### Health check failing?
Make sure your MCP servers have a `/health` endpoint that returns a 200 status code.

## Benefits of This Setup

✅ **Single Command Start**: No more juggling multiple terminals  
✅ **Automatic Restarts**: Services restart automatically if they crash  
✅ **Health Monitoring**: Built-in health checks for all services  
✅ **Centralized Logs**: View logs from all services in one place  
✅ **Port Management**: No port conflicts between services  
✅ **Easy Development**: Start/stop individual services as needed  

## Next Steps

1. Make sure Docker and Docker Compose are installed
2. Run `./scripts/mcp-docker.sh build` to build all images
3. Run `./scripts/mcp-docker.sh start` to start all services
4. Check `./scripts/mcp-docker.sh health` to verify everything is working
5. Configure your MCP clients to use the new endpoints! 