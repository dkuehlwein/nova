"""
Calendar tools for Google Workspace MCP Server.
Contains all Calendar-related functionality for event and calendar operations.
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Union, Optional, Any
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)

class CalendarTools:
    """Calendar tools for the Google Workspace MCP server."""
    
    def __init__(self, calendar_service):
        self.calendar_service = calendar_service
    
    async def list_calendars(self) -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Lists all calendars accessible to the user."""
        try:
            calendars_result = await asyncio.to_thread(
                self.calendar_service.calendarList().list().execute
            )
            calendars = calendars_result.get('items', [])
            
            calendar_list = []
            for calendar in calendars:
                calendar_info = {
                    'id': calendar['id'],
                    'summary': calendar.get('summary', ''),
                    'description': calendar.get('description', ''),
                    'primary': calendar.get('primary', False),
                    'access_role': calendar.get('accessRole', ''),
                    'selected': calendar.get('selected', False)
                }
                calendar_list.append(calendar_info)
            
            return calendar_list
        except HttpError as error:
            logger.error(f"Error listing calendars: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred listing calendars: {str(error)}"}

    async def create_event(self, calendar_id: str, summary: str, start_datetime: str,
                          end_datetime: str, description: str = "", location: str = "",
                          attendees: Optional[List[str]] = None, timezone: str = 'Europe/Berlin') -> Dict[str, str]:
        """Creates a new calendar event."""
        try:
            event = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start_datetime,
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_datetime,
                    'timeZone': timezone,
                },
            }
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            created_event = await asyncio.to_thread(
                self.calendar_service.events().insert(calendarId=calendar_id, body=event).execute
            )
            
            logger.info(f"Calendar event created: {created_event['id']}")
            return {
                "status": "success",
                "event_id": created_event['id'],
                "html_link": created_event.get('htmlLink', ''),
                "summary": created_event.get('summary', '')
            }
        except HttpError as error:
            logger.error(f"Error creating calendar event: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred creating event: {str(error)}"}

    async def list_events(self, calendar_id: str = 'primary', max_results: int = 50,
                         time_min: Optional[str] = None, time_max: Optional[str] = None) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """Lists upcoming events from a calendar."""
        try:
            if time_min is None:
                time_min = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            
            list_params = {
                'calendarId': calendar_id,
                'timeMin': time_min,
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            
            if time_max:
                list_params['timeMax'] = time_max
            
            events_result = await asyncio.to_thread(
                self.calendar_service.events().list(**list_params).execute
            )
            
            events = events_result.get('items', [])
            event_list = []
            
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                event_info = {
                    'id': event['id'],
                    'summary': event.get('summary', 'No Title'),
                    'start': start,
                    'end': end,
                    'description': event.get('description', ''),
                    'location': event.get('location', ''),
                    'html_link': event.get('htmlLink', ''),
                    'status': event.get('status', ''),
                    'creator': event.get('creator', {}),
                    'organizer': event.get('organizer', {}),
                    'attendees': event.get('attendees', [])
                }
                event_list.append(event_info)
            
            return event_list
        except HttpError as error:
            logger.error(f"Error listing calendar events: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred listing events: {str(error)}"}

    async def get_event(self, calendar_id: str, event_id: str) -> Union[Dict[str, Any], Dict[str, str]]:
        """Gets details of a specific calendar event."""
        try:
            event = await asyncio.to_thread(
                self.calendar_service.events().get(calendarId=calendar_id, eventId=event_id).execute
            )
            
            return {
                'id': event['id'],
                'summary': event.get('summary', ''),
                'description': event.get('description', ''),
                'location': event.get('location', ''),
                'start': event['start'],
                'end': event['end'],
                'html_link': event.get('htmlLink', ''),
                'status': event.get('status', ''),
                'creator': event.get('creator', {}),
                'organizer': event.get('organizer', {}),
                'attendees': event.get('attendees', [])
            }
        except HttpError as error:
            logger.error(f"Error getting calendar event {event_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred getting event: {str(error)}"}

    async def update_event(self, calendar_id: str, event_id: str, 
                          summary: Optional[str] = None,
                          description: Optional[str] = None,
                          location: Optional[str] = None,
                          start_datetime: Optional[str] = None,
                          end_datetime: Optional[str] = None,
                          timezone: str = 'Europe/Berlin') -> Dict[str, str]:
        """Updates an existing calendar event."""
        try:
            # First get the existing event
            event = await asyncio.to_thread(
                self.calendar_service.events().get(calendarId=calendar_id, eventId=event_id).execute
            )
            
            # Update fields that were provided
            if summary is not None:
                event['summary'] = summary
            if description is not None:
                event['description'] = description
            if location is not None:
                event['location'] = location
            if start_datetime is not None:
                event['start'] = {
                    'dateTime': start_datetime,
                    'timeZone': timezone
                }
            if end_datetime is not None:
                event['end'] = {
                    'dateTime': end_datetime,
                    'timeZone': timezone
                }
            
            updated_event = await asyncio.to_thread(
                self.calendar_service.events().update(
                    calendarId=calendar_id, eventId=event_id, body=event
                ).execute
            )
            
            logger.info(f"Calendar event updated: {event_id}")
            return {
                "status": "success",
                "event_id": updated_event['id'],
                "html_link": updated_event.get('htmlLink', ''),
                "summary": updated_event.get('summary', '')
            }
        except HttpError as error:
            logger.error(f"Error updating calendar event {event_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred updating event: {str(error)}"}

    async def delete_event(self, calendar_id: str, event_id: str) -> Union[str, Dict[str, str]]:
        """Deletes a calendar event."""
        try:
            await asyncio.to_thread(
                self.calendar_service.events().delete(calendarId=calendar_id, eventId=event_id).execute
            )
            
            logger.info(f"Calendar event deleted: {event_id}")
            return f"Calendar event {event_id} deleted successfully."
        except HttpError as error:
            logger.error(f"Error deleting calendar event {event_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred deleting event: {str(error)}"}

    async def create_quick_event(self, calendar_id: str, text: str) -> Dict[str, str]:
        """Creates an event using natural language."""
        try:
            event = await asyncio.to_thread(
                self.calendar_service.events().quickAdd(calendarId=calendar_id, text=text).execute
            )
            
            logger.info(f"Quick calendar event created: {event['id']}")
            return {
                "status": "success",
                "event_id": event['id'],
                "html_link": event.get('htmlLink', ''),
                "summary": event.get('summary', text)
            }
        except HttpError as error:
            logger.error(f"Error creating quick calendar event: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred creating quick event: {str(error)}"} 