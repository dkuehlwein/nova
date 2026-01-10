#!/usr/bin/env python3
"""
Google Workspace MCP Server - Gmail, Calendar, and productivity tools integration.

This is the main entry point for the Google Workspace MCP server that provides
access to Gmail and Google Calendar APIs through FastMCP.
"""

import argparse
import asyncio
import logging
import os
import subprocess
from datetime import datetime
from typing import List, Dict, Union, Optional, Any

from fastmcp import FastMCP
from fastapi.responses import JSONResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import our service class
from src.service import GoogleWorkspaceService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The GoogleWorkspaceService is now imported from src.service module


# --- FastMCP Server Setup ---
mcp = FastMCP(name="GoogleWorkspaceToolsServer")

def setup_tools(workspace_service: GoogleWorkspaceService):
    """Set up all the MCP tools for the workspace service.

    Tool Naming Convention:
    - Gmail tools are prefixed with 'gmail_' to avoid conflicts with other email providers
    - Calendar tools are prefixed with 'gcal_' to avoid conflicts with other calendar providers
    """

    # === Gmail Tools (prefixed with gmail_) ===

    @mcp.tool()
    async def gmail_send_email(recipient_ids: List[str], subject: str, message: str) -> Dict[str, str]:
        """Sends an email via Gmail to one or more recipients. Subject and message are distinct."""
        return await workspace_service.gmail_tools.send_email(recipient_ids, subject, message)

    @mcp.tool()
    async def gmail_get_unread_emails() -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Retrieves a list of unread emails from the Gmail primary inbox category."""
        return await workspace_service.gmail_tools.get_unread_emails()

    @mcp.tool()
    async def gmail_read_email(email_id: str) -> Dict[str, str]:
        """Retrieves the full content of a specific Gmail email and marks it as read."""
        return await workspace_service.gmail_tools.read_email(email_id)

    '''
    @mcp.tool()
    async def gmail_trash_email(email_id: str) -> Union[str, Dict[str, str]]:
        """Moves the specified Gmail email to the trash."""
        return await workspace_service.gmail_tools.trash_email(email_id)

    @mcp.tool()
    async def gmail_mark_as_read(email_id: str) -> Union[str, Dict[str, str]]:
        """Marks the specified Gmail email as read."""
        return await workspace_service.gmail_tools.mark_email_as_read(email_id)
    #'''

    @mcp.tool()
    async def gmail_create_draft(recipient_ids: List[str], subject: str, message: str) -> Dict[str, str]:
        """Creates a draft email message in Gmail for one or more recipients."""
        return await workspace_service.gmail_tools.create_draft(recipient_ids, subject, message)

    @mcp.tool()
    async def gmail_list_drafts() -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Lists all draft emails in Gmail with their ID, subject, and recipient."""
        return await workspace_service.gmail_tools.list_drafts()

    '''
    @mcp.tool()
    async def gmail_list_labels() -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Lists all labels in the Gmail mailbox."""
        return await workspace_service.gmail_tools.list_labels()

    @mcp.tool()
    async def gmail_create_label(label_name: str) -> Dict[str, str]:
        """Creates a new label in Gmail."""
        return await workspace_service.gmail_tools.create_label(label_name)
    #'''

    # === Google Calendar Tools (prefixed with gcal_) ===
    '''
    @mcp.tool()
    async def gcal_list_calendars() -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Lists all Google calendars accessible to the user."""
        return await workspace_service.calendar_tools.list_calendars()
    #'''

    @mcp.tool()
    async def gcal_create_event(calendar_id: str, summary: str, start_datetime: str,
                                end_datetime: str, description: str = "", location: str = "",
                                attendees: Optional[List[str]] = None) -> Dict[str, str]:
        """Creates a new Google Calendar event. Datetime format: 2025-06-06T10:00:00 (ISO format)"""
        return await workspace_service.calendar_tools.create_event(
            calendar_id, summary, start_datetime, end_datetime, description, location, attendees
        )

    @mcp.tool()
    async def gcal_list_events(calendar_id: str = 'primary', max_results: int = 50,
                               time_min: Optional[str] = None, time_max: Optional[str] = None) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """Lists upcoming events from a Google Calendar. If time_min not provided, uses current time."""
        return await workspace_service.calendar_tools.list_events(calendar_id, max_results, time_min, time_max)

    @mcp.tool()
    async def gcal_delete_event(calendar_id: str, event_id: str) -> Union[str, Dict[str, str]]:
        """Deletes a Google Calendar event by its ID."""
        return await workspace_service.calendar_tools.delete_event(calendar_id, event_id)

    '''
    @mcp.tool()
    async def create_quick_calendar_event(calendar_id: str, text: str) -> Dict[str, str]:
        """Creates an event using natural language. Example: 'Meeting with John tomorrow at 2pm'"""
        return await workspace_service.calendar_tools.create_quick_event(calendar_id, text)
    #'''
    # Health endpoint for server monitoring
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        return JSONResponse({
            "status": "healthy",
            "service": "google-workspace-mcp-server", 
            "version": "1.0.0",
            "timestamp": str(datetime.now()),
            "mcp_endpoint": "/mcp",
            "gmail_user": workspace_service.user_email,
            "tools_count": len(mcp._tools) if hasattr(mcp, '_tools') else 14  # Gmail: 10 tools, Calendar: 4 tools
        })

    # Tools count endpoint for Nova integration
    @mcp.custom_route("/tools/count", methods=["GET"])
    async def tools_count(request):
        tools_count = len(mcp._tools) if hasattr(mcp, '_tools') else 14
        return JSONResponse({
            "tools_count": tools_count,
            "gmail_tools": 10,
            "calendar_tools": 4,
            "total_tools": tools_count
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Google Workspace API FastMCP Server')
    parser.add_argument('--creds-file-path', required=True, help='OAuth 2.0 credentials file path (e.g., credentials.json)')
    parser.add_argument('--token-path', required=True, help='File location to store/retrieve access and refresh tokens (e.g., token.json)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=8002, help='Port to bind the server to')
    parser.add_argument('--oauth-port', type=int, default=9000, help='Port for OAuth flow')
    
    args = parser.parse_args()
    
    # Initialize GoogleWorkspaceService (which handles auth and core logic)
    workspace_service = GoogleWorkspaceService(args.creds_file_path, args.token_path)
    
    # Setup tools
    setup_tools(workspace_service)
    
    # --- Run FastMCP Server ---
    try:
        logger.info(f"Starting Google Workspace FastMCP server on http://{args.host}:{args.port}")
        logger.info(f"MCP endpoint: http://{args.host}:{args.port}/mcp")
        logger.info(f"Health endpoint: http://{args.host}:{args.port}/health")
        
        # Explicitly specify the path="/mcp" to ensure Nova compatibility
        mcp.run(transport="streamable-http", host=args.host, port=args.port, path="/mcp")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise 