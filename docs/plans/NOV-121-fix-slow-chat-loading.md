# NOV-121: Fix Slow Chat Loading and Add Loading Indicators

**Linear ticket:** NOV-121
**Branch:** fix/NOV-121-fix-slow-chat-loading-and-add-loading-indicators

## Investigation / Analysis

### Root Cause 1: N+1 Query Pattern in Chat List Endpoint

The `/chat/conversations` endpoint (`chat_endpoints.py:list_chats`) has a severe N+1 query problem:

1. `list_threads()` iterates over **all** checkpoints via `checkpointer.alist(None)` to collect unique thread IDs
2. For each thread ID, `get_summary()` is called **sequentially**
3. Each `get_summary()` call:
   - Calls `get_history()` which does `checkpointer.aget()` (1 DB query)
   - Calls `_build_timestamp_mapping()` which does `checkpointer.alist(config)` iterating **all checkpoints for that thread** (N DB reads)
   - For task threads, does an additional DB query to check task status
   - Calls `get_title()` which may do yet another DB query for custom title or task title

For 10 threads with 5 checkpoints each, that is ~60+ database operations just to list the sidebar.

### Root Cause 2: Expensive Chat History Loading

When opening an old chat (`/chat/conversations/{id}/task-data`):

1. `get_history()` is called which loads all messages (fine)
2. `_build_timestamp_mapping()` iterates **every checkpoint** in the thread's history to map message IDs to timestamps - this is O(checkpoints * messages_per_checkpoint)
3. The `get_task_chat_data` endpoint creates a full LangGraph chat agent (`create_chat_agent()`) just to check for interrupts - this involves loading tools, MCP connections, etc.
4. No caching of any of this data

### Root Cause 3: No Frontend Loading Feedback

The `handleChatSelect` function in `useChatPage.ts` calls `router.push()` then `await loadChat()` or `await loadTaskChat()`. During the entire await period:
- No loading indicator appears in the sidebar (the clicked item has no "loading" or "selected" state)
- The message area shows stale content from the previous chat until the new one fully loads
- `isLoading` is set inside `loadChat`, but nothing in the sidebar reacts to it visually per-item

## Approach

### Backend Fixes

**1. Optimize `list_chats` endpoint (chat_endpoints.py)**
- Skip `_build_timestamp_mapping()` in `get_summary()` - summaries don't need per-message timestamps, just latest timestamp from the checkpoint itself
- Add a lightweight `get_summary_fast()` method that avoids full history reconstruction
- Run summary fetching concurrently with `asyncio.gather()` instead of sequential loop

**2. Optimize `_build_timestamp_mapping` (conversation_service.py)**
- Make timestamp mapping optional (only needed for full history view, not for summaries)
- In `get_history()`, skip `_build_timestamp_mapping()` by default and use checkpoint timestamp as fallback

**3. Optimize `get_task_chat_data` endpoint (chat_endpoints.py)**
- Defer the agent creation and interrupt check - don't create a full agent just to check interrupts
- Use the checkpointer directly to check for interrupt state without creating the full agent

### Frontend Fixes

**4. Add loading state tracking for selected chat (useChatPage.ts)**
- Add `loadingChatId` state to track which chat is currently being loaded
- Set it immediately on click, clear on load complete

**5. Add visual loading indicator in sidebar (ChatSidebar.tsx, ChatHistoryItem.tsx)**
- Show spinner/highlight on the chat item being loaded
- Keep sidebar responsive

**6. Add loading skeleton in message area (ChatMessageList.tsx)**
- Show skeleton while messages are loading for an existing chat

## Key Files to Modify

### Backend
- `backend/api/chat_endpoints.py` - Optimize list_chats, get_task_chat_data
- `backend/services/conversation_service.py` - Add get_summary_fast(), make timestamp mapping optional

### Frontend
- `frontend/src/hooks/useChatPage.ts` - Add loadingChatId state
- `frontend/src/components/chat/ChatSidebar.tsx` - Pass and use loadingChatId
- `frontend/src/components/chat/ChatHistoryItem.tsx` - Show loading state
- `frontend/src/components/chat/ChatMessageList.tsx` - Add loading skeleton

### Tests
- `tests/unit/test_chat_loading_performance.py` - Unit tests for optimized endpoints
- `tests/unit/frontend/` or inline - Loading indicator rendering tests (if applicable)

## Open Questions / Risks

1. The `_build_timestamp_mapping` provides per-message timestamps. Skipping it for summaries is safe, but for full history view we should keep it. Need to verify that the checkpoint's own `ts` field is a reasonable fallback for the last-activity timestamp.
2. Checking interrupts without creating a full agent - need to verify that `checkpointer.aget()` state contains interrupt info directly, or if we need the agent's `aget_state()` method.
3. `asyncio.gather()` for concurrent summary fetching could hit DB connection pool limits if there are many threads. The pagination (limit=5) helps, but we should still be careful.
