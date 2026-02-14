# NOV-114: Fix chat sidebar showing AI system message instead of useful title

**Linear ticket**: NOV-114
**Branch**: fix/NOV-114-chat-sidebar-ai-system-message

## Investigation Notes

### Data flow for sidebar titles

1. Frontend `ChatSidebar` -> `ChatHistoryItem` displays `item.title` (bold) and `item.last_message` (preview)
2. Data comes from `GET /chat/conversations` -> `conversation_service.get_summary()`
3. `get_summary()` calls `get_title()` for the title and uses `messages[-1].content` for last_message
4. `get_title()` has a 3-step fallback chain:
   - Task chats: look up task title from DB
   - Check `chat_metadata_service.get_title()` for a persisted custom title
   - Fall back to first **user** message (truncated to 50 chars)
5. `generate_title()` is called separately from `POST /chat/conversations/{id}/generate-title`
   - Tries LLM-based title generation via LiteLLM HTTP API
   - Falls back to first user message if LLM fails
   - Persists result to `chat_metadata` table

### Previous fix attempts

Two previous PRs attempted to fix this:
- `fix/NOV-114-chat-title-not-persisting-to-db` (merged 061eb6c): Added prompt-leak detection, fallback to first user message in `generate_title()`
- `fix/NOV-114-title-generation-integration` (merged e761d56): Added thinking token stripping, integration tests

These fixes improved `generate_title()` but the ticket was marked Done prematurely. The LLM title generation still fails silently with local models (returns `{"generated": false}`).

### Current state of the code

The `get_title()` method (line 368) already correctly falls back to first user message. The `generate_title()` method also correctly falls back. However:

1. `generate_title()` returns `None` when there are no assistant messages yet, which means no title is persisted to metadata
2. The endpoint (chat_endpoints.py line 258-264) handles this by calling `get_title()` as fallback, but does NOT persist the result
3. On subsequent page loads, `get_title()` correctly computes the title from the first user message

### Remaining issues

1. **`generate_title()` requires both user AND assistant messages** - returns None for single-message conversations. The endpoint fallback doesn't persist the title, so it's recomputed each time (but correctly).

2. **Integration tests are not runnable without infrastructure** - `tests/integration/test_title_generation.py` requires real LiteLLM and PostgreSQL. These tests can never run in normal test suites and don't verify the actual fallback behavior.

3. **Unit tests mock too heavily** - `TestGenerateTitleSanitization` mocks the entire HTTP layer including aiohttp.ClientSession. While they test the validation logic, they don't catch the real bug scenario where the sidebar shows wrong content.

4. **The `last_message` preview in sidebar** - `get_summary()` picks `messages[-1].content` for the last_message field. For a new conversation where the AI's first response is the memory search message, this could show that message as the preview. However, typically the AI responds with more after the memory search.

## Approach

### 1. Simplify title generation - remove broken LLM title generation

The LLM-based title generation via local models is unreliable (small models echo prompts, reasoning models need thinking token stripping, etc.). Following the ticket's guidance: "Every major AI chat product derives conversation titles from the first user message."

**Decision**: Remove the LLM title generation entirely. Use first user message truncated to 70 chars as the title. This is simple, reliable, and matches what ChatGPT/Claude.ai/Gemini do as their initial title before LLM generation kicks in.

Rationale: The local LLM models (GLM-4.7-Flash, etc.) are unreliable for title generation. The added complexity of prompt-leak detection, thinking token stripping, and HTTP calls to LiteLLM is not worth it for a feature that consistently fails. If/when a reliable cloud model is available, title generation can be re-added.

### 2. Fix the fallback in get_title() to use 70 chars

Change truncation from 50 to 70 chars (ticket says "~60-80 chars"). This gives more context for identifying conversations.

### 3. Clean up the generate-title endpoint

Keep the endpoint but simplify it: just call `get_title()` and persist the result. No LLM call.

### 4. Remove useless tests, write proper ones

- Remove `tests/integration/test_title_generation.py` (requires infrastructure, doesn't catch bug)
- Remove `TestGenerateTitleSanitization` class (over-mocked, tests dead code)
- Remove `_is_valid_title`, `_PROMPT_LEAK_PHRASES` (dead code after removing LLM generation)
- Write new unit tests that verify:
  - Fallback picks first user message, not first AI message
  - First user message is properly truncated with ellipsis
  - Conversations with only AI messages before user message get correct title

## Key files to modify

- `backend/services/conversation_service.py` - Remove `generate_title()` LLM logic, simplify to user message fallback, remove prompt-leak helpers
- `backend/api/chat_endpoints.py` - Simplify generate-title endpoint
- `tests/unit/test_services/test_conversation_service.py` - Remove `TestGenerateTitleSanitization`, update `TestGenerateTitle`, add new fallback tests
- `tests/integration/test_title_generation.py` - Delete entirely

## Open questions

- Should we keep the `generate_title` endpoint for future use with a cloud model? **Decision**: Yes, keep it but simplify. The frontend already calls it, and it can be enhanced later.
- Should `last_message` also filter out AI system messages? **Deferred**: The ticket focuses on titles. The last_message showing memory search text is less likely since it's the LAST message, not the first.
