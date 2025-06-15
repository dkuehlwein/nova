# Nova Settings & Real-time Status – Implementation Roadmap

This document breaks the **Settings re-work and real-time plumbing** into small, self-contained work packages (WPs). Each WP is written so you can hand it directly to an AI coding assistant. 

👉 **Mandatory reminder for every WP:** *Search Context7 (use the `resolve-library-id` + `get-library-docs` tools) for the latest patterns before coding – especially for FastAPI background tasks, Redis async pubsub, TanStack Query, and Next app-router.*

⚠️  **Redis Setup Note:** First install Redis locally without Docker (`sudo apt install redis-server` on Ubuntu) due to current ARM/WSL/Docker compatibility issues. This is a temporary workaround.

---

## 0  Context Recap

* **Frontend**: Next 14 (app router, TS), shadcn-UI, TanStack Query not yet installed.
* **Backend**: FastAPI services `start_website.py` (chat agent) and `start_core_agent.py` plus various MCP servers – each already has a `/health` endpoint.
* **New architecture decisions**
  * MCP servers are defined in `configs/mcp_servers.yaml` (file-based, hot-reload)
  * The system prompt lives in `backend/agent/prompts/NOVA_SYSTEM_PROMPT.md`
  * Redis (new service) provides pub/sub; FastAPI pushes events → WebSocket clients
  * Docker-compose is already present; we'll add a restart endpoint that shells out to `docker-compose restart <service>` (dev-only convenience)
**Tests**:
Test go under 
- tests/backend/X for backend tests for module X 
- tests/frontend/X for frondend tests for part X
- tests for integration tests.

---

## Event Schema Standards

Define consistent event types in `backend/models/events.py`:

```python
from pydantic import BaseModel
from typing import Literal, Dict, Any
from datetime import datetime

class NovaEvent(BaseModel):
    id: str  # uuid
    type: Literal["mcp_toggled", "prompt_updated", "task_updated", "system_health", "config_validated"]
    timestamp: datetime
    data: Dict[str, Any]
    source: str  # service name

# WebSocket message format
class WebSocketMessage(BaseModel):
    id: str
    type: str
    timestamp: str  # ISO format
    data: Dict[str, Any]
    source: str
```

---

## Backend work packages

### **B1  Create YAML config for MCP servers** ✅ **COMPLETED**

**Goal**  Replace hard-coded list in `config.py` with a reloadable YAML.

1. ✅ Create directory `configs/` (if absent) and file `mcp_servers.yaml` seeded with:
   ```yaml
   gmail:
     url: http://localhost:8002/mcp
     health_url: http://localhost:8002/health
     description: Gmail MCP Server for email operations
     enabled: true
   ```
2. ✅ Add `pyyaml` and `watchdog` to backend deps (edit `pyproject.toml`).
3. ✅ In `backend/config.py`:
   * Load YAML in `load_mcp_yaml()` returning a `Dict[str, Any]`.
   * Expose a property `MCP_SERVERS` that filters only `enabled: true` entries.
4. ✅ **Hot-reload with debouncing**: start a watchdog observer (`watchdog[watchmedo]`) that listens for `mcp_servers.yaml` changes with 500ms debouncing to avoid race conditions and invalidates an in-memory cache (simple global `LOAD_TS`).

*Acceptance criteria*
* ✅ A unit test toggles `enabled:` flag and asserts the property changes after reload.
* ✅ Multiple rapid file changes only trigger one reload event.

**Completed:**
- ✅ Created `configs/mcp_servers.yaml` with initial Gmail server configuration
- ✅ Added `pyyaml>=6.0.0` and `watchdog>=4.0.0` dependencies
- ✅ Built `backend/utils/config_loader.py` with `ConfigLoader` class
- ✅ Implemented debounced file watching with 500ms delay
- ✅ Updated `backend/config.py` to use YAML configuration with fallback
- ✅ Added comprehensive unit tests for all functionality
- ✅ Thread-safe configuration loading with proper error handling
- ✅ Atomic file operations for configuration saves

### **B2  Move system prompt to markdown file + live reload**

1. Add `backend/agent/prompts/NOVA_SYSTEM_PROMPT.md` and copy the existing prompt text into it.
2. In `backend/agent/prompts.py` read the file on import:  
   `NOVA_SYSTEM_PROMPT = Path(__file__).with_name("NOVA_SYSTEM_PROMPT.md").read_text()`
3. **In dev, reuse the watchdog pattern from B1** with 500ms debouncing to listen for file saves and publish an event `{"type":"prompt_updated"}` via Redis (see B3).

### **B3  Redis integration & global event bus**

**Goal**  Allow any process to broadcast setting / task updates that UI clients receive via WebSocket.

1. Install Redis locally: `sudo apt install redis-server` (temporary workaround for Docker issues).
2. Add `redis-asyncio` to backend deps and bump backend image.
3. Implement `backend/utils/redis_manager.py`:
   * `get_redis()` (singleton `redis.asyncio.Redis` client)  
   * `async publish(event: NovaEvent)` - uses the event schema from above
   * `async subscribe(channel="nova_events") -> AsyncIterator[NovaEvent]`
4. Wherever YAML or prompt is edited (B1, B2 watchdog), call `publish()`.
5. Background task in `start_website.py` startup: `async for msg in subscribe(...)` → `websocket_manager.broadcast(msg)`.

### **B4  WebSocket endpoint**

* Add `websocket_manager.py` (track connections, `broadcast()`)
* `@router.websocket("/ws")` attaches clients, sends ping every 30 s, relays messages from Redis (handled in B3).
* Use the `WebSocketMessage` format defined in the schema section.

### **B5  MCP server endpoints**

