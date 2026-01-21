#!/usr/bin/env python3
"""
Outlook Mac MCP Server - Access local MS Outlook on Mac via AppleScript.

This is the main entry point for the Outlook MCP server that provides
access to local Microsoft Outlook on macOS through FastMCP.
"""

import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from fastmcp import FastMCP
from fastapi.responses import JSONResponse

from src.outlook_service import OutlookService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastMCP Server Setup ---
mcp = FastMCP(name="OutlookMacServer")


def setup_tools(outlook_service: OutlookService):
    """Set up all the MCP tools for the Outlook service.

    Tool names are simple base names without prefixes.
    Nova's mcp_client.py automatically prefixes with server name (outlook_mac-).
    """

    # === Email Tools ===

    @mcp.tool()
    async def list_emails(
        folder: str = "inbox",
        limit: int = 20,
        unread_only: bool = False,
        exclude_processed: bool = False,
        since_date: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        List emails from the specified folder.

        Args:
            folder: Folder name to list emails from (default: inbox)
            limit: Maximum number of emails to return (default: 20)
            unread_only: If True, only return unread emails
            exclude_processed: If True, exclude emails already processed by Nova (have "Nova Processed" category)
            since_date: Only return emails received on or after this date (format: YYYY-MM-DD)

        Returns:
            List of email summaries with id, subject, sender, date, read status, and processing status
        """
        return await outlook_service.list_emails(folder, limit, unread_only, exclude_processed, since_date)

    @mcp.tool()
    async def read_email(email_id: Union[str, int]) -> Dict[str, Any]:
        """
        Read the full content of an email by its ID.

        Args:
            email_id: The unique identifier of the email to read (string or integer)

        Returns:
            Full email content including subject, sender, recipients, date, and body
        """
        return await outlook_service.read_email(str(email_id))

    @mcp.tool()
    async def create_draft(
        recipients: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a draft email. Does not send the email.

        Args:
            recipients: List of recipient email addresses
            subject: Email subject line
            body: Email body content (plain text)
            cc: Optional list of CC recipient email addresses

        Returns:
            Confirmation with draft ID
        """
        return await outlook_service.create_draft(recipients, subject, body, cc)

    @mcp.tool()
    async def send_email(
        recipients: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send an email directly. REQUIRES USER APPROVAL.

        This tool sends the email immediately without saving as draft first.
        Use create_draft if you want to prepare an email for user review before sending.

        Args:
            recipients: List of recipient email addresses
            subject: Email subject line
            body: Email body content (plain text)
            cc: Optional list of CC recipient email addresses

        Returns:
            Confirmation with send status including recipients and subject
        """
        return await outlook_service.send_email(recipients, subject, body, cc)

    # === Contact Lookup Tools ===

    @mcp.tool()
    async def lookup_contact(name: str) -> Dict[str, Any]:
        """
        Look up an email address for a person by name.

        Searches contacts and recent emails to find an email address
        for the given name. Useful for resolving names to emails when the
        user only provides names.

        Args:
            name: The person's name to look up (e.g., "John Doe")

        Returns:
            Dict with:
            - found: True if email was found
            - email: The email address (if found)
            - display_name: The full display name
            - source: Where the email was found ("contacts" or "recent_emails")
        """
        return await outlook_service.lookup_contact(name)

    # === Calendar Tools ===

    @mcp.tool()
    async def list_calendar_events(
        days_ahead: int = 7,
        limit: int = 50,
        calendar_name: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        List upcoming calendar events.

        Args:
            days_ahead: Number of days ahead to look for events (default: 7)
            limit: Maximum number of events to return (default: 50)
            calendar_name: Optional specific calendar name (default: primary calendar)

        Returns:
            List of calendar events with id, subject, start, end, location, and attendees
        """
        return await outlook_service.list_calendar_events(days_ahead, limit, calendar_name)

    # === Internal Endpoints (not exposed as MCP tools) ===

    @mcp.custom_route("/internal/mark-processed/{email_id}", methods=["POST"])
    async def mark_email_processed_endpoint(request):
        """
        Mark an email as processed by Nova (internal endpoint, not an MCP tool).

        Used by the input hook system to prevent duplicate task creation.
        Not exposed to the LLM to keep the tool context clean.
        """
        email_id = request.path_params["email_id"]
        result = await outlook_service.mark_email_processed(str(email_id))
        return JSONResponse(result)

    # === Health & Info Endpoints ===

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        """Health check endpoint for server monitoring."""
        outlook_status = await outlook_service.check_outlook_status()
        return JSONResponse({
            "status": "healthy" if outlook_status["connected"] else "degraded",
            "service": "outlook-mac-mcp-server",
            "version": "1.3.0",
            "timestamp": str(datetime.now()),
            "mcp_endpoint": "/mcp",
            "outlook_connected": outlook_status["connected"],
            "outlook_error": outlook_status.get("error"),
            "tools_count": 6
        })

    @mcp.custom_route("/tools/count", methods=["GET"])
    async def tools_count(request):
        """Tools count endpoint for Nova integration."""
        return JSONResponse({
            "tools_count": 6,
            "email_tools": 4,
            "calendar_tools": 1,
            "contact_tools": 1,
            "total_tools": 6
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Outlook Mac MCP Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=9000, help='Port to bind the server to')
    parser.add_argument('--folder', type=str, default=None,
                        help='Target folder path instead of inbox (e.g., "2026/Cohort 1")')

    args = parser.parse_args()

    # Initialize OutlookService with optional target folder
    outlook_service = OutlookService(target_folder=args.folder)

    # Setup tools
    setup_tools(outlook_service)

    # --- Run FastMCP Server ---
    try:
        logger.info(f"Starting Outlook Mac MCP server on http://{args.host}:{args.port}")
        if args.folder:
            logger.info(f"Target folder: {args.folder}")
        else:
            logger.info("Using default inbox")
        logger.info(f"MCP endpoint: http://{args.host}:{args.port}/mcp")
        logger.info(f"Health endpoint: http://{args.host}:{args.port}/health")

        # Run with streamable-http transport for LiteLLM compatibility
        mcp.run(transport="streamable-http", host=args.host, port=args.port, path="/mcp")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
