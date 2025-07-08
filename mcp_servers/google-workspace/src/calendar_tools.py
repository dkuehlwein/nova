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
                          attendees: Optional[List[str]] = None, timezone: str = 'Europe/Berlin') -> Dict[str, Any]:
        """Creates a new calendar event and reports any scheduling conflicts."""
        try:
            # Check for conflicts BEFORE creating the event
            conflicts = await self._check_conflicts(calendar_id, start_datetime, end_datetime)
            
            # Create the event regardless of conflicts (as requested)
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
            
            # Prepare response with conflict information
            response = {
                "status": "success",
                "event_id": created_event['id'],
                "html_link": created_event.get('htmlLink', ''),
                "summary": created_event.get('summary', ''),
                "conflicts_detected": len(conflicts) > 0,
                "conflicts": conflicts
            }
            
            if conflicts:
                logger.warning(f"Event created with {len(conflicts)} scheduling conflicts: {created_event['id']}")
                response["conflict_summary"] = f"This event conflicts with {len(conflicts)} existing event(s)"
            
            return response
            
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
                          timezone: str = 'Europe/Berlin') -> Dict[str, Any]:
        """Updates an existing calendar event and reports any scheduling conflicts."""
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
            
            # Check for conflicts if time was changed
            conflicts = []
            if start_datetime is not None or end_datetime is not None:
                # Get the final start/end times for conflict checking
                final_start = start_datetime if start_datetime else event['start'].get('dateTime', event['start'].get('date'))
                final_end = end_datetime if end_datetime else event['end'].get('dateTime', event['end'].get('date'))
                
                if final_start and final_end:
                    conflicts = await self._check_conflicts(calendar_id, final_start, final_end, exclude_event_id=event_id)
            
            # Update the event regardless of conflicts
            updated_event = await asyncio.to_thread(
                self.calendar_service.events().update(
                    calendarId=calendar_id, eventId=event_id, body=event
                ).execute
            )
            
            logger.info(f"Calendar event updated: {event_id}")
            
            # Prepare response with conflict information
            response = {
                "status": "success",
                "event_id": updated_event['id'],
                "html_link": updated_event.get('htmlLink', ''),
                "summary": updated_event.get('summary', ''),
                "conflicts_detected": len(conflicts) > 0,
                "conflicts": conflicts
            }
            
            if conflicts:
                logger.warning(f"Event updated with {len(conflicts)} scheduling conflicts: {event_id}")
                response["conflict_summary"] = f"This event now conflicts with {len(conflicts)} existing event(s)"
            
            return response
            
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

    async def create_quick_event(self, calendar_id: str, text: str) -> Dict[str, Any]:
        """Creates an event using natural language and reports any scheduling conflicts."""
        try:
            # Create the event first (Google handles the natural language parsing)
            event = await asyncio.to_thread(
                self.calendar_service.events().quickAdd(calendarId=calendar_id, text=text).execute
            )
            
            logger.info(f"Quick calendar event created: {event['id']}")
            
            # Check for conflicts after creation (since we need Google to parse the time)
            conflicts = []
            if 'start' in event and 'end' in event:
                start_time = event['start'].get('dateTime', event['start'].get('date'))
                end_time = event['end'].get('dateTime', event['end'].get('date'))
                
                if start_time and end_time:
                    conflicts = await self._check_conflicts(calendar_id, start_time, end_time, exclude_event_id=event['id'])
            
            # Prepare response with conflict information
            response = {
                "status": "success",
                "event_id": event['id'],
                "html_link": event.get('htmlLink', ''),
                "summary": event.get('summary', text),
                "conflicts_detected": len(conflicts) > 0,
                "conflicts": conflicts
            }
            
            if conflicts:
                logger.warning(f"Quick event created with {len(conflicts)} scheduling conflicts: {event['id']}")
                response["conflict_summary"] = f"This event conflicts with {len(conflicts)} existing event(s)"
            
            return response
            
        except HttpError as error:
            logger.error(f"Error creating quick calendar event: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred creating quick event: {str(error)}"}

    async def _check_conflicts(self, calendar_id: str, start_datetime: str, end_datetime: str, 
                              exclude_event_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Check for scheduling conflicts with existing events in the specified time range.
        
        Args:
            calendar_id: The calendar to check for conflicts
            start_datetime: Start time in ISO format (e.g., '2025-06-25T10:00:00+02:00')
            end_datetime: End time in ISO format
            exclude_event_id: Optional event ID to exclude from conflict checking (for updates)
            
        Returns:
            List of conflicting events with details
        """
        conflicts = []
        
        try:
            # Query events in the time range
            events_result = await asyncio.to_thread(
                self.calendar_service.events().list(
                    calendarId=calendar_id,
                    timeMin=start_datetime,
                    timeMax=end_datetime,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute
            )
            
            events = events_result.get('items', [])
            
            # Parse input times for comparison
            from datetime import datetime
            import dateutil.parser
            
            new_start = dateutil.parser.parse(start_datetime)
            new_end = dateutil.parser.parse(end_datetime)
            
            for event in events:
                # Skip the event we're updating
                if exclude_event_id and event.get('id') == exclude_event_id:
                    continue
                
                # Skip declined events
                if event.get('status') == 'cancelled':
                    continue
                
                # Get event times
                event_start_str = event['start'].get('dateTime', event['start'].get('date'))
                event_end_str = event['end'].get('dateTime', event['end'].get('date'))
                
                if not event_start_str or not event_end_str:
                    continue
                
                # Parse event times
                event_start = dateutil.parser.parse(event_start_str)
                event_end = dateutil.parser.parse(event_end_str)
                
                # Check for overlap: new event overlaps if it starts before existing ends 
                # and ends after existing starts
                if new_start < event_end and new_end > event_start:
                    conflict = {
                        'id': event.get('id'),
                        'summary': event.get('summary', 'No Title'),
                        'start': event_start_str,
                        'end': event_end_str,
                        'location': event.get('location', ''),
                        'organizer': event.get('organizer', {}),
                        'html_link': event.get('htmlLink', '')
                    }
                    conflicts.append(conflict)
            
            logger.info(f"Conflict check completed: found {len(conflicts)} conflicts")
            return conflicts
            
        except Exception as error:
            logger.error(f"Error checking calendar conflicts: {error}")
            # Return empty list on error - don't block event creation
            return []