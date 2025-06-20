import os
import base64
import asyncio
import email
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .gmail_tools import GmailTools
from .calendar_tools import CalendarTools


class GoogleWorkspaceService:
    """Google Workspace service that provides Gmail and Calendar functionality."""
    
    # OAuth 2.0 scopes for Gmail and Calendar
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.compose',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    def __init__(self, creds_file_path: str, token_path: str):
        """Initialize the Google Workspace service with OAuth credentials."""
        self.creds_file_path = creds_file_path
        self.token_path = token_path
        self.creds = self._get_credentials()
        self.gmail_service = self._get_gmail_service()
        self.calendar_service = self._get_calendar_service()
        
        # Get user email
        self.user_email = self._get_user_email()
        
        # Initialize tool classes
        self.gmail_tools = GmailTools(self.gmail_service, self.user_email)
        self.calendar_tools = CalendarTools(self.calendar_service)
    
    def _get_credentials(self) -> Credentials:
        """Get or refresh OAuth credentials."""
        creds = None
        
        # Load existing credentials
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.creds_file_path):
                    raise FileNotFoundError(f"Credentials file not found at {self.creds_file_path}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.creds_file_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        return creds
    
    def _get_gmail_service(self):
        """Create and return Gmail service object."""
        return build('gmail', 'v1', credentials=self.creds, static_discovery=False)
    
    def _get_calendar_service(self):
        """Create and return Calendar service object."""
        return build('calendar', 'v3', credentials=self.creds, static_discovery=False)
    
    def _get_user_email(self) -> str:
        """Get user's email address from Gmail profile."""
        try:
            profile = self.gmail_service.users().getProfile(userId='me').execute()
            return profile.get('emailAddress', '')
        except HttpError as error:
            return ''
    
    # Gmail Methods
    async def get_user_profile(self) -> Dict[str, Any]:
        """Get the user's Gmail profile information."""
        return await self.gmail_tools.get_user_profile()
    
    async def list_messages(self, query: str = "", max_results: int = 10) -> List[Dict[str, Any]]:
        """List Gmail messages with optional query."""
        return await self.gmail_tools.list_messages(query, max_results)
    
    async def get_message(self, message_id: str) -> Dict[str, Any]:
        """Get a specific Gmail message by ID."""
        return await self.gmail_tools.get_message(message_id)
    
    async def send_message(self, to: str, subject: str, body: str, 
                          html_body: Optional[str] = None, 
                          cc: Optional[str] = None, 
                          bcc: Optional[str] = None) -> Dict[str, Any]:
        """Send an email message."""
        # Convert single recipient to list format expected by gmail_tools
        recipients = [to]
        if cc:
            recipients.extend(cc.split(", "))
        if bcc:
            recipients.extend(bcc.split(", "))
        return await self.gmail_tools.send_email(recipients, subject, body)
    
    async def create_draft(self, to: str, subject: str, body: str, 
                          html_body: Optional[str] = None) -> Dict[str, Any]:
        """Create a draft email."""
        # Convert single recipient to list format expected by gmail_tools
        recipients = [to]
        return await self.gmail_tools.create_draft(recipients, subject, body)
    
    async def search_messages(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search Gmail messages with a query."""
        return await self.gmail_tools.search_messages(query, max_results)
    
    async def create_label(self, name: str) -> Dict[str, Any]:
        """Create a Gmail label."""
        return await self.gmail_tools.create_label(name)
    
    async def trash_email(self, email_id: str) -> Dict[str, Any]:
        """Move an email to trash."""
        return await self.gmail_tools.trash_email(email_id)
    
    # Calendar Methods
    async def list_calendars(self) -> List[Dict[str, Any]]:
        """List all calendars accessible to the user."""
        return await self.calendar_tools.list_calendars()
    
    async def create_event(self, calendar_id: str, summary: str, 
                          start_datetime: str, end_datetime: str,
                          description: Optional[str] = None,
                          location: Optional[str] = None,
                          attendees: Optional[List[str]] = None,
                          timezone: str = 'Europe/Berlin') -> Dict[str, Any]:
        """Create a calendar event."""
        return await self.calendar_tools.create_event(
            calendar_id, summary, start_datetime, end_datetime,
            description, location, attendees, timezone
        )
    
    async def list_events(self, calendar_id: str = 'primary', 
                         max_results: int = 10,
                         time_min: Optional[str] = None,
                         time_max: Optional[str] = None) -> List[Dict[str, Any]]:
        """List calendar events."""
        return await self.calendar_tools.list_events(calendar_id, max_results, time_min, time_max)
    
    async def get_event(self, calendar_id: str, event_id: str) -> Dict[str, Any]:
        """Get a specific calendar event."""
        return await self.calendar_tools.get_event(calendar_id, event_id)
    
    async def update_event(self, calendar_id: str, event_id: str, 
                          summary: Optional[str] = None,
                          description: Optional[str] = None,
                          location: Optional[str] = None,
                          start_datetime: Optional[str] = None,
                          end_datetime: Optional[str] = None,
                          timezone: str = 'Europe/Berlin') -> Dict[str, Any]:
        """Update a calendar event."""
        return await self.calendar_tools.update_event(
            calendar_id, event_id, summary, description, location,
            start_datetime, end_datetime, timezone
        )
    
    async def delete_event(self, calendar_id: str, event_id: str) -> Dict[str, Any]:
        """Delete a calendar event."""
        return await self.calendar_tools.delete_event(calendar_id, event_id)
    
    async def create_quick_event(self, calendar_id: str, text: str) -> Dict[str, Any]:
        """Create an event using natural language text."""
        return await self.calendar_tools.create_quick_event(calendar_id, text) 