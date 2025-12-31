# ADR-011: LiteLLM-First Model Management Architecture

**Status**: Accepted - Implemented
**Date**: 2025-07-28
**Updated**: 2025-12-31
**Supersedes**: [ADR-009](archive/009-hybrid-llm-architecture.md)

> **Implementation Notes**: All phases complete. Memory system uses LiteLLM routing via OpenAI-compatible clients. User settings support separate chat, memory, and embedding model selection. Dynamic model discovery via `/models/categorized` endpoint. Onboarding includes model selection step.

---

## Context

Nova originally had complex model management that created barriers:
- LiteLLM UI required manual password lookup
- Configuration scattered across YAML, .env, and database
- No UI for adding new models
- Memory system hardcoded to Google Gemini
- Users needed to understand provider differences

### Strategic Goal

Nova should be a **task management system that uses LiteLLM for AI**, not a model management system.

## Decision

Implement a **LiteLLM-First Architecture** where:
- LiteLLM is the single AI gateway for all model operations
- Nova only stores model selection preferences, not provider configuration
- Memory and chat both route through LiteLLM's OpenAI-compatible API
- Model discovery happens dynamically via LiteLLM API

## Architecture

```
Nova ←→ LiteLLM ←→ [OpenAI, Anthropic, HuggingFace, Local Models, etc.]
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| LLM Service | `backend/services/llm_service.py` | Model discovery and LiteLLM integration |
| User Settings | `backend/models/user_settings.py` | Model preferences (`chat_llm_model`, `memory_llm_model`, `embedding_model`) |
| GraphitiManager | `backend/memory/graphiti_manager.py` | Memory using OpenAI clients → LiteLLM |
| Onboarding | `frontend/src/app/onboarding/page.tsx` | 5-step wizard with model selection |
| Settings | `frontend/src/app/settings/page.tsx` | Model management UI |

### Model Categories

- **Chat Models**: For user-facing conversations (e.g., `phi-4-Q4_K_M`, `qwen3-32b`)
- **Memory Models**: For knowledge graph operations (typically same as chat)
- **Embedding Models**: For semantic search (e.g., `qwen3-embedding-4b`)

## Configuration

### LiteLLM Config (`configs/litellm_config.yaml`)

Models are defined in LiteLLM configuration, not Nova:
- HuggingFace models for local-first approach
- Cloud models (OpenAI, Anthropic) as optional
- Embedding models for memory system

### User Settings (Database)

Nova stores only model preferences:
```python
chat_llm_model: str = "phi-4-Q4_K_M"
memory_llm_model: str = "phi-4-Q4_K_M"
embedding_model: str = "qwen3-embedding-4b"
chat_llm_temperature: float = 0.7
memory_llm_temperature: float = 0.1
```

## Integration

### Memory System Migration

Graphiti uses OpenAI-compatible clients pointing to LiteLLM:
- `OpenAIClient` instead of `GeminiClient`
- `OpenAIEmbedder` instead of `GeminiEmbedder`
- Base URL: LiteLLM proxy (default `http://localhost:4000`)

### Model Discovery

Frontend discovers available models via:
```
GET /api/models/categorized → { chat_models: [...], embedding_models: [...] }
```

This queries LiteLLM's `/models` endpoint and categorizes results.

### Onboarding Flow

5-step wizard:
1. Welcome
2. API Keys
3. **AI Models** (select chat, memory, embedding)
4. User Profile
5. Complete

## Consequences

### Positive

- Single integration point for all AI operations
- Provider-agnostic model selection
- Instant model switching (no restarts for cloud models)
- Memory system freed from Gemini lock-in
- Simplified onboarding (<2 minutes)

### Negative

- LiteLLM dependency for all AI operations
- Additional network hop through proxy
- Users need LiteLLM running for any AI functionality

### Risks

- **LiteLLM unavailable**: All AI operations fail. Mitigated by health checks.
- **Migration complexity**: Existing Gemini users need migration. Mitigated by auto-detection.

## Related ADRs

- **ADR-003**: Graphiti memory system (now uses LiteLLM routing)
- **ADR-004**: Configuration management (model settings in Tier 3)

---
*Last reviewed: 2025-12-31*
