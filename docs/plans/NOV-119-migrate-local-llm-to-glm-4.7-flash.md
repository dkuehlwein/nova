# NOV-119: Migrate Local LLM from Nemotron3 to GLM-4.7-Flash

**Linear ticket:** [NOV-119](https://linear.app/nova-development/issue/NOV-119/migrate-local-llm-from-nemotron3-to-glm-47-flash)

## Investigation Notes

- **Model discovery is dynamic**: Local models are auto-discovered from LM Studio at startup via `llm_service.py:initialize_local_llm_models()`. No static config changes needed. GLM-4.7-Flash appears automatically as `local/zai-org/glm-4.7-flash`.
- **Thinking tags already handled**: GLM-4.7-Flash outputs `<think>...</think>` tags. Frontend already parses these (`markdown-parser.ts`) and renders collapsible reasoning blocks (`MarkdownMessage.tsx`). Title generation (`conversation_service.py`) strips them. No code changes needed.
- **Tool calling works**: Verified via LiteLLM - correct tool selection and parameter extraction.
- **NovaChatOpenAI wrapper**: Cleans null defaults from tool schemas. Model-agnostic, keep as-is.
- **Eval framework missing**: `tests/evals/` has no source files. Manual testing required for quality comparison.

## Approach

The architecture is already model-agnostic. The migration requires:
1. Update Nemotron-specific references in comments/docstrings to be model-agnostic
2. Manual verification by the user (chat quality, streaming, core agent loop)
3. No config, prompt, or frontend changes needed

## Key Files Modified

| File | Change |
|------|--------|
| `backend/agent/chat_llm.py` | Docstring: removed Nemotron-specific reference |
| `backend/services/conversation_service.py` | Comment: generalized thinking token reference |
| `tests/integration/test_title_generation.py` | Comments: generalized model references |
| `tests/unit/test_services/test_conversation_service.py` | Comment: generalized model reference |

## Open Questions

- **Eval comparison**: No programmatic eval framework exists. Quality comparison (verbosity, accuracy) must be done manually via the chat UI.
- **OpenRouter GLM**: `llm_service.py` has `z-ai/glm-4.5-air:free` as an OpenRouter model. Updating this to 4.7 could be a separate concern.
