# DRAFT: DeepEval Integration for LLM Testing

**Status**: Proposed
**Date**: 2025-07-16

---

## Context

Nova lacks systematic LLM evaluation:
- Manual testing with custom scripts
- No regression testing for prompt changes
- No standardized metrics across models
- No production performance monitoring
- No CI/CD integration for model validation

## Decision

Integrate **DeepEval** as Nova's LLM evaluation framework:
- Compatible with existing LiteLLM proxy
- Supports local models
- Provides 14+ built-in metrics
- Enables CI/CD integration

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Golden Dataset │───▶│   DeepEval      │───▶│   LiteLLM       │
│  (Test Cases)   │    │   Runner        │    │   Proxy         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Evaluation    │
                       │   Results       │
                       └─────────────────┘
```

## Key Components

### Model Configuration
DeepEval connects to Nova's LiteLLM proxy at `localhost:4000`.

### Metrics
- **Nova Tool Calling**: Custom metric for escalation tool usage
- **Answer Relevancy**: Response quality
- **Faithfulness**: Accuracy to context

### Golden Dataset
Test cases covering:
- Tool calling scenarios
- Task management operations
- Escalation patterns

## Integration Points

### LiteLLM Proxy
DeepEval uses `LiteLLMModel` pointing to Nova's proxy with existing API key.

### Chat Agent Testing
Direct integration with `create_chat_agent()` for end-to-end tests.

### CI/CD Pipeline
GitHub Actions workflow triggers on:
- Prompt file changes (`backend/agent/prompts/**`)
- LiteLLM config changes
- LLM code changes (`backend/agent/llm.py`)

## Evaluation Types

| Type | Purpose |
|------|---------|
| Regression | Detect performance degradation |
| Comparison | Compare models systematically |
| Production | Monitor live performance |

## Consequences

### Positive

- Automated regression detection
- Consistent model comparison
- CI/CD integration prevents broken deployments
- Standardized evaluation metrics

### Negative

- DeepEval dependency
- Evaluation adds latency to CI
- Initial setup for golden dataset

## Next Steps

1. Install DeepEval: `uv add deepeval`
2. Create model configuration for LiteLLM
3. Implement Nova-specific metrics
4. Build golden dataset
5. Set up CI/CD integration

---
*Draft - Not yet implemented*
