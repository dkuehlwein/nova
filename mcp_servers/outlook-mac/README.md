# Outlook Mac MCP Server

MCP server for accessing local Microsoft Outlook on macOS via AppleScript.

## Overview

This server provides tools to interact with a locally installed Microsoft Outlook application on Mac using the AppleScript bridge (`appscript` library). It exposes email and calendar functionality as MCP tools.

## Requirements

- macOS with Microsoft Outlook installed
- Python 3.13+
- uv package manager
- Outlook must be running for the server to access it

## Why Host-Only? (Cannot Run in Docker)

This server uses AppleScript (`appscript` library) to communicate with the local Outlook application. It **cannot run in Docker** because:

1. AppleScript requires macOS (not Linux)
2. It needs access to the Mac's GUI/WindowServer
3. It must communicate with the locally running Outlook app

The server runs on the host machine and is accessed by LiteLLM via `host.docker.internal`.

## Tools

| Tool | Description |
|------|-------------|
| `list_emails` | List emails from inbox or specified folder |
| `read_email` | Read the full content of an email by ID |
| `create_draft` | Create a draft email (does not send) |
| `list_calendar_events` | List upcoming calendar events |

> **Note**: The server intentionally does not include `send_email` to require human oversight for outgoing emails.

## Installation

```bash
cd mcp_servers/outlook-mac
uv sync
```

## Running Manually

```bash
uv run python main.py --host 0.0.0.0 --port 9100
```

### Test the Server

```bash
# Health check
curl http://localhost:9100/health

# Tools count
curl http://localhost:9100/tools/count
```

## Running as a Service (launchd)

To run automatically on login, use the included launchd plist:

```bash
# Create a personalized plist (replace ${HOME} with your actual home directory)
sed "s|\${HOME}|$HOME|g" com.nova.outlook-mcp.plist > ~/Library/LaunchAgents/com.nova.outlook-mcp.plist

# Load the service
launchctl load ~/Library/LaunchAgents/com.nova.outlook-mcp.plist

# Start it now
launchctl start com.nova.outlook-mcp
```

### Service Management

```bash
# Check status
launchctl list | grep nova.outlook

# View logs
tail -f /tmp/nova-outlook-mcp.out.log
tail -f /tmp/nova-outlook-mcp.err.log

# Stop service
launchctl stop com.nova.outlook-mcp

# Unload service (stop and remove from startup)
launchctl unload ~/Library/LaunchAgents/com.nova.outlook-mcp.plist
```

## LiteLLM Integration

The server is registered in LiteLLM via `configs/litellm_config.yaml`:

```yaml
mcp_servers:
  outlook_mac:
    url: http://host.docker.internal:9100/mcp
    transport: http
    description: "Local Outlook for Mac - Email and Calendar (via AppleScript)"
```

LiteLLM (running in Docker) accesses the host-based service via `host.docker.internal`.

## Endpoints

- **MCP Endpoint**: `http://localhost:9100/mcp`
- **Health Check**: `http://localhost:9100/health`
- **Tools Count**: `http://localhost:9100/tools/count`

## Permissions

When first running, macOS may prompt for permission to control Outlook. Grant "Automation" permissions in System Settings > Privacy & Security > Automation.

## Troubleshooting

### "Could not connect to Outlook"

1. Make sure Outlook is running
2. Grant Terminal/IDE automation permissions in System Settings > Privacy & Security > Automation
3. You may need to grant Full Disk Access to Terminal/your IDE

### Port 9100 in use

Check what's using the port:
```bash
lsof -i :9100
```

Change to a different port if needed:
```bash
uv run python main.py --host 0.0.0.0 --port 9101
```

Then update `litellm_config.yaml` to match.
