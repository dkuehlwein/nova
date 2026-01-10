"""
Outlook Tool Interface Configuration

Defines the mapping between abstract email operations and Outlook MCP tool names.
The Outlook MCP server exposes tools via LiteLLM at outlook_mac server.

Tool Naming Convention (ADR-019):
- Email tools: prefixed with 'outlook_' (e.g., outlook_list_emails, outlook_read_email)
- Calendar tools: prefixed with 'outlook_cal_' (e.g., outlook_cal_list_events)
- Contact tools: prefixed with 'outlook_' (e.g., outlook_lookup_contact)

Note: mark_email_processed is NOT an MCP tool - it's an internal REST endpoint
called directly by the input hook to avoid polluting the LLM's tool context.
"""

# Outlook MCP server name (as registered in LiteLLM config)
OUTLOOK_MCP_SERVER = "outlook_mac"

# Outlook interface mapping: abstract operation -> MCP tool name
# Tool Naming Convention (ADR-019):
# - Email tools: prefixed with 'outlook_' (e.g., outlook_list_emails)
# - Calendar tools: prefixed with 'outlook_cal_' (e.g., outlook_cal_list_events)
OUTLOOK_TOOL_INTERFACE = {
    # List emails from inbox
    "list_emails": "outlook_list_emails",

    # Get single email content by ID
    "get_email": "outlook_read_email",

    # Calendar events
    "list_calendar_events": "outlook_cal_list_events",

    # Contact lookup
    "lookup_contact": "outlook_lookup_contact",
}

# Tool parameter mapping for Outlook
# Maps abstract parameter names to Outlook MCP expected names
OUTLOOK_TOOL_PARAMETERS = {
    "outlook_list_emails": {
        # list_emails uses: folder, limit, unread_only, exclude_processed
    },
    "outlook_read_email": {
        "message_id": "email_id"  # Map generic message_id to Outlook's email_id
    },
}

# Default parameters for Outlook tools
OUTLOOK_DEFAULT_PARAMETERS = {
    "outlook_list_emails": {
        "folder": "inbox",
        "limit": 50,
        "unread_only": False,
        "exclude_processed": True,  # By default, only fetch unprocessed emails
    }
}
