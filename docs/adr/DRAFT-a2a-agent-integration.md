# DRAFT: A2A Agent Integration

**Status**: Proposed (Supersedes DRAFT-hierarchical-agent-architecture)
**Date**: 2026-01

---

## Context

Nova needs multi-agent capabilities for complex, multi-step tasks. The current `chat_agent` is a simple reactive agent that struggles with tasks requiring planning, delegation, or coordination with specialized agents.

Two approaches were evaluated:

### Option 1: Custom Hierarchical Architecture

The existing [DRAFT-hierarchical-agent-architecture.md](./DRAFT-hierarchical-agent-architecture.md) proposes a Supervisor/Worker pattern within the chat agent:

- **Pros**: Full control over agent behavior
- **Cons**:
  - Requires significant custom implementation
  - Limited to internal agents only
  - No standardized protocol for external interop
  - Reinvents patterns that already exist in the ecosystem

### Option 2: A2A Protocol Integration (This Proposal)

[A2A (Agent-to-Agent)](https://a2aprotocol.ai/) is Google's open standard for agent interoperability, announced in 2025 with 50+ technology partners including LangChain, Microsoft, Salesforce, and SAP.

- **Pros**:
  - Industry standard protocol
  - Already supported by LiteLLM v1.80.8+
  - Enables both internal and external agent communication
  - Similar integration pattern to MCP (already implemented in Nova)
  - LiteLLM provides routing, authentication, and logging

- **Cons**:
  - Depends on external protocol evolution
  - May need adapters for non-compliant agents

## Decision

Adopt the **A2A protocol** for multi-agent communication, enabling Nova to:

1. **Act as an A2A Server**: Expose Nova's chat agent so external agents can discover and call it
2. **Act as an A2A Client**: Call external A2A-compatible agents (LangGraph, Azure AI Foundry, Bedrock AgentCore, etc.)

This supersedes the custom hierarchical architecture proposal.

## Architecture

```
External Agents                    Nova System                         External A2A Agents
      │                                │                                      │
      │  GET /.well-known/agent.json   │                                      │
      ├───────────────────────────────▶│                                      │
      │  (Agent Card Discovery)        │ A2A Server Layer                     │
      │                                │   └─ FastAPI endpoints               │
      │  POST /a2a                     │   └─ JSON-RPC 2.0 handler            │
      ├───────────────────────────────▶│                                      │
      │  (JSON-RPC: tasks/send)        │                                      │
      │◀───────────────────────────────┤                                      │
      │                                │                                      │
                                       │ Chat Agent (LangGraph)               │
                                       │   └─ Existing agent with tools       │
                                       │   └─ call_agent tool (NEW)           │
                                       │                                      │
                                       │ A2A Client Layer                     │
                                       │   └─ A2AClientManager                │
                                       │   └─ Agent discovery & caching       │
                                       │───────────────────────────────────────▶│
                                       │      POST /a2a (JSON-RPC)            │
                                       │◀───────────────────────────────────────│
```

### Integration with LiteLLM

LiteLLM v1.80.8+ provides an [A2A Agent Gateway](https://docs.litellm.ai/docs/a2a) that offers:

- Unified interface for multiple agent types (LangGraph, Azure AI Foundry, Bedrock, Pydantic AI)
- Request/response logging
- Access control (which teams/keys can access which agents)
- Cost tracking per query

Nova can leverage this gateway for external agent calls while also exposing itself as an A2A endpoint.

## A2A Protocol Overview

### Agent Card Discovery

Every A2A agent exposes a card at `/.well-known/agent.json`:

```json
{
  "protocolVersion": "1.0",
  "name": "nova",
  "displayName": "Nova - AI Task Manager",
  "description": "AI-powered kanban task management with memory",
  "interfaces": [
    {"url": "http://localhost:8000/a2a", "protocol": "JSONRPC"}
  ],
  "capabilities": {
    "streaming": true,
    "stateHistory": true
  },
  "skills": [
    {"name": "task_management", "description": "Create, update, and list kanban tasks"},
    {"name": "memory_search", "description": "Search conversation memory"}
  ]
}
```

### JSON-RPC Communication

A2A uses JSON-RPC 2.0 for message exchange:

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "method": "tasks/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Create a high-priority task for code review"}],
      "messageId": "msg-123"
    }
  }
}
```

## Implementation Phases

### Phase 1: A2A Server

Expose Nova as an A2A-compatible agent:

| Component | Description |
|-----------|-------------|
| `GET /.well-known/agent.json` | Return Nova's Agent Card |
| `POST /a2a` | JSON-RPC handler delegating to `chat_service.stream_chat()` |
| Optional API key auth | Via `A2A_API_KEY` environment variable |

### Phase 2: A2A Client

Enable Nova to call external A2A agents:

| Component | Description |
|-----------|-------------|
| `A2AClientManager` | Follows `MCPClientManager` pattern |
| Agent discovery | Fetch and cache agent cards |
| YAML configuration | Register agents in `litellm_config.yaml` |

### Phase 3: Tool Integration

Make A2A agents available as LangChain tools:

| Component | Description |
|-----------|-------------|
| `get_a2a_tools()` | Convert registered agents to `StructuredTool` |
| `get_all_tools()` | Include A2A tools alongside MCP tools |
| Tool approval | Integrate with existing approval system (ADR-013) |

## Configuration

Following the MCP pattern (ADR-015), A2A agents are configured in YAML:

```yaml
# configs/litellm_config.yaml

