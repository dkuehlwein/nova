# Nova Chat Page Review

**Date:** 2026-02-04
**Reviewer:** Claude (as programmer, designer, user)

---

## Issues Identified by User

### 1. Tool Names Not Selectable/Copyable
**Problem:** Can't select/copy tool names when debugging issues.

**Current behavior:** Tool names in "Using tool: X" are rendered as plain text within a styled container, making selection difficult.

**Fix:** Make tool names a selectable `<code>` element or add a copy button.

```tsx
// In CollapsibleToolCall.tsx
<span className="font-mono select-all cursor-text">
  {toolName}
</span>
<button onClick={() => navigator.clipboard.writeText(toolName)} aria-label="Copy tool name">
  <CopyIcon />
</button>
```

### 2. Tool Approval UI Disappears on Chat Reload
**Problem:** After approving a tool, the approval indicator vanishes when chat is reloaded from history.

**Root cause:** Tool approval decisions are not persisted with messages or rendered differently in loaded vs. live chats.

**Fix options:**
1. Store approval decisions in message metadata
2. Render a collapsed "✓ Tool approved" indicator for historical tool calls
3. Keep the same visual treatment but mark as "approved" with a checkmark

### 3. "Thinking" Numbers Are Unnecessary
**Problem:** "Thinking (1)", "Thinking (2)" etc. don't add value. User wants to read actual thoughts, not count them.

**Fix:** Remove the numbers, just show "Thinking" with expand/collapse. Or better: show first line of thinking as preview.

---

## Code Quality Issues

### Critical: useChat.ts is 1,022 Lines
**File:** `frontend/src/hooks/useChat.ts`

**Problems:**
- Violates single responsibility principle
- Streaming logic (~450 lines) mixed with state management
- Tool call buffering duplicated in 3 places (lines 357-411, 510-553)
- Hard to test in isolation

**Recommended refactor:** Extract the duplicated buffered tool call processing (lines 357-411 and 510-553) into a single helper function. Keep the hook unified but better organized with clear sections. Splitting into multiple hooks may just move complexity around without reducing it - the streaming state machine logic is inherently coupled.

### High: MarkdownMessage.tsx Complex Parsing (318 Lines)
**File:** `frontend/src/components/chat/MarkdownMessage.tsx`

**Problems:**
- Regex-based `<think>` tag parsing inline with rendering
- Tool marker replacement `[[TOOL:N]]` not memoized
- `parseContentIntoParts()` runs every render

**Fix:** Extract to `contentParser.ts` utility, wrap with `useMemo()`.

### High: Prop Drilling in page.tsx
**File:** `frontend/src/app/chat/page.tsx` (lines 150-176)

15+ props passed to `ChatMessageList`. Use React Context for:
- Message action handlers (copy, rate, regenerate)
- Escalation handlers
- UI state (copiedMessageId, ratedMessages)

### Low: Message Ratings Not Persisted (Future Work)
**File:** `frontend/src/hooks/useChatMessage.ts` (line 40)

```typescript
// TODO: Send rating to backend for analytics
```

Ratings lost on page refresh. Not critical for current work package - defer to future iteration.

### Medium: Race Condition in Chat Loading
**File:** `frontend/src/hooks/useChatPage.ts` (lines 226-265)

```typescript
fetchTaskInfo();  // Not awaited
loadTaskChat(taskParam);  // Async
router.push(newUrl);  // URL updates before data loads
```

**Fix:** Await data loading before URL update.

### Medium: Hardcoded Connection Status
**File:** `frontend/src/hooks/useChat.ts` (line 95)

```typescript
isConnected: true, // Start as connected to avoid initial health check
```

No actual backend health check on mount.

### Low: Console Warnings
Browser shows "Unknown event type: hook_processing_started" - should be silently handled.

---

## Additional Code Quality Issues (Architectural Review)

### Medium: Type Duplication
The `ToolCall` interface is defined in both:
- `frontend/src/hooks/useChat.ts` (lines 4-10)
- `frontend/src/components/chat/MarkdownMessage.tsx` (lines 9-15)

**Fix:** Extract to a shared types file (e.g., `frontend/src/types/chat.ts`) and import from both locations.

### Low: Memory Leak Potential in Streaming
The streaming logic in `useChat.ts` uses refs and callbacks that may not clean up properly if the component unmounts mid-stream. The `abortControllerRef` exists but cleanup paths during unmount should be verified.

