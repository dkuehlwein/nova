"""
Email Tool Interface Configuration

Defines the mapping between abstract email operations and concrete MCP tool names.
This allows swapping email providers (Gmail, Outlook, IMAP, etc.) without changing core email processing logic.

Tool Naming Convention (ADR-019):
- Gmail tools: prefixed with 'gmail_' (e.g., gmail_get_unread_emails)
- Outlook tools: prefixed with 'outlook_' (e.g., outlook_list_emails)
- Google Calendar tools: prefixed with 'gcal_' (e.g., gcal_list_events)
- Outlook Calendar tools: prefixed with 'outlook_cal_' (e.g., outlook_cal_list_events)
"""

# Email interface mapping: abstract operation -> possible concrete tool names
# Order matters: first matching tool wins
EMAIL_TOOL_INTERFACE = {
    # List/fetch emails operation
    "list_emails": [
        "gmail_get_unread_emails",  # Google Workspace MCP (preferred)
        "outlook_list_emails",      # Outlook Mac MCP
        # Legacy naming (deprecated - will be removed)
        "get_unread_emails",
        "list_emails",
        "list_messages",
        "fetch_emails",
    ],

    # Get single email content operation
    "get_email": [
        "gmail_read_email",         # Google Workspace MCP (preferred)
        "outlook_read_email",       # Outlook Mac MCP
        # Legacy naming (deprecated - will be removed)
        "read_email_content",
        "read_email",
        "get_message",
        "fetch_email",
    ],

    # List email labels/folders operation
    "list_labels": [
        "gmail_list_labels",        # Google Workspace MCP (preferred)
        # Legacy naming (deprecated - will be removed)
        "list_gmail_labels",
        "list_labels",
        "list_folders",
    ],

    # Send email operation
    "send_email": [
        "gmail_send_email",         # Google Workspace MCP (preferred)
        "outlook_send_email",       # Outlook Mac MCP
        # Legacy naming (deprecated - will be removed)
        "send_email",
        "compose_email",
    ],

    # Create draft email operation
    "create_draft": [
        "gmail_create_draft",       # Google Workspace MCP (preferred)
        "outlook_create_draft",     # Outlook Mac MCP
        # Legacy naming (deprecated - will be removed)
        "create_draft_email",
        "create_draft",
    ],

    # Mark email as read operation
    "mark_read": [
        "gmail_mark_as_read",       # Google Workspace MCP (preferred)
        # Legacy naming (deprecated - will be removed)
        "mark_email_as_read",
        "mark_read",
    ]
}

# Tool parameter mapping: abstract parameter -> concrete parameter names by tool
EMAIL_TOOL_PARAMETERS = {
    # Gmail tools
    "gmail_get_unread_emails": {},
    "gmail_read_email": {
        "message_id": "email_id"
    },
    "gmail_send_email": {
        "recipients": "recipient_ids"
    },
    "gmail_create_draft": {
        "recipients": "recipient_ids"
    },

    # Outlook tools
    "outlook_list_emails": {},
    "outlook_read_email": {
        "message_id": "email_id"
    },
    "outlook_send_email": {},
    "outlook_create_draft": {},

    # Legacy tool parameter mappings (deprecated)
    "get_unread_emails": {},
    "read_email_content": {
        "message_id": "email_id"
    },
    "get_message": {
        "message_id": "id"
    },
    "fetch_email": {
        "message_id": "email_id"
    },
}
