# ADR-005: Nova Settings and Real-time Infrastructure

**Status**: Accepted - Implemented
**Date**: 2025-06
**Updated**: 2025-12-31

> **Implementation Notes**: Backend real-time infrastructure complete. YAML config loading, hot-reload, Redis pub/sub, WebSocket broadcasting, MCP management, and structured logging all operational. Frontend TanStack Query integration partial.

---

## Context

Nova needed a real-time settings infrastructure to:
- Hot-reload configuration changes (MCP servers, system prompts)
- Broadcast changes to connected clients via WebSocket
- Provide consistent API for configuration management
- Enable service restarts for development convenience

## Decision

Implement a real-time settings infrastructure with:
- **YAML-based configuration** with file watching and hot-reload
- **Redis pub/sub** for event distribution across services
- **WebSocket endpoints** for client notification
- **Structured logging** with request correlation

## Architecture

```
File Change → ConfigLoader → Redis Pub/Sub → WebSocket Broadcast → Frontend Update
                                  ↓
                           Agent Reload
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| ConfigLoader | `backend/utils/config_loader.py` | YAML loading with debounced file watching |
| PromptLoader | `backend/utils/prompt_loader.py` | System prompt loading with hot-reload |
| RedisManager | `backend/utils/redis_manager.py` | Async Redis client with pub/sub |
| WebSocketManager | `backend/utils/websocket_manager.py` | Connection management and broadcasting |
| WebSocket Endpoints | `backend/api/websocket_endpoints.py` | WS API endpoints |
| MCP Endpoints | `backend/api/mcp_endpoints.py` | MCP server management |
| Admin Endpoints | `backend/api/admin_endpoints.py` | Service restart (dev-only) |
| Config Endpoints | `backend/api/config_endpoints.py` | Configuration validation and backups |
| Logging | `backend/utils/logging.py` | Structured JSON logging |

## Configuration Files

| File | Purpose |
|------|---------|
| `configs/mcp_servers.yaml` | MCP server definitions |
| `backend/agent/prompts/NOVA_SYSTEM_PROMPT.md` | System prompt |
| `configs/input_hooks.yaml` | Input hook configuration |
| `configs/tool_permissions.yaml` | Tool approval rules |

## Event Types

| Event | Trigger | Purpose |
|-------|---------|---------|
| `prompt_updated` | System prompt file change | Reload agent prompts |
| `mcp_toggled` | MCP server enable/disable | Update tool availability |
| `config_validated` | Config validation complete | UI feedback |
| `task_updated` | Task status change | Kanban updates |

## API Endpoints

### WebSocket
| Endpoint | Purpose |
|----------|---------|
| `WS /ws/` | Main WebSocket connection |
| `GET /ws/connections` | Active connection status |
| `GET /ws/metrics` | Connection metrics |
| `POST /ws/broadcast` | Test broadcasting |

### MCP Management
| Endpoint | Purpose |
|----------|---------|
| `GET /api/mcp` | List MCP servers with health |
| `PUT /api/mcp/{name}/toggle` | Enable/disable server |

### Configuration
| Endpoint | Purpose |
|----------|---------|
| `POST /api/config/validate` | Validate configuration |
| `GET /api/config/backups` | List backups |
| `POST /api/config/restore/{id}` | Restore backup |

### Admin (Development)
| Endpoint | Purpose |
|----------|---------|
| `POST /api/admin/restart/{service}` | Restart Docker service |
| `GET /api/admin/allowed-services` | List restartable services |

## Features

### Hot-Reload System
- File watching with 500ms debounce
- Automatic cache invalidation
- Redis event publishing on change

### Configuration Validation
- Pydantic models for all config types
- URL validation, duplicate detection
- Automatic backup before saves

### Structured Logging
- JSON format with `structlog`
- Request ID correlation
- Service identification

## Consequences

### Positive

- Zero-restart configuration updates
- Real-time UI synchronization
- Consistent configuration API
- Comprehensive audit trail via backups

### Negative

- Redis dependency for pub/sub
- Additional complexity in file watching
- WebSocket connection management overhead

## Related ADRs

- **ADR-004**: Configuration architecture (BaseConfigManager pattern)
- **ADR-012**: Input hooks use same config system

---
*Last reviewed: 2025-12-31*
