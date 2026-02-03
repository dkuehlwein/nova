#!/usr/bin/env python3
"""
MS Graph MCP Server - Microsoft 365 Email, Calendar, and People integration.

This is the main entry point for the MS Graph MCP server that provides
access to Microsoft 365 via the MS Graph API through FastMCP.
"""

import argparse
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastapi.responses import JSONResponse, RedirectResponse

from src.auth import MSGraphAuth
from src.service import MSGraphService

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
CLIENT_ID = os.getenv("MS_GRAPH_CLIENT_ID")
TENANT_ID = os.getenv("MS_GRAPH_TENANT_ID")
CLIENT_SECRET = os.getenv("MS_GRAPH_CLIENT_SECRET")
TOKEN_CACHE_PATH = os.getenv("MS_GRAPH_TOKEN_CACHE_PATH", "/app/credentials/token_cache.json")
REDIRECT_URI = os.getenv("MS_GRAPH_REDIRECT_URI", "http://localhost:8400/callback")

# FastMCP server
mcp = FastMCP(name="MSGraphServer")

# Global service instance
graph_service: Optional[MSGraphService] = None
graph_auth: Optional[MSGraphAuth] = None


def setup_auth_endpoints():
    """Set up OAuth authentication endpoints."""

    @mcp.custom_route("/auth/status", methods=["GET"])
    async def auth_status(request):
        """Check authentication status."""
        if not graph_auth:
            return JSONResponse({
                "authenticated": False,
                "error": "Server not configured",
            })

        status = graph_auth.get_auth_status()
        return JSONResponse(status)

    @mcp.custom_route("/auth/start", methods=["GET"])
    async def auth_start(request):
        """Start OAuth flow - returns authorization URL or redirects."""
        from fastapi.responses import HTMLResponse

        if not graph_auth:
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>MS Graph - Configuration Error</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background: #f5f5f5; }
                    .card { background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
                    h1 { color: #d32f2f; margin-top: 0; }
                    p { color: #666; line-height: 1.6; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>⚠️ Configuration Error</h1>
                    <p>The MS Graph server is not configured. Please ensure the following environment variables are set:</p>
                    <ul>
                        <li><code>MS_GRAPH_CLIENT_ID</code></li>
                        <li><code>MS_GRAPH_TENANT_ID</code></li>
                        <li><code>MS_GRAPH_CLIENT_SECRET</code></li>
                    </ul>
                </div>
            </body>
            </html>
            """, status_code=500)

        # Check if already authenticated (unless force=true)
        force_reauth = request.query_params.get("force") == "true"
        if graph_auth.is_authenticated() and not force_reauth:
            status = graph_auth.get_auth_status()
            return HTMLResponse(content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>MS Graph - Already Authenticated</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background: #f5f5f5; }}
                    .card {{ background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }}
                    h1 {{ color: #2e7d32; margin-top: 0; }}
                    p {{ color: #666; line-height: 1.6; }}
                    .user {{ font-size: 1.2em; color: #333; font-weight: 500; }}
                    .actions {{ margin-top: 24px; }}
                    a {{ display: inline-block; padding: 12px 24px; background: #0078d4; color: white; text-decoration: none; border-radius: 6px; margin: 0 8px; }}
                    a:hover {{ background: #106ebe; }}
                    a.secondary {{ background: #666; }}
                    a.secondary:hover {{ background: #555; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>✅ Already Authenticated</h1>
                    <p>You are signed in as:</p>
                    <p class="user">{status.get('user_email', 'Unknown')}</p>
                    <p class="actions">
                        <a href="/auth/start?force=true">Sign in as different user</a>
                        <a href="/health" class="secondary">View Status</a>
                    </p>
                </div>
            </body>
            </html>
            """)

        result = graph_auth.get_authorization_url()
        auth_url = result["auth_url"]

        # Check if user wants JSON (for API clients)
        accept = request.headers.get("accept", "")
        if "application/json" in accept:
            return JSONResponse({
                "auth_url": auth_url,
                "instructions": "Visit the auth_url in your browser to authenticate",
            })

        # Return nice HTML page with clickable link
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>MS Graph - Sign In</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background: #f5f5f5; }}
                .card {{ background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }}
                h1 {{ color: #0078d4; margin-top: 0; }}
                p {{ color: #666; line-height: 1.6; }}
                .btn {{ display: inline-block; padding: 16px 32px; background: #0078d4; color: white; text-decoration: none; border-radius: 8px; font-size: 1.1em; font-weight: 500; margin-top: 16px; }}
                .btn:hover {{ background: #106ebe; }}
                .logo {{ font-size: 48px; margin-bottom: 16px; }}
                .note {{ font-size: 0.9em; color: #999; margin-top: 24px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="logo">🔐</div>
                <h1>Sign in to Microsoft 365</h1>
                <p>Nova needs access to your Microsoft 365 account to read emails, manage calendar events, and look up contacts.</p>
                <a href="{auth_url}" class="btn">Sign in with Microsoft</a>
                <p class="note">You'll be redirected to Microsoft's sign-in page.</p>
            </div>
        </body>
        </html>
        """)

    @mcp.custom_route("/callback", methods=["GET"])
    async def auth_callback(request):
        """Handle OAuth callback."""
        if not graph_auth:
            return JSONResponse({
                "error": "Server not configured",
            }, status_code=500)

        # Extract code and state from query params
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")
        error_description = request.query_params.get("error_description")

        if error:
            return JSONResponse({
                "success": False,
                "error": error,
                "error_description": error_description,
            }, status_code=400)

        if not code or not state:
            return JSONResponse({
                "success": False,
                "error": "Missing code or state parameter",
            }, status_code=400)

        # Complete the auth flow
        result = graph_auth.complete_auth_flow(code, state)

        if result.get("success"):
            # Re-initialize the service with the new token
            global graph_service
            if graph_service:
                await graph_service.initialize()

            # Return success HTML page
            from fastapi.responses import HTMLResponse
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Successful</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; max-width: 600px; margin: 0 auto; background: #f5f5f5; }}
                    .card {{ background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }}
                    h1 {{ color: #2e7d32; margin-top: 0; }}
                    p {{ color: #666; line-height: 1.6; }}
                    .user {{ font-size: 1.2em; color: #333; font-weight: 500; background: #e8f5e9; padding: 12px 20px; border-radius: 8px; display: inline-block; }}
                    .success-icon {{ font-size: 48px; margin-bottom: 16px; }}
                    .note {{ font-size: 0.9em; color: #999; margin-top: 24px; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="success-icon">✅</div>
                    <h1>Authentication Successful!</h1>
                    <p>You are now signed in as:</p>
                    <p class="user">{result.get('user_email', 'Unknown')}</p>
                    <p class="note">You can close this window and return to Nova.</p>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html, status_code=200)
        else:
            return JSONResponse({
                "success": False,
                "error": result.get("error", "Authentication failed"),
            }, status_code=400)

    @mcp.custom_route("/auth/logout", methods=["POST"])
    async def auth_logout(request):
        """Log out and clear tokens."""
        if not graph_auth:
            return JSONResponse({
                "error": "Server not configured",
            }, status_code=500)

        graph_auth.logout()

        # Close the service client
        global graph_service
        if graph_service:
            await graph_service.close()
            graph_service = MSGraphService(graph_auth)

        return JSONResponse({
            "success": True,
            "message": "Logged out successfully",
        })


def setup_tools(service: MSGraphService):
    """Set up all MCP tools for the MS Graph service."""

    # === Email Tools ===

    @mcp.tool()
    async def list_emails(
        folder: str = "inbox",
        limit: int = 20,
        unread_only: bool = False,
        since_date: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        List emails from the specified folder.

        Args:
            folder: Folder name to list emails from (default: inbox)
            limit: Maximum number of emails to return (default: 20)
            unread_only: If True, only return unread emails
            since_date: Only return emails received on or after this date (format: YYYY-MM-DD)

        Returns:
            List of email summaries with id, subject, sender, date, read status
        """
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.mail_tools.list_emails(folder, limit, unread_only, since_date)

    @mcp.tool()
    async def read_email(email_id: str) -> Dict[str, Any]:
        """
        Read the full content of an email by its ID.

        Args:
            email_id: The unique identifier of the email to read

        Returns:
            Full email content including subject, sender, recipients, date, and body
        """
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.mail_tools.read_email(email_id)

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
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.mail_tools.create_draft(recipients, subject, body, cc)

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
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.mail_tools.send_email(recipients, subject, body, cc)

    # === Calendar Tools ===

    @mcp.tool()
    async def list_calendar_events(
        days_ahead: int = 7,
        limit: int = 50,
        calendar_id: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        List upcoming calendar events.

        Args:
            days_ahead: Number of days ahead to look for events (default: 7)
            limit: Maximum number of events to return (default: 50)
            calendar_id: Optional specific calendar ID (default: primary calendar)

        Returns:
            List of calendar events with id, subject, start, end, location, and attendees
        """
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.calendar_tools.list_calendar_events(days_ahead, limit, calendar_id)

    @mcp.tool()
    async def create_event(
        summary: str,
        start_datetime: str,
        end_datetime: str,
        description: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
        calendar_id: str = "primary"
    ) -> Dict[str, Any]:
        """
        Create a new calendar event.

        Args:
            summary: Event title/summary
            start_datetime: Event start time (ISO format: 2025-06-06T10:00:00)
            end_datetime: Event end time (ISO format: 2025-06-06T11:00:00)
            description: Event description/body (optional)
            location: Event location (optional)
            attendees: List of attendee email addresses (optional)
            calendar_id: Calendar ID (default: primary)

        Returns:
            Created event details with event_id
        """
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.calendar_tools.create_event(
            summary, start_datetime, end_datetime, description, location, attendees, calendar_id
        )

    @mcp.tool()
    async def update_event(
        event_id: str,
        summary: Optional[str] = None,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing calendar event.

        Args:
            event_id: The ID of the event to update
            summary: New event title (optional)
            start_datetime: New start time (optional)
            end_datetime: New end time (optional)
            description: New description (optional)
            location: New location (optional)

        Returns:
            Updated event details
        """
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.calendar_tools.update_event(
            event_id, summary, start_datetime, end_datetime, description, location
        )

    @mcp.tool()
    async def delete_event(event_id: str) -> Dict[str, str]:
        """
        Delete a calendar event by its ID.

        Args:
            event_id: The ID of the event to delete

        Returns:
            Confirmation of deletion
        """
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.calendar_tools.delete_event(event_id)

    # === People Tools ===

    @mcp.tool()
    async def lookup_contact(name: str) -> Dict[str, Any]:
        """
        Look up an email address for a person by name.

        Searches contacts and frequent email contacts to find an email address
        for the given name. Useful for resolving names to emails.

        Args:
            name: The person's name to look up (e.g., "John Doe")

        Returns:
            Dict with found status, email, display_name, and source
        """
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.people_tools.lookup_contact(name)

    @mcp.tool()
    async def search_people(query: str, limit: int = 10) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Search organization directory for people.

        Searches people the user has communicated with and the organization directory.

        Args:
            query: Search query (name, email, or other relevant terms)
            limit: Maximum number of results (default: 10)

        Returns:
            List of people with display_name, email, job_title, department
        """
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.people_tools.search_people(query, limit)

    @mcp.tool()
    async def get_user_profile(user_id: str = "me") -> Dict[str, Any]:
        """
        Get user profile information.

        Args:
            user_id: User ID or "me" for the authenticated user (default: "me")

        Returns:
            User profile with display_name, email, job_title, department, etc.
        """
        if not service.is_ready():
            return {"error": "Service not authenticated. Visit /auth/start to authenticate."}
        return await service.people_tools.get_user_profile(user_id)


def setup_health_endpoints(service: MSGraphService):
    """Set up health and info endpoints."""

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        """Health check endpoint for server monitoring."""
        auth_status = graph_auth.get_auth_status() if graph_auth else {"authenticated": False}

        return JSONResponse({
            "status": "healthy" if service.is_ready() else "degraded",
            "service": "ms-graph-mcp-server",
            "version": "1.0.0",
            "timestamp": str(datetime.now()),
            "mcp_endpoint": "/mcp",
            "authenticated": auth_status.get("authenticated", False),
            "user_email": auth_status.get("user_email", ""),
            "tools_count": 11,  # 4 email + 4 calendar + 3 people
        })

    @mcp.custom_route("/tools/count", methods=["GET"])
    async def tools_count(request):
        """Tools count endpoint for Nova integration."""
        return JSONResponse({
            "tools_count": 11,
            "email_tools": 4,
            "calendar_tools": 4,
            "people_tools": 3,
            "total_tools": 11,
        })


async def initialize_service():
    """Initialize the MS Graph service."""
    global graph_auth, graph_service

    if not CLIENT_ID or not TENANT_ID or not CLIENT_SECRET:
        logger.error("MS_GRAPH_CLIENT_ID, MS_GRAPH_TENANT_ID, and MS_GRAPH_CLIENT_SECRET must be set")
        return False

    # Initialize auth
    graph_auth = MSGraphAuth(
        client_id=CLIENT_ID,
        tenant_id=TENANT_ID,
        client_secret=CLIENT_SECRET,
        token_cache_path=TOKEN_CACHE_PATH,
        redirect_uri=REDIRECT_URI,
    )

    # Initialize service
    graph_service = MSGraphService(graph_auth)

    # Try to initialize if already authenticated
    if graph_auth.is_authenticated():
        success = await graph_service.initialize()
        if success:
            logger.info(f"Service initialized with user: {graph_service.user_info.get('mail', 'unknown')}")
        else:
            logger.warning("Could not initialize service - authentication may have expired")
    else:
        logger.info("Service created but not authenticated - visit /auth/start to authenticate")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MS Graph API FastMCP Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind the server to')

    args = parser.parse_args()

    # Check required environment variables
    if not CLIENT_ID or not TENANT_ID or not CLIENT_SECRET:
        logger.error("Required environment variables not set:")
        logger.error("  MS_GRAPH_CLIENT_ID, MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_SECRET")
        exit(1)

    # Initialize service synchronously for startup
    asyncio.run(initialize_service())

    # Setup auth endpoints
    setup_auth_endpoints()

    # Setup tools (even if not authenticated, they'll return appropriate errors)
    setup_tools(graph_service)

    # Setup health endpoints
    setup_health_endpoints(graph_service)

    # Run server
    logger.info(f"Starting MS Graph MCP server on http://{args.host}:{args.port}")
    logger.info(f"MCP endpoint: http://{args.host}:{args.port}/mcp")
    logger.info(f"Health endpoint: http://{args.host}:{args.port}/health")
    logger.info(f"Auth endpoints: /auth/status, /auth/start, /auth/callback")

    if graph_auth and graph_auth.is_authenticated():
        status = graph_auth.get_auth_status()
        logger.info(f"Authenticated user: {status.get('user_email', 'unknown')}")
    else:
        logger.info("Not authenticated - visit /auth/start to authenticate")

    # Run with streamable-http transport for LiteLLM compatibility
    mcp.run(transport="streamable-http", host=args.host, port=args.port, path="/mcp")
