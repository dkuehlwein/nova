# ADR-019: Browser Automation Caching

**Status**: Implemented
**Date**: 2026-02-16

> **Implementation Notes**: Shared utility in `backend/utils/browser_automation.py` (BrowserManager class). Consumers: LAM automation (`backend/skills/add_user_to_coe_gitlab/lam_automation.py`), MS Graph auto-auth (`backend/utils/ms_graph_auth_browser.py`). Originally introduced in NOV-120, extracted into shared utility in NOV-123.

---

## Context

Nova uses Playwright browser automation for two distinct flows: creating LDAP accounts via LAM (a skill) and completing MS Graph OAuth flows (MCP tool authentication). Both require persistent browser state across multiple agent tool invocations within a process lifetime.

The challenge is Nova's skill loader, which re-imports tool modules on every invocation. Standard Python caching mechanisms (module-level globals, class attributes) are wiped on re-import. This means a browser launched for one tool call would be lost by the next call, forcing the user to repeat MFA/SSO authentication each time.

Additionally, browser state must survive beyond the in-memory process. Chromium session cookies and certificate selections live only in memory by default -- restarting the backend process would also lose authentication state.

## Decision

Implement a **namespace-isolated BrowserManager** that uses three layers of persistence:

1. **Process-level cache via `sys.modules`**: Browser contexts are stored as synthetic entries in Python's `sys.modules` dict, keyed by namespace (e.g., `_nova_browser_lam`). Unlike module globals, `sys.modules` entries survive module re-imports, keeping the browser alive across tool calls within the same process.

2. **Persistent Chromium profiles**: Each namespace gets a dedicated `user_data_dir` at `~/.cache/nova/{namespace}-chromium-profile/`. Chromium persists standard cookies, localStorage, and certificate selections to this directory automatically.

3. **Explicit cookie save/restore**: Session cookies (marked `session`-only by identity providers) are not written to Chromium's profile directory. BrowserManager saves the full cookie jar to `~/.cache/nova/{namespace}-sso-state.json` via Playwright's `storage_state()` API, and restores them on context creation. This bridges process restarts for SSO/MFA cookies.

## Architecture

```
Agent Tool Call
      |
      v
BrowserManager("namespace")
      |
      +---> sys.modules cache hit?
      |         |
      |    Yes: reuse context
      |    No:  create new
      |              |
      |              v
      |         Chromium persistent context
      |         (user_data_dir on disk)
      |              |
      |              v
      |         Restore session cookies
      |         from {namespace}-sso-state.json
      |
      v
  Return context
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| BrowserManager | `backend/utils/browser_automation.py` | Shared persistent browser context with namespace isolation |
| LAM consumer | `backend/skills/add_user_to_coe_gitlab/lam_automation.py` | Uses `BrowserManager("lam")` for LDAP account creation |
| MS Graph consumer | `backend/utils/ms_graph_auth_browser.py` | Uses `BrowserManager("ms-graph")` for OAuth auto-auth |
| Profile storage | `~/.cache/nova/{namespace}-chromium-profile/` | Chromium persistent profile directory |
| Cookie storage | `~/.cache/nova/{namespace}-sso-state.json` | Saved session cookies for cross-restart persistence |

## Design Details

### Why sys.modules, Not Globals or Singletons

Module-level globals are cleared when the skill loader re-imports the module. A singleton class with a class-level cache has the same problem -- the class itself is re-created on re-import. `sys.modules` is the one Python namespace that persists across imports within a process, making it the correct place for process-lifetime state that must survive re-imports.

The cache entries use a `types.SimpleNamespace` to hold the Playwright instance and browser context, stored under keys like `_nova_browser_lam`. These keys are unlikely to collide with real module names.

### Namespace Isolation

Each consumer creates a `BrowserManager` with a unique namespace string. This provides complete isolation: separate Chromium profiles (different cookies, certs, localStorage), separate cookie backup files, and separate cache entries. LAM and MS Graph browser sessions never interfere with each other.

### Cookie Domain Filtering

When restoring cookies, consumers can exclude specific domains. LAM excludes its own hostname to avoid stale LAM session cookies while preserving SSO/PingOne cookies. This prevents authentication loops caused by expired application-level sessions.

### Corrupt Profile Recovery

If a persistent context fails to launch (corrupt Chromium profile), BrowserManager wipes the profile directory and retries once. This handles cases where an unclean shutdown left the profile in an inconsistent state.

## Consequences

### Positive

- Browser contexts survive module re-imports across agent tool calls
- Users complete MFA/SSO once per process session, not once per tool call
- SSO cookies survive backend restarts via explicit cookie save/restore
- New consumers can adopt the pattern by creating a `BrowserManager` with a new namespace
- No external state management service required (file-based, local only)

### Negative

- **Single-process only**: The `sys.modules` cache is per-process. Multiple backend workers would each maintain their own browser instance. This is acceptable for Nova's single-admin MVP architecture.
- **No multi-user support**: Browser profiles are per-namespace, not per-user. Only one user's SSO session is cached per namespace. Adequate for the current single-admin design.
- **Chromium dependency**: Requires `playwright install chromium` to be run separately. Playwright is a large dependency.
- **Non-headless default**: MFA flows require a visible browser, which limits use in containerized or CI environments. Consumers fall back to manual auth URL messages when headless.

### Risks

- **Profile disk growth**: Chromium profiles accumulate cache data over time. Mitigated by the corrupt-profile wipe mechanism and the fact that profiles are in `~/.cache/` (user-clearable).
- **Stale cookies**: Saved session cookies may expire between process restarts. The restore is best-effort; if cookies are invalid, the user simply re-authenticates.

## Related ADRs

- **ADR-015**: LiteLLM MCP Gateway Migration (MCP tool routing that triggers MS Graph auto-auth)
- **ADR-014**: Pluggable Skills System (skill loader re-import behavior that motivates the `sys.modules` cache)

---
*Last reviewed: 2026-02-16*
