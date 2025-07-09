# ADR-009: Local and Hybrid LLM Integration via LiteLLM

## Status
Accepted (Revised)

## Context

Nova initially relied exclusively on Google's Gemini API. This created dependencies related to rate limiting, cost, internet reliability, and data privacy. The goal is to introduce a hybrid architecture supporting both cloud and local LLMs to mitigate these issues.

This ADR has been revised to incorporate a more robust, industry-standard approach using an open-source LLM gateway, which simplifies the architecture and aligns with the project's existing configuration patterns.

## Decision

We will implement a **hybrid LLM architecture** using **LiteLLM** as a central gateway. This proxy service will manage all LLM requests, routing them to either a cloud provider (Google API) or a local provider (**Ollama**) based on a central configuration stored in the **database**.

This approach provides:
- **Provider Flexibility**: Easily switch between or mix cloud and local models.
- **Simplified Services**: The core backend and MCP servers no longer need provider-specific logic.
- **Centralized & Dynamic Control**: Manage models, keys, and routing in the database via the Settings UI at runtime.
- **Cost Optimization**: Reduce API costs through local inference.
- **Reliability & Privacy**: Enable offline capability and keep data on-premises.

## Architecture Overview

### Component Changes

#### 1. **New Infrastructure: LiteLLM Gateway**

We will add two new containers to our Docker-based infrastructure:

**Ollama Service (`ollama`)**
- Runs the Ollama server for local model inference.
- Manages model storage, downloading, and GPU acceleration.

**LiteLLM Gateway (`litellm`)**
- A central proxy service that receives all LLM requests from within the Nova ecosystem.
- Provides a unified, OpenAI-compatible API endpoint to all internal services.
- Will be dynamically configured by the Nova Backend based on settings stored in the database.

#### 2. **Configuration Overhaul (Database-driven)**

- **Database Storage**: A new `llm_models` table will be created in the PostgreSQL database to store model configurations. This aligns with the Tier 3 (User Settings) pattern from ADR-008.
- **Dynamic Configuration**: The Nova Backend will be responsible for reading this database table and configuring the LiteLLM service on startup and on-change, likely by generating the necessary config and using LiteLLM's `/config/reload` endpoint.
- **Secrets Management**: Secrets like API keys will still be loaded from the `.env` file into the backend, which then uses them to configure LiteLLM. They are never stored in the database directly.

**Database Schema (`llm_models` table):**
```sql
CREATE TABLE llm_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,           -- Display name (e.g., "Gemma 3 8B Local")
    model_name VARCHAR(200) NOT NULL,     -- LiteLLM model identifier
    provider VARCHAR(50) NOT NULL,        -- Provider type (ollama, openai, etc.)
    is_default BOOLEAN DEFAULT FALSE,     -- Whether this is the default model
    is_active BOOLEAN DEFAULT TRUE,       -- Whether model is available
    config JSONB,                         -- Provider-specific configuration
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 3. **Core LLM Integration Points (Revised Scope)**

All services that perform LLM calls will be updated to use the LiteLLM gateway. This is a simple change, as they will all now target a single, OpenAI-compatible endpoint.

**The scope of this change includes:**
- **Chat Agent (`chat_agent.py`)**
- **Core Agent (`core_agent.py`)**
- **Memory System (`graphiti_manager.py`)**
- **Email Processing (`email_tasks.py`)**
- **ALL MCP Servers that use LLMs (`mcp_servers/*`)**

#### 4. **Frontend Changes**

- **Settings UI (`settings/page.tsx`)**: The frontend settings page will be extended with a new section to manage the `llm_models` database table, allowing users to add, edit, and select the models they want to use at runtime.
- **LiteLLM Monitoring Integration**: The UI will include monitoring capabilities leveraging LiteLLM's built-in dashboard features:
  - **Cost Tracking**: Real-time token usage and cost monitoring per model
  - **Usage Analytics**: Request frequency, response times, and success rates
  - **Expert Settings**: Advanced configuration panel with budget controls and usage alerts
  - **Dashboard Integration**: Optional embedded LiteLLM UI at `/llm-monitoring` endpoint

#### 5. **Error Handling Strategy**

**MVP Scope:**
- LiteLLM gateway will **return an error** if the selected provider fails
- No automatic fallback to secondary providers initially
- Errors will be logged and surfaced to the user through Nova's existing error handling system

**Error Scenarios & Handling:**
- **Ollama Service Down**: Return clear error message, suggest using cloud model
- **Model Not Downloaded**: Automatically trigger model download via Ollama API
- **Out of VRAM**: Return resource exhaustion error with model recommendations
- **LiteLLM Gateway Failure**: Fallback to direct cloud provider calls (future enhancement)
- **Invalid Model Configuration**: Validate model configs before saving to database

**Monitoring & Alerting:**
- LiteLLM provides built-in health check endpoints (`/health`)
- Nova backend will monitor service health and update model availability status
- Failed requests will be tracked in LiteLLM's monitoring dashboard

### Model Strategy

- The default local model will be **Gemma 3 8B Instruct**, which provides excellent performance for agentic tool use while being suitable for 16GB VRAM configurations.
- Alternative models like **Qwen 2.5 32B Instruct** will be available for users with more powerful hardware (32GB+ VRAM).

## Implementation Phases

### Phase 1: Infrastructure & Database
1. Add `ollama` and `litellm` containers to Docker Compose.
2. Create the `llm_models` database schema and API endpoints in the Nova Backend for managing it.
3. Implement the logic in the Nova Backend to dynamically configure LiteLLM from the database.

### Phase 2: Core Integration
1. Migrate all services (backend and MCPs) to make their LLM calls to the LiteLLM gateway's endpoint.

### Phase 3: User Experience & Documentation
1. Build the new Settings UI for managing LLM configurations.
2. Document the new architecture and how to add/configure models.

## Conclusion

Adopting LiteLLM as a database-configured gateway is a significant architectural improvement. It fully addresses the project's requirements for a hybrid, privacy-first LLM architecture and aligns perfectly with our established patterns for dynamic, user-driven configuration. This approach is faster to implement, more robust, and more flexible than the originally proposed solutions.