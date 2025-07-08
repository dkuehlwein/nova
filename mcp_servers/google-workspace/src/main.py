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

# Import our tool modules
from gmail_tools import GmailTools
from calendar_tools import CalendarTools

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleWorkspaceService:
    """Main service class that coordinates Gmail and Calendar operations."""
    
    def __init__(self,
                 creds_file_path: str,
                 token_path: str,
                 scopes: list[str] = None,
                 oauth_port: int = 9000):
        logger.info(f"Initializing GoogleWorkspaceService with creds file: {creds_file_path}")
        self.creds_file_path = creds_file_path
        self.token_path = token_path
        self.scopes = scopes if scopes is not None else [
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/calendar'
        ]
        self.oauth_port = oauth_port
        
        # Get credentials and initialize services
        self.token = self._get_token()
        logger.info("Token retrieved successfully")
        
        # Initialize Google API services
        self.gmail_service = self._get_gmail_service()
        self.calendar_service = self._get_calendar_service()
        logger.info("Google services initialized")
        
        # Get user email
        self.user_email = self._get_user_email()
        logger.info(f"User email retrieved: {self.user_email}")
        
        # Initialize tool modules
        self.gmail_tools = GmailTools(self.gmail_service, self.user_email)
        self.calendar_tools = CalendarTools(self.calendar_service)
        logger.info("Gmail and Calendar tools initialized")

    def _get_token(self) -> Credentials:
        """Retrieve or create OAuth 2.0 credentials."""
        token = None
        
        # Load existing token if it exists
        if os.path.exists(self.token_path):
            token = Credentials.from_authorized_user_file(self.token_path, self.scopes)
        
        # If there are no (valid) credentials available, let the user log in
        if not token or not token.valid:
            if token and token.expired and token.refresh_token:
                try:
                    token.refresh()
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}. Starting new auth flow.")
                    token = None
            
            if not token:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.creds_file_path, self.scopes
                    )
                    flow.redirect_uri = f'http://localhost:{self.oauth_port}/'
                    token = flow.run_local_server(port=self.oauth_port, open_browser=False)
                    logger.info(f"Please visit this URL for authorization: {flow.authorization_url()[0]}")
                except Exception as e:
                    logger.error(f"OAuth flow failed: {e}")
                    # Add WSL2 troubleshooting info
                    if 'WSL' in os.environ.get('WSL_DISTRO_NAME', '') or 'wsl' in os.environ.get('NAME', '').lower():
                        wsl_ip = self._get_wsl_ip()
                        logger.error('')
                        logger.error('=== WSL2 OAuth Troubleshooting ===')
                        logger.error('You are running in WSL2. This can cause OAuth redirect issues.')
                        logger.error('')
                        logger.error('SOLUTION 1 - Restart WSL2:')
                        logger.error('  From Windows PowerShell (as Administrator):')
                        logger.error('  > wsl --shutdown')
                        logger.error('  Then restart your WSL2 terminal')
                        logger.error('')
                        logger.error('SOLUTION 2 - Use WSL2 IP address:')
                        logger.error(f'  Instead of localhost:{self.oauth_port}, try:')
                        logger.error(f'  http://{wsl_ip}:{self.oauth_port}/')
                    raise ValueError(f'OAuth flow failed. Error: {e}')
                    
            # Save the credentials for the next run
            with open(self.token_path, 'w') as token_file:
                token_file.write(token.to_json())
                logger.info(f'Token saved to {self.token_path}')
        
        return token

    def _get_wsl_ip(self) -> str:
        """Get WSL2 IP address for OAuth troubleshooting."""
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            return result.stdout.strip().split()[0]
        except:
            return "WSL_IP_NOT_FOUND"

    def _get_gmail_service(self):
        """Initialize Gmail API service."""
        try:
            return build('gmail', 'v1', credentials=self.token, static_discovery=False)
        except HttpError as error:
            logger.error(f'Error building Gmail service: {error}')
            raise ValueError(f'Error building Gmail service: {error}')
    
    def _get_calendar_service(self):
        """Initialize Calendar API service."""
        try:
            return build('calendar', 'v3', credentials=self.token, static_discovery=False)
        except HttpError as error:
            logger.error(f'Error building Calendar service: {error}')
            raise ValueError(f'Error building Calendar service: {error}')

    def _get_user_email(self) -> str:
        """Get user's email address from Gmail profile."""
        try:
            profile = self.gmail_service.users().getProfile(userId='me').execute()
            return profile.get('emailAddress', '')
        except HttpError as error:
            logger.error(f'Error getting user email: {error}')
            return ''

    # No wrapper methods needed - tools will call gmail_tools and calendar_tools directly


