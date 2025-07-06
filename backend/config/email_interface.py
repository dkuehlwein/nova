"""
Email Tool Interface Configuration

Defines the mapping between abstract email operations and concrete MCP tool names.
This allows swapping email providers (Gmail, IMAP, etc.) without changing core email processing logic.
"""

# Email interface mapping: abstract operation -> possible concrete tool names
EMAIL_TOOL_INTERFACE = {
    # List/fetch emails operation
    "list_emails": [
        "get_unread_emails",    # Google Workspace MCP
        "list_messages",        # Generic Gmail API
        "fetch_emails",         # IMAP MCP
        "list_inbox_emails"     # Alternative naming
    ],
    
    # Get single email content operation  
    "get_email": [
        "read_email_content",   # Google Workspace MCP
        "get_message",          # Generic Gmail API
        "fetch_email",          # IMAP MCP
        "get_email_content"     # Alternative naming
    ],
    
    # List email labels/folders operation
    "list_labels": [
        "list_gmail_labels",    # Google Workspace MCP
        "list_labels",          # Generic Gmail API
        "list_folders",         # IMAP MCP
        "get_labels"            # Alternative naming
    ],
    
    # Send email operation (for future use)
    "send_email": [
        "send_email",           # Google Workspace MCP
        "compose_email",        # Alternative naming
        "send_message"          # Generic naming
    ],
    
    # Mark email as read operation (for future use)
    "mark_read": [
        "mark_email_as_read",   # Google Workspace MCP
        "mark_read",            # Generic naming
        "set_read_status"       # Alternative naming
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