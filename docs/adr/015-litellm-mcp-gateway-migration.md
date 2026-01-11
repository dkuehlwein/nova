# ADR-015: LiteLLM MCP Gateway Migration

**Status**: Accepted - Implemented
**Date**: 2026-01-06
**Updated**: 2026-01-06
**Related**: [ADR-011](011-simplified-model-management-system.md)

> **Implementation Notes**: Phases 1-3 complete. MCP servers are now configured in `configs/litellm_config.yaml` and managed by LiteLLM. Nova's `MCPClientManager` queries LiteLLM's `/mcp-rest/tools/list` API. Frontend MCP settings page is read-only. Host-only servers (outlook_mac) run via launchd on macOS.

---

## Context

Nova currently manages MCP (Model Context Protocol) servers through a custom configuration file (`configs/mcp_servers.yaml`) and a dedicated `MCPClientManager` class that:

1. Reads server configurations from YAML
2. Performs health checks on each server
3. Connects via `langchain_mcp_adapters.client.MultiServerMCPClient`
4. Aggregates tools from multiple servers

This approach has limitations:

- **Duplication**: LiteLLM now offers native MCP Gateway functionality, duplicating Nova's logic
- **No Enterprise Support**: No mechanism for inheriting MCP servers from a central/enterprise registry
- **Local-Only**: Machine-specific MCP servers (e.g., Outlook on Mac) cannot coexist with shared enterprise services
- **Maintenance**: Nova must maintain MCP client code that LiteLLM already provides

### LiteLLM MCP Gateway Capabilities