# --- FastMCP Server Setup ---
mcp = FastMCP(name="GoogleWorkspaceToolsServer")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Google Workspace API FastMCP Server')
    parser.add_argument('--creds-file-path', required=True, help='OAuth 2.0 credentials file path (e.g., credentials.json)')
    parser.add_argument('--token-path', required=True, help='File location to store/retrieve access and refresh tokens (e.g., token.json)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=8002, help='Port to bind the server to')
    parser.add_argument('--oauth-port', type=int, default=9000, help='Port for OAuth flow')
    
    args = parser.parse_args()
    
    # Initialize GoogleWorkspaceService (which handles auth and core logic)
    workspace_service = GoogleWorkspaceService(args.creds_file_path, args.token_path, oauth_port=args.oauth_port)
    
    # === Gmail Tools ===
    
    @mcp.tool()
    async def send_email(recipient_ids: List[str], subject: str, message: str) -> Dict[str, str]:
        """Sends an email to one or more recipients. Subject and message are distinct."""
        return await workspace_service.gmail_tools.send_email(recipient_ids, subject, message)

    @mcp.tool()
    async def get_unread_emails() -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Retrieves a list of unread emails from the primary inbox category."""
        return await workspace_service.gmail_tools.get_unread_emails()

    @mcp.tool()
    async def read_email_content(email_id: str) -> Dict[str, str]:
        """Retrieves the full content of a specific email. AUTOMATICALLY marks the email as read - no need to call mark_email_as_read separately."""
        return await workspace_service.gmail_tools.read_email(email_id)

    @mcp.tool()
    async def trash_email(email_id: str) -> Union[str, Dict[str, str]]:
        """Moves the specified email to the trash."""
        return await workspace_service.gmail_tools.trash_email(email_id)

    @mcp.tool()
    async def mark_email_as_read(email_id: str) -> Union[str, Dict[str, str]]:
        """Marks the specified email as read."""
        return await workspace_service.gmail_tools.mark_email_as_read(email_id)

    @mcp.tool()
    async def create_draft_email(recipient_ids: List[str], subject: str, message: str) -> Dict[str, str]:
        """Creates a draft email message for one or more recipients."""
        return await workspace_service.gmail_tools.create_draft(recipient_ids, subject, message)

    @mcp.tool()
    async def list_draft_emails() -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Lists all draft emails with their ID, subject, and recipient."""
        return await workspace_service.gmail_tools.list_drafts()

    @mcp.tool()
    async def list_gmail_labels() -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Lists all labels in the user's mailbox."""
        return await workspace_service.gmail_tools.list_labels()

    @mcp.tool()
    async def create_new_label(label_name: str) -> Dict[str, str]:
        """Creates a new label in Gmail."""
        return await workspace_service.gmail_tools.create_label(label_name)

    # === Calendar Tools ===
    
    @mcp.tool()
    async def list_calendars() -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Lists all calendars accessible to the user."""
        return await workspace_service.calendar_tools.list_calendars()

    @mcp.tool()
    async def create_calendar_event(calendar_id: str, summary: str, start_datetime: str, 
                                  end_datetime: str, description: str = "", location: str = "",
                                  attendees: Optional[List[str]] = None) -> Dict[str, str]:
        """Creates a new calendar event. Datetime format: 2025-06-06T10:00:00 (ISO format)"""
        return await workspace_service.calendar_tools.create_event(
            calendar_id, summary, start_datetime, end_datetime, description, location, attendees
        )

    @mcp.tool()
    async def list_calendar_events(calendar_id: str = 'primary', max_results: int = 50, 
                                 time_min: Optional[str] = None) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """Lists upcoming events from a calendar. If time_min not provided, uses current time."""
        return await workspace_service.calendar_tools.list_events(calendar_id, max_results, time_min)

    @mcp.tool()
    async def create_quick_calendar_event(calendar_id: str, text: str) -> Dict[str, str]:
        """Creates an event using natural language. Example: 'Meeting with John tomorrow at 2pm'"""
        return await workspace_service.calendar_tools.create_quick_event(calendar_id, text)

    # Health endpoint for server monitoring
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        return JSONResponse({
            "status": "healthy",
            "service": "google-workspace-mcp-server", 
            "version": "1.0.0",
            "timestamp": str(datetime.now()),
            "mcp_endpoint": "/mcp/",
            "gmail_user": workspace_service.user_email
        })

    # --- Run FastMCP Server ---
    try:
        logger.info(f"Starting Google Workspace FastMCP server on http://{args.host}:{args.port}")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise 