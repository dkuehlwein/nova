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

- **Database Storage**: A new `llm_models` table will be created in the PostgreSQL database to store model configurations (e.g., model name, provider, API keys). This aligns with the Tier 3 (User Settings) pattern from ADR-008.
- **Dynamic Configuration**: The Nova Backend will be responsible for reading this database table and configuring the LiteLLM service on startup and on-change, likely by generating the necessary config and using LiteLLM's `/config/reload` endpoint.
- **Secrets Management**: Secrets like API keys will still be loaded from the `.env` file into the backend, which then uses them to configure LiteLLM. They are never stored in the database directly.

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

#### 5. **Error Handling (MVP Scope)**

- For the MVP, the LiteLLM gateway will be configured to **return an error** if the selected provider fails. An automatic fallback to a secondary provider is not in scope for the initial implementation.

### Model Strategy

- The default local model will be **Qwen 2.5 32B Instruct**, which is state-of-the-art for agentic tool use as of July 2025.
- A smaller alternative, like **Gemma 2 9B IT**, will be recommended for users with less powerful hardware.

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