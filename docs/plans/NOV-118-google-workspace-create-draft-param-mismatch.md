# NOV-118: Fix google_workspace-create_draft parameter mismatch

**Linear ticket:** NOV-118

## Investigation / Analysis

The `google_workspace-create_draft` MCP tool fails with validation errors because the LLM sends `recipients` and `body`, but the tool schema expects `recipient_ids` and `message`.

### Root Cause

The google-workspace MCP server uses different parameter names than the ms_graph and outlook-mac servers:

| Parameter | google-workspace | ms_graph / outlook-mac |
|-----------|-----------------|----------------------|
| Recipients | `recipient_ids` | `recipients` |
| Email body | `message` | `body` |

The LLM naturally uses `recipients` and `body` because those are the names used by the other email MCP servers (and are more intuitive names in general).

The mismatch exists in two layers:
1. `main.py` - the `@mcp.tool()` decorated functions (MCP schema exposed to LiteLLM/LLM)
2. `gmail_tools.py` - the `GmailTools` class methods (internal implementation)

The same mismatch affects both `create_draft` and `send_email`.

## Approach

Rename parameters in both the MCP tool definitions (`main.py`) and the underlying `GmailTools` class (`gmail_tools.py`) to match the convention used by ms_graph and outlook-mac:
- `recipient_ids` -> `recipients`
- `message` -> `body`

This is the simplest fix: align parameter names at both layers so the schema matches what the LLM sends and is consistent across all email MCP servers.

### Why not just rename at the MCP layer?

We could rename only in `main.py` and map parameters when calling `gmail_tools`. But renaming at both layers is cleaner - no mapping needed, consistent naming throughout, and the existing tests already use `to`/`body` through the `service.py` wrapper anyway.

## Key Files to Modify

- `mcp_servers/google-workspace/main.py` - MCP tool definitions (both `create_draft` and `send_email`)
- `mcp_servers/google-workspace/src/main.py` - Same MCP tool definitions (production entry point)
- `mcp_servers/google-workspace/src/gmail_tools.py` - `GmailTools.create_draft()` and `send_email()` method signatures

## Open Questions / Risks

- The `service.py` wrapper already uses `to`/`body` and converts to `recipients` list before calling `gmail_tools`. After renaming, the service.py calls remain valid since it passes positional args or the renamed kwargs match.
- Existing tests in `test_gmail.py` call through `service.py` (which uses `to`/`body`), so they should still pass after the rename.
