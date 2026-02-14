# NOV-120: Persist PingOne SSO session across coe_gitlab skill invocations

**Linear ticket**: NOV-120
**Branch**: `feature/NOV-120-persist-pingone-sso-session`

## Investigation Notes

### Current Behavior

In `backend/skills/add_user_to_coe_gitlab/lam_automation.py`, the `create_lam_account()` function:

1. Launches a **fresh** Playwright Chromium browser on every call (line 153)
2. Creates a **new browser context** with no persistence (line 157)
3. Closes both context and browser in the `finally` block (lines 399-402)
4. This means all cookies, sessions, and auth state are **destroyed** after each call

The SSO flow (lines 170-188) detects PingOne SSO redirects and waits for the user to manually complete MFA. Because the browser profile is ephemeral, this MFA prompt appears on **every single** `create_iam_account` call, even within the same session.

### Reference: Playwright MCP Plugin

Claude Code's Playwright MCP plugin persists auth by using `launch_persistent_context()` with a `user_data_dir` at `~/Library/Caches/ms-playwright/mcp-chromium-profile/`. This stores cookies/session data on disk and reuses it across calls.

### Key Insight

Playwright offers two approaches for persistence:
1. **`launch_persistent_context(user_data_dir)`** - Uses a Chromium user data directory that persists cookies/localStorage between launches. This is the simplest approach and matches what the Playwright MCP plugin does.
2. **`storage_state` save/load** - Exports cookies and localStorage to a JSON file and re-imports on next context creation. More granular but more code.

Option 1 (persistent context) is simpler and proven to work for SSO scenarios. It also avoids the need to explicitly manage save/load lifecycle.

## Approach

### Use `browser.launch_persistent_context()` with a dedicated user_data_dir

**Changes to `lam_automation.py`:**

1. Define a cache directory: `~/.cache/nova/lam-chromium-profile/`
2. Replace `browser.launch()` + `browser.new_context()` with `chromium.launch_persistent_context(user_data_dir, ...)` which combines browser launch and context creation into a single step that persists cookies.
3. In the `finally` block, close only the context (persistent context has no separate browser object).
4. Keep the SSO detection logic as-is -- it will simply not trigger on subsequent calls because the SSO cookies are already present.

**Graceful fallback for stale/corrupt state:**

If the persistent context fails to launch (e.g., corrupt profile), catch the exception, delete the profile directory, and retry with a fresh profile. This handles the "stale cookie" acceptance criterion.

**No leakage between unrelated sessions:**

The profile is specific to this skill (`lam-chromium-profile`). It does not affect other skills or Playwright instances. The SSO session has its own natural expiry (controlled by PingOne server-side), so stale cookies will simply trigger a fresh SSO prompt -- no silent failures.

**Browser cleanup:**

`launch_persistent_context` returns a `BrowserContext` that, when closed, releases the browser process. The existing `finally` block pattern is preserved.

### Config addition

Add a `browser.profile_dir` option to `config.yaml.example` so admins can customize the profile location if needed. Default to `~/.cache/nova/lam-chromium-profile/`.

## Key Files to Modify

| File | Change |
|------|--------|
| `backend/skills/add_user_to_coe_gitlab/lam_automation.py` | Switch to `launch_persistent_context()`, add fallback logic |
| `backend/skills/add_user_to_coe_gitlab/config.yaml.example` | Add `browser.profile_dir` setting |
| `tests/unit/skills/test_add_user_to_coe_gitlab.py` | Add unit tests for storage state persistence behavior |

## Unit Tests

Tests will mock Playwright and verify:
1. `launch_persistent_context` is called with the correct `user_data_dir`
2. On corrupt profile (launch raises exception), the profile dir is deleted and retried
3. Context is properly closed in the `finally` block

## Open Questions / Risks

- **Lock file contention**: If two concurrent `create_iam_account` calls happen, they may fight over the profile directory. This is unlikely in the current single-user skill usage pattern, but worth noting. The existing Playwright MCP plugin has the same limitation.
- **Profile dir disk usage**: Chromium profiles can grow over time. The profile is small for cookie-only usage, but worth monitoring. Users can delete `~/.cache/nova/lam-chromium-profile/` to reset.