a2a_agents:
  research_agent:
    url: http://research-service:8000
    description: "Deep research and analysis agent"
    auth:
      type: apiKey
      header: X-API-Key
      key_env: RESEARCH_AGENT_API_KEY

  code_reviewer:
    url: http://code-review:8000
    description: "Code review and improvement suggestions"
    auth:
      type: none  # Development mode
```

## Files to Create

| File | Purpose |
|------|---------|
| `backend/a2a_client.py` | A2AClientManager for discovering and calling agents |
| `backend/api/a2a_endpoints.py` | FastAPI endpoints for A2A server |
| `backend/services/a2a_service.py` | Business logic for A2A operations |
| `backend/models/a2a_models.py` | Pydantic models for A2A protocol |
| `backend/tools/a2a_tools.py` | LangChain tool wrappers |

## Files to Modify

| File | Changes |
|------|---------|
| `backend/tools/__init__.py` | Add `get_a2a_tools()` |
| `backend/agent/chat_agent.py` | Include A2A tools in `get_all_tools()` |
| `backend/start_website.py` | Register A2A router |
| `configs/litellm_config.yaml` | Add `a2a_agents` section |
| `backend/config.py` | Add A2A settings |

## Consequences

### Positive

- **Industry Standard**: Google's A2A protocol with 50+ technology partners
- **Interoperability**: Connect with external agents (research, code review, data analysis)
- **Familiar Pattern**: Similar to existing MCP integration (ADR-015)
- **LiteLLM Integration**: Built-in routing, auth, and observability
- **Future-Proof**: Protocol actively developed by major vendors

### Negative

- **External Dependency**: Protocol evolution outside Nova's control
- **Complexity**: Additional abstraction layer for agent communication
- **Adapters**: May need custom adapters for non-A2A agents

## Comparison with Hierarchical Architecture

| Aspect | Hierarchical (Old) | A2A (New) |
|--------|-------------------|-----------|
| Scope | Internal only | Internal + external agents |
| Protocol | Custom | Industry standard |
| Implementation | Build from scratch | Leverage LiteLLM gateway |
| Interoperability | None | Full A2A ecosystem |
| Complexity | Custom planning logic | Standard protocol handling |

## References

- [LiteLLM A2A Gateway](https://docs.litellm.ai/docs/a2a)
- [LiteLLM v1.80.8 Release Notes](https://docs.litellm.ai/release_notes/v1-80-8)
- [LangGraph A2A Integration](https://docs.litellm.ai/docs/providers/langgraph)
- [LangChain A2A Server](https://docs.langchain.com/langgraph-platform/server-a2a)
- [Google A2A Protocol](https://a2aprotocol.ai/)
- [A2A LangGraph Template](https://github.com/llmx-de/a2a-template-langgraph)

---

*Draft - Not yet implemented*
