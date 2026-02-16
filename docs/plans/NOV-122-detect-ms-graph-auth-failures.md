# NOV-122: Detect MS Graph auth failures and surface clear error with auth URL

**Linear ticket:** NOV-122
**Branch:** feature/NOV-122-detect-ms-graph-auth-failures
**Blocks:** NOV-123 (Auto-authenticate MS Graph via Playwright browser automation)

## Investigation

### Current behavior
When MS Graph tokens expire or are missing, tool calls fail with unhelpful errors:
- `httpx.HTTPStatusError` from `response.raise_for_status()` gets caught by the generic `except Exception` handler in each tool method
- The error surfaces as e.g. `"Failed to look up contact: Client error '401 Unauthorized'..."` -- which is technically accurate but not actionable
- Downstream consumers (e.g., `resolve_participant_email` in `add_user_to_coe_gitlab/tools.py`) may further obscure the error into "Unexpected response format from MS Graph lookup"

### Code structure
Each tool class (`MailTools`, `CalendarTools`, `PeopleTools`) follows the same pattern:
1. Call `await self.service.ensure_client()` to get an authenticated httpx client
2. Make HTTP requests to MS Graph API
3. Call `response.raise_for_status()` which raises `httpx.HTTPStatusError` for 4xx/5xx
4. Catch-all `except Exception as e` returns `{"error": f"Failed to ...: {str(e)}"}`

The `ensure_client()` method in `MSGraphService` can also raise `RuntimeError` if not authenticated, but in the normal expired-token scenario, the client exists and the request simply gets a 401/403 back from MS Graph.

### Auth URL
The auth start URL is available at `http://localhost:8400/auth/start` (the MCP server's `/auth/start` endpoint). This is the URL users need to visit to re-authenticate.

The `MSGraphService` holds a reference to `self.auth` (an `MSGraphAuth` instance) which has `get_authorization_url()`, but calling that generates a new MSAL auth URL with a state nonce. For simplicity, we should point users to the `/auth/start` endpoint which handles the full flow with a nice HTML page.

The auth start URL can be constructed from the redirect URI: if redirect is `http://localhost:8400/callback`, the auth start is `http://localhost:8400/auth/start`.

## Approach

**Where to add auth detection:** In `MSGraphService` as a shared helper method, not in each tool class individually. This keeps the detection logic DRY and makes it available to all tool classes through `self.service`.

**What to detect:**
- `httpx.HTTPStatusError` where `response.status_code` is 401 or 403
- These indicate expired tokens, revoked consent, or insufficient permissions

**What to return:**
- A dict with `"error"` key containing a clear message about auth failure
- An `"auth_url"` key with the URL to re-authenticate
- An `"auth_required"` boolean flag for programmatic detection (useful for NOV-123)

**Auth URL construction:** Derive from `self.auth.redirect_uri` by replacing `/callback` with `/auth/start`. This avoids hardcoding and works regardless of host/port configuration.

**Non-auth errors:** Unchanged -- 404, 500, etc. continue to use the existing error format.

## Key files to modify

| File | Change |
|------|--------|
| `mcp_servers/ms_graph/src/service.py` | Add `is_auth_error()` and `auth_error_response()` helper methods |
| `mcp_servers/ms_graph/src/people_tools.py` | Catch auth errors before generic exception handler |
| `mcp_servers/ms_graph/src/mail_tools.py` | Same pattern |
| `mcp_servers/ms_graph/src/calendar_tools.py` | Same pattern |
| `mcp_servers/ms_graph/tests/test_auth_error_detection.py` | New test file |

## Open questions

- None. The approach is straightforward.