LiteLLM (already Nova's LLM gateway per ADR-011) now provides:

- **MCP Server Registry**: Add/manage MCP servers via UI or config
- **Transport Support**: Streamable HTTP, SSE, and STDIO
- **Discovery API**: `/mcp-rest/tools/list` returns all tools with source server metadata
- **Access Control**: MCP permissions by Key, Team, or User
- **Database Persistence**: Already enabled in Nova (`store_model_in_db: true`)

## Decision

Migrate all MCP server management to LiteLLM, making it the single registry for both LLMs (per ADR-011) and MCP tools. This extends the "LiteLLM-First" architecture to include tool sources.

### Architecture

**Initial State (All Local):**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Developer Machine                              │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      Local LiteLLM Proxy                           │ │
│  │                                                                    │ │
│  │                          MCP Servers                               │ │
│  │  ┌───────────────────────────────────────────────────────────────┐│ │
│  │  │ • google-workspace    (Gmail, Calendar)                       ││ │
│  │  │ • feature-request     (Linear integration)                    ││ │
│  │  │ • outlook-mac         (Local Outlook - Mac only)              ││ │
│  │  └───────────────────────────────────────────────────────────────┘│ │
│  │                                                                    │ │
│  │   MCP Gateway: /mcp-rest/tools/list ─── Aggregated tools          │ │
│  └────────────────────────────────────────┬───────────────────────────┘ │
│                                           │                              │
│  ┌────────────────────────────────────────▼───────────────────────────┐ │
│  │                          Nova                                      │ │
│  │  • Single LiteLLM connection                                       │ │
│  │  • No mcp_servers.yaml parsing                                     │ │
│  │  • Tools via LiteLLM MCP Gateway API                               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

**Future State (Enterprise Federation):**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Developer Machine                              │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      Local LiteLLM Proxy                           │ │
│  │  ┌──────────────────┐     ┌─────────────────────────────────────┐ │ │
│  │  │  Local MCP       │     │      Upstream Enterprise            │ │ │
│  │  │  ─────────────   │     │      ────────────────────           │ │ │
│  │  │  • outlook-mac   │     │  api_base: enterprise.company.com   │ │ │
│  │  │  • local-scripts │     │  (aggregates enterprise MCP tools)  │ │ │
│  │  └──────────────────┘     └─────────────────────────────────────┘ │ │
│  │                                                                    │ │
│  │   MCP Gateway: /mcp-rest/tools/list ─── Local + Enterprise tools  │ │
│  └────────────────────────────────────────┬───────────────────────────┘ │
│                                           │                              │
│  ┌────────────────────────────────────────▼───────────────────────────┐ │
│  │                          Nova                                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────│─────────────────────────────┘
                                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Enterprise LiteLLM                                  │
│  • google-workspace    • jira-integration    • company-knowledge-base   │
│  • feature-request     • (centrally managed, team access controls)      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Location | Change |
|-----------|----------|--------|
| MCP Client | `backend/mcp_client.py` | Query LiteLLM `/mcp-rest/tools/list` instead of YAML |
| Config | `configs/mcp_servers.yaml` | Migrate to `configs/litellm_config.yaml` |
| LiteLLM Config | `configs/litellm_config.yaml` | Add `mcp_servers` section |
| Config Registry | `backend/utils/config_registry.py` | Remove MCP server config loader |

### LiteLLM MCP Server Configuration

MCP servers are defined in LiteLLM config using dictionary format with underscores (hyphens not allowed in server names):

```yaml
# configs/litellm_config.yaml
mcp_servers:
  google_workspace:
    url: http://nova-google-workspace:8000/mcp
    transport: http
    description: "Google Workspace - Gmail and Calendar operations"

  feature_request:
    url: http://nova-feature-request:8000/mcp
    transport: http
    description: "Linear integration for feature requests"

  outlook_mac:  # Host-only server (cannot run in Docker)
    url: http://host.docker.internal:9100/mcp
    transport: http
    description: "Local Outlook for Mac - Email and Calendar (via AppleScript)"
```

**Important Configuration Notes**:
- Server names use underscores, not hyphens (LiteLLM validation requirement)
- Transport `http` corresponds to FastMCP's `streamable-http`
- URLs should not have trailing slashes (causes 307 redirects)
- Host services use `host.docker.internal` to be accessible from Docker containers

### Enterprise Federation (Local → Enterprise Chaining)

For enterprise scenarios, the local LiteLLM connects to an upstream enterprise LiteLLM:

```yaml
# Local litellm_config.yaml
model_list:
  # Enterprise models via upstream
  - model_name: enterprise/*
    litellm_params:
      model: openai/*
      api_base: https://enterprise-litellm.company.com
      api_key: ${ENTERPRISE_LITELLM_KEY}

mcp_servers:
  # Local-only servers
  - name: outlook-mac
    url: http://localhost:9000/mcp/
    transport: streamable_http
    
  # Enterprise MCP servers via upstream (forwarding supported)
```

> **Note**: Research confirms LiteLLM supports MCP tool aggregation from multiple sources and can forward requests to upstream proxies. The MCP Gateway acts as a unified endpoint that aggregates tools from all registered MCP servers.

## Implementation Phases

### Host-Only MCP Servers

Some MCP servers cannot run in Docker and must run on the host:

| Server | Reason | Access Pattern |
|--------|--------|----------------|
| `outlook_mac` | Uses AppleScript (requires macOS GUI) | `host.docker.internal:9100` |

**Host Service Management**:
- Located in `mcp_servers/outlook-mac/`
- Includes launchd plist for automatic startup: `com.nova.outlook-mcp.plist`
- Logs at `/tmp/nova-outlook-mcp.{out,err}.log`
- Port 9100 (default 9000 often conflicts with Tailscale)

### Phase 1: Add Outlook MCP Server (Completed)

Created MCP server for Mac Outlook access in `mcp_servers/outlook-mac/`:

- Uses `FastMCP` framework (consistent with existing servers)
- Access Outlook via `appscript` (Python AppleScript bridge)
- Tools provided:
  - `list_emails` - List emails from inbox/folders
  - `read_email` - Read email content by ID
  - `create_draft` - Create email draft (no direct send initially)
  - `list_calendar_events` - List calendar events
- Runs as host service (cannot be containerized)

### Phase 2: Register with LiteLLM (Completed)

1. Added MCP server definitions to `litellm_config.yaml` (see configuration above)
2. Verified LiteLLM discovers and exposes tools via `/mcp-rest/tools/list`
3. Tested tool execution through LiteLLM gateway

**Verification**:
```bash
curl -s -H "Authorization: Bearer sk-1234" http://localhost:4000/mcp-rest/tools/list
```

### Phase 3: Migrate Nova MCP Client (Completed)

1. Updated `MCPClientManager` to query LiteLLM's `/mcp-rest/tools/list` API
2. Removed dependency on `langchain_mcp_adapters.client.MultiServerMCPClient`
3. Added tool call functionality via LiteLLM's `/mcp-rest/tools/call` API
4. Removed `mcp_servers.yaml` configuration file
5. Updated `ConfigRegistry` to remove MCP config loader
6. Updated `/api/mcp/` endpoint to be read-only (LiteLLM is source of truth)
7. Removed `MCP_SERVERS` property from `config.py`

**Key Changes**:
- `backend/mcp_client.py`: Complete rewrite to use LiteLLM HTTP API
- `backend/api/mcp_endpoints.py`: Simplified to read-only status from LiteLLM
- `backend/config.py`: Removed MCP_SERVERS property
- `backend/utils/config_registry.py`: Removed mcp_servers config registration
- `configs/mcp_servers.yaml`: Deleted (configuration now in `litellm_config.yaml`)

### Phase 4: Enterprise Testing (Future)

1. Deploy test enterprise LiteLLM instance
2. Configure local→enterprise proxy chaining
3. Verify MCP server aggregation across both layers
4. Document enterprise deployment pattern

## Consequences

### Positive

- **Simpler Nova**: Remove ~200 lines of MCP management code
- **Single Registry**: LiteLLM manages both LLMs and MCP tools
- **Enterprise Ready**: Federation architecture for local/enterprise split
- **Access Control**: Leverage LiteLLM's key/team permissions for MCP
- **UI Management**: MCP servers managed via LiteLLM UI

### Negative

- **LiteLLM Dependency**: Tighter coupling to LiteLLM for tool discovery
- **Migration Effort**: Existing deployments need config migration
- **Upstream Complexity**: Enterprise federation adds deployment complexity

### Risks

| Risk | Mitigation |
|------|------------|
| LiteLLM MCP API changes | Pin LiteLLM version, add API compatibility tests |
| Enterprise MCP not aggregating | Configure enterprise MCPs locally pointing to enterprise URLs |
| Migration breaks existing setups | Provide migration script, keep YAML parser as fallback |

## MCP Tool Namespacing Convention

**Updated**: 2026-01-11

To prevent tool name collisions when multiple MCP servers are registered, Nova applies automatic server-name prefixing to all MCP tools.

### Format

```
{server_name}-{tool_name}
```

**Examples**:
- `send_email` from `google_workspace` → `google_workspace-send_email`
- `list_emails` from `outlook_mac` → `outlook_mac-list_emails`
- `request_feature` from `feature_request` → `feature_request-request_feature`

### Why Hyphen Separator?

The hyphen (`-`) separator is compatible with Claude's tool name pattern: `^[a-zA-Z0-9_-]{1,128}$`

This matches LiteLLM's built-in prefixing convention (implemented in PR #12271, #12430).

### Implementation

1. **MCP Servers**: Define tools with simple base names (no manual prefixes)
   - ✅ `send_email`, `list_events`, `create_draft`
   - ❌ `gmail_send_email`, `outlook_list_emails`

2. **Nova's mcp_client.py**: Automatically prefixes tool names with `server_name-` when converting to LangChain tools

3. **Tool Permissions**: Reference tools by their prefixed names in `configs/tool_permissions.yaml`

### Benefits

- **Automatic uniqueness**: No manual discipline required
- **Clean MCP servers**: Servers have simple, reusable tool names
- **Collision-proof**: Two servers can define `send_email` without conflict
- **Industry standard**: Follows MCP protocol best practices

## Related ADRs

- **ADR-011**: LiteLLM-First Model Management (extended to MCP)
- **ADR-012**: Multi-Input Hook Architecture (email/calendar hooks may use MCP)
- **ADR-014**: Pluggable Skills System (skills may expose MCP-compatible tools)

---
*Last reviewed: 2026-01-11*