1. `GET /api/mcp`  – return full list from YAML + live health status (reuse `MCPClientManager.check_server_health`).
2. `PUT /api/mcp/{name}/toggle` – flip `enabled` flag in YAML, save, `publish(NovaEvent(type="mcp_toggled", name=name, enabled=enabled))`.
3. Add pydantic `MCPServer` schema for response validation.

### **B6  Service restart endpoint (dev-only)**

`POST /api/admin/restart/{service_name}`
* Sanitize `service_name` against an `ALLOWED_SERVICES` list defined in settings.
* Use `subprocess.run(["docker-compose","restart",service_name])` and return stdout/stderr.

### **B7  Unit tests**

* pytest cases for YAML toggle, Redis publish/subscribe round-trip, and restart endpoint (mock subprocess).

### **B8  Observability & Logging Standards** ✅ **COMPLETED**

**Goal**  Implement structured logging and system observability.

1. ✅ Add structured logging configuration in `backend/utils/logging.py`:
   * Use `structlog` for consistent JSON logging
   * Define log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
   * Add request ID correlation for tracing
2. ✅ Add logging to all configuration changes, MCP toggles, and system events.
3. 🔄 Implement metrics endpoints:
   * `GET /api/metrics/websocket-connections` - active connection count
   * `GET /api/metrics/event-throughput` - events per minute
   * `GET /api/metrics/redis-health` - Redis connectivity status
4. 🔄 Add health check endpoint for Redis connectivity: `GET /api/health/redis`

*Acceptance criteria*
* ✅ All configuration changes are logged with structured data
* 🔄 WebSocket connection metrics are available
* 🔄 Redis health can be monitored independently

**Completed:**
- ✅ Structured logging with `structlog` and `orjson`
- ✅ Request ID middleware for FastAPI
- ✅ Event schema models in `backend/models/events.py`
- ✅ Helper functions for consistent logging
- ✅ Unit tests for logging functionality
- ✅ Added dependencies: `structlog`, `redis`, `orjson`

**Note:** Metrics endpoints will be implemented in B4 (WebSocket) and B3 (Redis) work packages.

### **B9  Configuration Validation**

**Goal**  Prevent invalid configurations and provide validation feedback.

1. Create Pydantic models for YAML validation in `backend/models/config.py`:
   ```python
   class MCPServerConfig(BaseModel):
       url: str
       health_url: str  
       description: str
       enabled: bool = True
   
   class MCPServersConfig(BaseModel):
       __root__: Dict[str, MCPServerConfig]
   ```
2. Add validation in YAML loading with detailed error reporting.
3. Create endpoint `POST /api/config/validate` - validates configuration without saving.
4. Add configuration backup/restore functionality:
   * Auto-backup on each change to `configs/backups/`
   * `POST /api/config/restore/{backup_id}` endpoint

*Acceptance criteria*
* Invalid YAML configurations are rejected with clear error messages
* Configuration changes are automatically backed up
* Validation can be performed without saving changes

---

## Integration work packages

### **I1  Integration Tests**

**Goal**  Test complete real-time flows end-to-end.

1. Create `tests/integration/test_settings_realtime.py`:
   * Test YAML change → Redis event → WebSocket broadcast flow
   * Test prompt file change → UI update flow  
   * Test MCP server toggle → health status update flow
2. Create `tests/integration/test_websocket_flows.py`:
   * Test WebSocket connection lifecycle
   * Test multiple concurrent clients receiving events
   * Test Redis reconnection scenarios
3. Add pytest fixtures for:
   * Redis test instance setup/teardown
   * WebSocket test client
   * Temporary configuration files

*Acceptance criteria*
* End-to-end settings change flows are tested
* WebSocket real-time updates are verified
* Redis pub/sub reliability is validated

---

## Frontend work packages

### **F1  Add TanStack Query & WebSocket hook**

1. `npm i @tanstack/react-query react-use-websocket`
2. Create `src/lib/queryClient.ts` and wrap `<QueryClientProvider>` in `app/(root)/layout.tsx`.
3. Implement `useNovaWebSocket()` that connects to `/ws`, decodes JSON using the `WebSocketMessage` schema, and dispatches to `queryClient.setQueryData()`.

### **F2  Live MCP & Health panels**

* Convert mocks in `settings/page.tsx` to real queries (`useQuery("mcp-servers", fetcher)` with staleTime 0).
* Switch toggles call `mutation(toggleMcp)`; optimistic update → server reply via WS.
* Health overview grid subscribes to `system_health` events.

### **F3  Navbar real-time counters**

* Currently shows static task counts; subscribe to `task_updated` WS events and update cache.

---

## Dev-Ops work packages

### **D1  Extend docker-compose**

* Add `redis:` service. Mount data volume if desired.
* Expose `/var/run/docker.sock` to backend container so restart endpoint works (`volumes: ["/var/run/docker.sock:/var/run/docker.sock"]`).

### **D2  Docs & onboarding**

* Update rules in .cursor/rules with:
  * How to add new MCP servers via YAML.
  * How hot-reload works.
  * How to use restart endpoint (dev-only).
  * Logging standards and observability endpoints.

---

## Done when
* Changing `enabled:` in YAML or saving the prompt file instantly propagates to the UI without page reload.
* Settings page shows real server list & can toggle them.
* Navbar numbers update live when core-agent processes tasks.
* `docker-compose restart mcp_gmail` can be triggered from the UI and reflected back in health status.
* All configuration changes are logged with structured data.
* Invalid configurations are prevented with clear validation feedback.
* Integration tests verify end-to-end real-time flows.

Happy building! Remember: **always** pull the freshest examples from Context7 first. 💪 