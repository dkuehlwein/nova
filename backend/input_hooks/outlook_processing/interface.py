"""
Outlook Tool Interface Configuration

Defines the mapping between abstract email operations and Outlook MCP tool names.
The Outlook MCP server exposes tools via LiteLLM at outlook_mac server.

Tool Naming Convention (ADR-015 MCP Tool Namespacing):
- All MCP tools are automatically prefixed with server_name-tool_name
- Example: outlook_mac-list_emails, outlook_mac-read_email, outlook_mac-list_calendar_events

Note: mark_email_processed is NOT an MCP tool - it's an internal REST endpoint
called directly by the input hook to avoid polluting the LLM's tool context.
"""

# Outlook MCP server name (as registered in LiteLLM config)
OUTLOOK_MCP_SERVER = "outlook_mac"

# Outlook interface mapping: abstract operation -> MCP tool name (prefixed per ADR-015)
OUTLOOK_TOOL_INTERFACE = {
    # List emails from inbox
    "list_emails": "outlook_mac-list_emails",

    # Get single email content by ID
    "get_email": "outlook_mac-read_email",

    # Calendar events
    "list_calendar_events": "outlook_mac-list_calendar_events",

    # Contact lookup
    "lookup_contact": "outlook_mac-lookup_contact",
}

# Tool parameter mapping for Outlook
# Maps abstract parameter names to Outlook MCP expected names
OUTLOOK_TOOL_PARAMETERS = {
    "outlook_mac-list_emails": {
        # list_emails uses: folder, limit, unread_only, exclude_processed
    },
    "outlook_mac-read_email": {
        "message_id": "email_id"  # Map generic message_id to Outlook's email_id
    },
}

# Default parameters for Outlook tools
OUTLOOK_DEFAULT_PARAMETERS = {
    "outlook_mac-list_emails": {
        "folder": "inbox",
        "limit": 50,
        "unread_only": False,
        "exclude_processed": True,  # By default, only fetch unprocessed emails
    }
}