### Low: Streaming Performance (Future Optimization)
Each SSE event triggers a separate `setState` call, causing a re-render per token/chunk. During fast streaming, this can cause UI jank on slower devices.

**Future optimization options (not for current WP):**
- Batch state updates and flush every 100ms
- Use `useReducer` for better batching of complex state
- Use React 18's `startTransition` to mark streaming updates as non-urgent

---

## Chat History Naming Research

### Best Practice: Auto-Generate Titles with LLM

**Sources:**
- [ChatOllama Blog - Smart Title Generation](https://blog.chatollama.cloud/blog/2025-09-09-improving-ai-chat-experience-with-smart-title-generation/)
- [VideoSDK - LLM Real-Time Conversation](https://www.videosdk.live/developer-hub/llm/llm-for-real-time-conversation)

### When to Generate
Trigger after first meaningful AI response (message count = 2). This ensures:
- Sufficient context for accurate title
- Not wasted on abandoned chats
- Timely enough that user sees it

### What to Use as Input
Combine user's first message + AI's first response summary. This captures:
- User intent
- Actual topic discussed
- More accurate than first message alone

### Implementation Pattern
```typescript
class ConversationTitleGenerator {
  async generateTitle(conversationId: string, messages: Message[], maxLength = 50): Promise<string> {
    try {
      const prompt = `Generate a concise title (max ${maxLength} chars) for this conversation:
        User: ${messages[0].content}
        Assistant: ${messages[1].content.substring(0, 200)}

        Title should describe the topic, not be generic.`;

      const title = await llm.generate(prompt);
      return title.slice(0, maxLength);
    } catch {
      // Fallback cascade
      return this.extractKeywords(messages[0].content)
        || `Chat - ${new Date().toLocaleDateString()}`;
    }
  }
}
```

### Considerations for Nova
- **Timing:** Generate after first assistant response
- **Model:** Use a fast/cheap model (not the main chat model)
- **Updates:** Optionally update title if conversation topic shifts significantly
- **User override:** Allow manual title editing
- **Fallback:** Use date + first few words if LLM fails

### Nova-Specific Implementation
Title generation could incorporate:
- Topic from first exchange ("Adding users to GitLab")
- Skill activations if used ("add_user_to_coe_gitlab")

**Chat vs Task distinction:**
- Regular chats: Just need a descriptive title
- Task-linked chats: Could show task status badge in sidebar (already have task_id in chat history items)
- Consider showing a subtle indicator if a chat spawned a task or is linked to one

---

## Priority Summary

| Priority | Issue | Type | Effort |
|----------|-------|------|--------|
| **P0** | Approval UI disappears on reload | UX Bug | Medium |
| **P1** | Tool names not copyable | UX Bug | Small |
| **P1** | Refactor useChat.ts (1,022 lines) | Code Quality | Medium |
| **P2** | Remove "Thinking" numbers | UX | Small |
| **P2** | Auto-generate chat titles | Feature | Medium |
| **P2** | Extract MarkdownMessage parsing | Code Quality | Medium |
| **P2** | Fix chat loading race condition | Bug | Medium |
| **P2** | Fix type duplication (ToolCall) | Code Quality | Small |
| **P3** | Reduce prop drilling with Context | Code Quality | Medium |
| **P3** | Add actual connection health check | Reliability | Small |
| **P3** | Verify streaming cleanup on unmount | Reliability | Small |
| **Future** | Persist message ratings | Feature | Medium |
| **Future** | Batch streaming state updates | Performance | Medium |

---

## Files Referenced

- `frontend/src/hooks/useChat.ts` - Main chat hook (1,022 lines)
- `frontend/src/hooks/useChatPage.ts` - Page-level state (302 lines)
- `frontend/src/hooks/useChatMessage.ts` - Message interactions (50 lines)
- `frontend/src/app/chat/page.tsx` - Chat page component (204 lines)
- `frontend/src/components/chat/MarkdownMessage.tsx` - Message rendering (318 lines)
- `frontend/src/components/chat/ChatMessageBubble.tsx` - Message bubble (190 lines)
- `frontend/src/components/chat/CollapsibleToolCall.tsx` - Tool call display (78 lines)
- `frontend/src/components/chat/EscalationBox.tsx` - Decision UI (170 lines)
