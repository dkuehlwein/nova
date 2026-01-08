"""
Email Tool Interface Configuration

Defines the mapping between abstract email operations and concrete MCP tool names.
This allows swapping email providers (Gmail, IMAP, etc.) without changing core email processing logic.
"""

# Email interface mapping: abstract operation -> possible concrete tool names
EMAIL_TOOL_INTERFACE = {
    # List/fetch emails operation
    "list_emails": [
        "gmail_get_unread_emails",  # Google Workspace MCP (gmail_ prefixed)
        "get_unread_emails",        # Legacy naming
        "list_messages",            # Generic Gmail API
        "fetch_emails",             # IMAP MCP
        "list_inbox_emails"         # Alternative naming
    ],

    # Get single email content operation
    "get_email": [
        "gmail_read_email",         # Google Workspace MCP (gmail_ prefixed)
        "read_email_content",       # Legacy naming
        "get_message",              # Generic Gmail API
        "fetch_email",              # IMAP MCP
        "get_email_content"         # Alternative naming
    ],

    # List email labels/folders operation
    "list_labels": [
        "gmail_list_labels",        # Google Workspace MCP (gmail_ prefixed)
        "list_gmail_labels",        # Legacy naming
        "list_labels",              # Generic Gmail API
        "list_folders",             # IMAP MCP
        "get_labels"                # Alternative naming
    ],

    # Send email operation (for future use)
    "send_email": [
        "gmail_send_email",         # Google Workspace MCP (gmail_ prefixed)
        "send_email",               # Legacy naming
        "compose_email",            # Alternative naming
        "send_message"              # Generic naming
    ],

    # Mark email as read operation (for future use)
    "mark_read": [
        "gmail_mark_as_read",       # Google Workspace MCP (gmail_ prefixed)
        "mark_email_as_read",       # Legacy naming
        "mark_read",                # Generic naming
        "set_read_status"           # Alternative naming
    ]
}

# Tool parameter mapping: abstract parameter -> concrete parameter names by tool
EMAIL_TOOL_PARAMETERS = {
    "get_unread_emails": {
        # Google Workspace MCP parameters
    },
    "read_email_content": {
        "message_id": "email_id"  # Google Workspace expects email_id, not message_id
    },
    "get_message": {
        "message_id": "id"  # Generic Gmail API expects id
    },
    "fetch_email": {
        "message_id": "email_id"  # IMAP might expect email_id
    },
    "list_messages": {
        # Generic Gmail API parameters
    }
}