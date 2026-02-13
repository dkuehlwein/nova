"""
Email Tool Interface Configuration

Defines the mapping between abstract email operations and concrete MCP tool names.
This allows swapping email providers (Gmail, Outlook, IMAP, etc.) without changing core email processing logic.

Tool Naming Convention (ADR-015 MCP Tool Namespacing):
- All MCP tools are automatically prefixed with server_name-tool_name
- Google Workspace: google_workspace-send_email, google_workspace-get_unread_emails
- Outlook Mac: outlook_mac-send_email, outlook_mac-list_emails
"""

# Email interface mapping: abstract operation -> possible concrete tool names
# Order matters: first matching tool wins
EMAIL_TOOL_INTERFACE = {
    # List/fetch emails operation
    "list_emails": [
        "google_workspace-get_unread_emails",  # Google Workspace MCP (preferred)
        "outlook_mac-list_emails",             # Outlook Mac MCP
    ],

    # Get single email content operation
    "get_email": [
        "google_workspace-read_email",         # Google Workspace MCP (preferred)
        "outlook_mac-read_email",              # Outlook Mac MCP
    ],

    # List email labels/folders operation
    "list_labels": [
        "google_workspace-list_labels",        # Google Workspace MCP (preferred)
    ],

    # Send email operation
    "send_email": [
        "google_workspace-send_email",         # Google Workspace MCP (preferred)
        "outlook_mac-send_email",              # Outlook Mac MCP
    ],

    # Create draft email operation
    "create_draft": [
        "google_workspace-create_draft",       # Google Workspace MCP (preferred)
        "outlook_mac-create_draft",            # Outlook Mac MCP
    ],

    # Mark email as read operation
    "mark_read": [
        "google_workspace-mark_as_read",       # Google Workspace MCP (preferred)
    ]
}

# Tool parameter mapping: abstract parameter -> concrete parameter names by tool
EMAIL_TOOL_PARAMETERS = {
    # Google Workspace tools (prefixed per ADR-015)
    "google_workspace-get_unread_emails": {},
    "google_workspace-read_email": {
        "message_id": "email_id"
    },
    "google_workspace-send_email": {},
    "google_workspace-create_draft": {},

    # Outlook Mac tools (prefixed per ADR-015)
    "outlook_mac-list_emails": {},
    "outlook_mac-read_email": {
        "message_id": "email_id"
    },
    "outlook_mac-send_email": {},
    "outlook_mac-create_draft": {},
}
