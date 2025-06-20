# Google Workspace MCP Server

A comprehensive Model Context Protocol (MCP) server that provides access to Google Workspace services including Gmail and Google Calendar.

## Features

### Gmail Integration
- Send emails to multiple recipients
- Read and manage inbox (unread emails, mark as read, trash)
- Create and manage draft emails
- Label management (create, apply, remove, rename, delete)
- Email filtering and searching
- Email archiving and restoration
- Folder management (Gmail labels as folders)
- Batch operations for bulk email management

### Google Calendar Integration
- List all accessible calendars
- Create, read, update, and delete calendar events
- Natural language event creation using Quick Add
- Event management with attendees, location, and descriptions
- Time zone support (defaults to Europe/Berlin for Daniel)
- Upcoming events retrieval with filtering

## Setup

### Prerequisites
1. **Google Cloud Project**: Set up a project with Gmail and Calendar APIs enabled
2. **OAuth 2.0 Credentials**: Download `credentials.json` from Google Cloud Console
3. **Python 3.12+**: Required for the server

### Google Cloud Console Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the following APIs:
   - Gmail API: `https://console.cloud.google.com/apis/library/gmail.googleapis.com`
   - Calendar API: `https://console.cloud.google.com/apis/library/calendar-json.googleapis.com`
4. Configure OAuth consent screen:
   - Set application type to "Desktop application"
   - Add your email to test users during development
5. Create OAuth 2.0 Client ID credentials:
   - Application type: Desktop app
   - Download as `credentials.json`

### Required Scopes
The server automatically requests these OAuth scopes:
- `https://www.googleapis.com/auth/gmail.modify` - Gmail access
- `https://www.googleapis.com/auth/calendar` - Calendar access

### Installation
```bash
cd mcp_servers/gmail
pip install -r requirements.txt
```

### Running the Server
```bash
python main.py \
  --creds-file-path /path/to/credentials.json \
  --token-path /path/to/token.json \
  --host 127.0.0.1 \
  --port 8002 \
  --oauth-port 9000
```

### First-Time Authentication
1. Run the server - it will open a browser for OAuth
2. Sign in with your Google account
3. Grant permissions for Gmail and Calendar access
4. The server will save tokens for future use

### WSL2 Troubleshooting
If OAuth fails in WSL2, try these solutions:
1. Restart WSL2: `wsl --shutdown` (from Windows PowerShell as Admin)
2. Use WSL2 IP instead of localhost in OAuth flow
3. Configure Windows Firewall for WSL2
4. Temporarily disable IP Helper service

## Available Tools

### Gmail Tools
- `send_email(recipient_ids, subject, message)` - Send email
- `get_unread_emails()` - Get unread emails from inbox
- `read_email_content(email_id)` - Read specific email content
- `mark_email_as_read(email_id)` - Mark email as read
- `trash_email(email_id)` - Move email to trash
- `create_draft_email(recipient_ids, subject, message)` - Create draft
- `list_draft_emails()` - List all drafts
- `search_all_emails(query, max_results)` - Search with Gmail syntax
- `archive_email(email_id)` - Archive email
- `restore_email_to_inbox(email_id)` - Restore from archive
- `batch_archive_emails(query, max_emails)` - Bulk archive

### Label Management
- `list_gmail_labels()` - List all labels
- `create_new_label(label_name)` - Create label
- `apply_label_to_email(email_id, label_id)` - Apply label
- `remove_label_from_email(email_id, label_id)` - Remove label
- `rename_gmail_label(label_id, new_name)` - Rename label
- `delete_gmail_label(label_id)` - Delete label
- `search_emails_by_label(label_id)` - Find emails by label

### Filter Management
- `list_email_filters()` - List all filters
- `get_email_filter_details(filter_id)` - Get filter config
- `create_new_email_filter(criteria..., actions...)` - Create filter
- `delete_email_filter(filter_id)` - Delete filter

### Folder Management
- `list_email_folders()` - List user-created folders
- `create_new_folder(folder_name)` - Create folder
- `move_email_to_folder(email_id, folder_id)` - Move to folder

### Calendar Tools
- `list_calendars()` - List accessible calendars
- `create_calendar_event(calendar_id, summary, start_datetime, end_datetime, ...)` - Create event
- `list_calendar_events(calendar_id, max_results, time_min)` - List upcoming events
- `get_calendar_event(calendar_id, event_id)` - Get event details
- `update_calendar_event(calendar_id, event_id, ...)` - Update event
- `delete_calendar_event(calendar_id, event_id)` - Delete event
- `create_quick_calendar_event(calendar_id, text)` - Natural language event creation

## Configuration for Nova

Add to your `configs/mcp_servers.yaml`:

```yaml
google-workspace:
  command: python
  args:
    - mcp_servers/gmail/main.py
    - --creds-file-path
    - /path/to/your/credentials.json
    - --token-path  
    - /path/to/your/token.json
    - --host
    - 127.0.0.1
    - --port
    - 8002
  env: {}
```

## Health Check
The server provides a health check endpoint at `/health` that returns:
- Server status and version
- Service type (google-workspace-mcp-server)
- Connected Gmail user email
- MCP endpoint information

## Time Zone Configuration
The calendar functionality defaults to `Europe/Berlin` timezone for Daniel. This can be customized in the `create_event` and `update_event` methods.

## Error Handling
All tools include comprehensive error handling and return structured error responses when operations fail. Check the `status` field in responses for error conditions.

## Development
The server uses FastMCP for the MCP protocol implementation and Google's official API client libraries for workspace integration.
