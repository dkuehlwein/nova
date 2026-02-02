# MS Graph MCP Server

Microsoft 365 integration via MS Graph API for Nova.

## Features

- **Email**: List, read, create drafts, send emails
- **Calendar**: List, create, update, delete events
- **People**: Lookup contacts, search organization directory, get user profiles

## Setup

### 1. Azure AD App Registration

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. Create a new registration or use existing one
3. Add these **API permissions** (Delegated):
   - `User.Read` - Read user profile
   - `Mail.Read` - List and read emails
   - `Calendars.Read` - List calendar events
   - `Calendars.ReadWrite` - Create/update/delete events
   - `User.Read.All` - Search directory (requires admin consent)
4. Grant admin consent for permissions (required for `User.Read.All`)
5. Add **redirect URI**: `http://localhost:8400/callback`
6. Note your **Client ID** and **Tenant ID**
7. Create a **Client Secret** and note its value

### 2. Environment Variables

Add to your `.env` file:

```bash
MS_GRAPH_CLIENT_ID=your-client-id
MS_GRAPH_TENANT_ID=your-tenant-id
MS_GRAPH_CLIENT_SECRET=your-client-secret
```

### 3. Start the Server

```bash
# Build and start
docker-compose up -d --build ms-graph

# Check logs
docker-compose logs -f ms-graph

# Check health
curl http://localhost:8400/health
```

### 4. Authenticate

1. Check auth status: `curl http://localhost:8400/auth/status`
2. Start auth flow: `curl http://localhost:8400/auth/start`
3. Copy the `auth_url` and open in browser
4. Log in with your Microsoft account
5. Grant permissions when prompted
6. You'll be redirected to `/auth/callback` - success!

## Tools

| Tool | Description |
|------|-------------|
| `list_emails` | List emails from a folder |
| `read_email` | Read full email content |
| `create_draft` | Create a draft email |
| `send_email` | Send an email directly |
| `list_calendar_events` | List upcoming calendar events |
| `create_event` | Create a calendar event |
| `update_event` | Update an existing event |
| `delete_event` | Delete a calendar event |
| `lookup_contact` | Find email by person's name |
| `search_people` | Search organization directory |
| `get_user_profile` | Get user profile information |

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `/mcp` | MCP protocol endpoint (for LiteLLM) |
| `/health` | Health check |
| `/tools/count` | Tool count |
| `/auth/status` | Authentication status |
| `/auth/start` | Start OAuth flow |
| `/auth/callback` | OAuth callback handler |
| `/auth/logout` | Clear authentication |

## Token Lifecycle

- **Access tokens** expire after ~1 hour and are auto-refreshed
- **Refresh tokens** are valid for 90 days and roll forward on use
- Tokens are persisted in `credentials/token_cache.json`
- Container restarts preserve authentication state

## Development

```bash
# Install dependencies
cd mcp_servers/ms_graph
uv sync

# Run locally (not in Docker)
uv run python main.py --host 127.0.0.1 --port 8400

# Run tests
uv run pytest tests/ -v
```

## Testing Permissions

Before building, test that your Azure AD app has correct permissions:

```bash
cd backend && uv run python ../scripts/test_ms_graph_full.py
```

This script tests all required API endpoints and reports any permission issues.
