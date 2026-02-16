# NOV-123: Auto-authenticate MS Graph via Playwright Browser Automation

**Linear ticket**: NOV-123
**Blocked by**: NOV-122 (merged)

## Investigation / Analysis

### Current State

**NOV-122 (auth detection)**: When an MS Graph MCP tool call returns a 401/403, `MSGraphService.handle_tool_error()` now returns a structured error dict:
```python
{"error": "MS Graph authentication required...", "auth_required": True, "auth_url": "http://localhost:8400/auth/start"}
```
This error flows back through LiteLLM MCP gateway to the Nova agent as tool output. The agent then tells the user to visit the auth URL manually.

**LAM browser automation** (`backend/skills/add_user_to_coe_gitlab/lam_automation.py`): Provides a proven pattern for persistent Playwright browser contexts:
- `_get_browser_cache()` - Process-level cache in `sys.modules` (survives module re-imports)
- `_get_or_create_browser_context()` - Creates/reuses persistent Chromium context with `user_data_dir`
- `_restore_sso_cookies()` / `_save_sso_cookies()` - Saves/restores SSO session cookies that Chromium doesn't persist
- `close_lam_browser()` - Cleanup
- Handles corrupt profile retry, dead context detection, headless mode

**MS Graph auth flow**: OAuth 2.0 authorization code flow using MSAL. The MCP server has:
- `/auth/start` - Shows "Sign in with Microsoft" button that redirects to Azure AD
- `/callback` - Handles the OAuth code exchange via `MSGraphAuth.complete_auth_flow()`
- Token cache stored at `MS_GRAPH_TOKEN_CACHE_PATH` (file-based MSAL cache)

### Key Insight: Where Auto-Auth Should Live

The auto-auth must happen on the Nova backend side (not in the MCP server). The flow is:
1. Agent calls an MS Graph MCP tool (e.g., `list_emails`)
2. LiteLLM routes to the MS Graph MCP server
3. MCP server returns `auth_required: true` with `auth_url`
4. Tool result flows back to Nova agent
5. **NEW**: Nova intercepts this and launches Playwright to complete the OAuth flow
6. After auth succeeds, Nova retries the original tool call

The interception point is in `mcp_client.py` at `MCPClientManager.call_mcp_tool()`, where the tool response is parsed. When `auth_required` is detected, we trigger the browser automation.

### The OAuth Browser Flow

The MS Graph MCP server's `/auth/start` endpoint does:
1. Returns an HTML page with a "Sign in with Microsoft" link
2. The link goes to `https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?...`
3. User signs in at Microsoft (may need MFA)
4. Microsoft redirects to `/callback?code=...&state=...`
5. MCP server exchanges the code for tokens via MSAL

For Playwright automation:
1. Navigate to `http://localhost:8400/auth/start`
2. Click the "Sign in with Microsoft" button/link
3. Wait for Microsoft login page
4. User may need to enter credentials + MFA (browser must be visible)
5. Wait for redirect back to `/callback`
6. Wait for the success page ("Authentication Successful!")

### Shared Utility Design

The LAM browser code has two concerns mixed together:
1. **Browser infrastructure** - persistent context, cache, cookie save/restore (reusable)
2. **LAM-specific logic** - URL building, form filling, account creation (skill-specific)

The shared utility should extract concern #1 into `backend/utils/browser_automation.py`.

## Approach

### Phase 1: Extract shared browser utility

Create `backend/utils/browser_automation.py` with:
- `BrowserManager` class that handles persistent browser contexts
- Parameterized by a `namespace` (e.g., "lam", "ms-graph") to isolate profile dirs and cookie storage
- Reusable methods: `get_or_create_context()`, `save_cookies()`, `restore_cookies()`, `close()`
- Process-level cache using the same `sys.modules` trick

### Phase 2: Refactor LAM automation to use shared utility

Update `lam_automation.py` to import from `utils.browser_automation` instead of having its own browser management. All LAM-specific logic stays in `lam_automation.py`.

### Phase 3: Build MS Graph auto-auth

Create `backend/utils/ms_graph_auth_browser.py` with:
- `authenticate_ms_graph(auth_url: str)` - Opens browser, navigates to auth start, waits for OAuth completion
- Uses `BrowserManager("ms-graph")` for persistent context
- Waits for the success page after callback
- Returns success/failure

### Phase 4: Integrate with MCP tool calls

Modify `mcp_client.py` `MCPClientManager.call_mcp_tool()` to:
- Detect `auth_required` in tool response
- Call `authenticate_ms_graph()` when detected
- Retry the original tool call after successful auth
- Return the retry result (or the auth error if auth fails)

### Phase 5: Tests

Unit tests for:
- `BrowserManager` creates and caches persistent context (mocked Playwright)
- Cookie save/restore works for different namespaces
- LAM automation still works with shared utility (regression)
- MS Graph auth flow detection and retry logic in `call_mcp_tool`

## Key Files to Modify

| File | Change |
|------|--------|
| `backend/utils/browser_automation.py` | **NEW** - Shared Playwright browser utility |
| `backend/utils/ms_graph_auth_browser.py` | **NEW** - MS Graph OAuth browser automation |
| `backend/skills/add_user_to_coe_gitlab/lam_automation.py` | Refactor to use shared utility |
| `backend/mcp_client.py` | Add auth detection + auto-auth + retry in `call_mcp_tool()` |
| `tests/unit/test_browser_automation.py` | **NEW** - Tests for shared browser utility |
| `tests/unit/test_ms_graph_auth_browser.py` | **NEW** - Tests for MS Graph auto-auth |
| `tests/unit/skills/test_add_user_to_coe_gitlab.py` | Add/update tests for refactored LAM |

## Design Decisions

1. **Namespace-based isolation**: Each consumer (LAM, MS Graph) gets its own profile directory and cookie storage, so they don't interfere with each other.

2. **Auto-retry in mcp_client.py**: The auth + retry happens transparently at the MCP client level. The agent doesn't need to know about the browser automation -- it just gets the tool result (either success after auto-auth, or an error if auth fails).

3. **Non-headless by default**: OAuth flows require user interaction (MFA, consent). The browser must be visible. This matches the existing LAM pattern.

4. **Single retry**: After successful auth, retry the tool call once. If it still fails, return the error to the agent.

5. **Cookie filtering**: When restoring cookies for MS Graph, filter by Microsoft domains. The LAM code already does similar filtering by LAM hostname.

## Open Questions / Risks

1. **MFA dependency**: The user must be at the computer to complete MFA. The browser will wait (with a configurable timeout, default 2 minutes). If the user isn't available, the tool call will time out.

2. **Headless environments**: In Docker/CI, headless browser can't do interactive MFA. This feature is designed for local development use. May need to skip auto-auth and fall back to the manual URL message when running headless.

3. **Race condition**: If multiple tool calls fail with auth errors simultaneously, we should only launch one browser session. The `BrowserManager` cache handles this naturally since the context is shared.

4. **LiteLLM response format**: Need to verify that `auth_required` and `auth_url` survive the LiteLLM MCP gateway round-trip. The response comes back as a text content block in MCP format, then parsed in `call_mcp_tool()`. Will need to handle JSON parsing of the text content.
