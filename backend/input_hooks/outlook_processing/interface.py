"""
Outlook Tool Interface Configuration

Defines the mapping between abstract email operations and Outlook MCP tool names.
The Outlook MCP server exposes tools via LiteLLM at outlook_mac server.

Note: LiteLLM returns tools without server prefix. Tool names are:
  - list_emails (not outlook_mac__list_emails)
  - read_email (not outlook_mac__read_email)
  - mark_email_processed (not outlook_mac__mark_email_processed)
"""

# Outlook MCP server name (as registered in LiteLLM config)
OUTLOOK_MCP_SERVER = "outlook_mac"

# Outlook interface mapping: abstract operation -> MCP tool name
# LiteLLM returns tools without server prefix
OUTLOOK_TOOL_INTERFACE = {
    # List emails from inbox
    "list_emails": "list_emails",

    # Get single email content by ID
    "get_email": "read_email",

    # Mark email as processed (adds "Nova Processed" category)
    "mark_processed": "mark_email_processed",

    # Calendar events (for future use)
    "list_calendar_events": "list_calendar_events",
}

# Tool parameter mapping for Outlook
# Maps abstract parameter names to Outlook MCP expected names
OUTLOOK_TOOL_PARAMETERS = {
    "list_emails": {
        # list_emails uses: folder, limit, unread_only, exclude_processed
    },
    "read_email": {
        "message_id": "email_id"  # Map generic message_id to Outlook's email_id
    },
    "mark_email_processed": {
        "message_id": "email_id"  # Map generic message_id to Outlook's email_id
    },
}

# Default parameters for Outlook tools
OUTLOOK_DEFAULT_PARAMETERS = {
    "list_emails": {
        "folder": "inbox",
        "limit": 50,
        "unread_only": False,
        "exclude_processed": True,  # By default, only fetch unprocessed emails
    }
}
