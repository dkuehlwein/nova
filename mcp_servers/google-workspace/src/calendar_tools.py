"""
Calendar tools for Google Workspace MCP Server.
Contains all Calendar-related functionality for event and calendar operations.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Union, Optional, Any

import dateutil.parser
from dateutil import tz
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class CalendarTools:
    """Calendar tools for the Google Workspace MCP server."""
    
    DEFAULT_TIMEZONE = 'Europe/Berlin'
    DEFAULT_MAX_RESULTS = 50
    
    def __init__(self, calendar_service):
        self.calendar_service = calendar_service
        self._berlin_tz = tz.gettz(self.DEFAULT_TIMEZONE)
    
    def _handle_http_error(self, error: HttpError, operation: str) -> Dict[str, str]:
        """Centralized HTTP error handling."""
        logger.error(f"Error {operation}: {error}")
        return {
            "status": "error", 
            "error_message": f"An HttpError occurred {operation}: {str(error)}"
        }
    
    def _normalize_datetime(self, dt_string: str) -> datetime:
        """Parse datetime string and ensure timezone awareness."""
        parsed_dt = dateutil.parser.parse(dt_string)
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=self._berlin_tz)
        return parsed_dt
    
    def _format_event_info(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format standard event information."""
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        return {
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
    
    def _create_conflict_response(self, event: Dict[str, Any], conflicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create standardized response with conflict information."""
        response = {
            "status": "success",
            "event_id": event['id'],
            "html_link": event.get('htmlLink', ''),
            "summary": event.get('summary', ''),
            "conflicts_detected": len(conflicts) > 0,
            "conflicts": conflicts
        }
        
        if conflicts:
            logger.warning(f"Event operation completed with {len(conflicts)} scheduling conflicts: {event['id']}")
            response["conflict_summary"] = f"This event conflicts with {len(conflicts)} existing event(s)"
        
        return response
    
    async def list_calendars(self) -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Lists all calendars accessible to the user."""
        try:
            calendars_result = await asyncio.to_thread(
                self.calendar_service.calendarList().list().execute
            )
            calendars = calendars_result.get('items', [])
            
            return [
                {
                    'id': calendar['id'],
                    'summary': calendar.get('summary', ''),
                    'description': calendar.get('description', ''),
                    'primary': calendar.get('primary', False),
                    'access_role': calendar.get('accessRole', ''),
                    'selected': calendar.get('selected', False)
                }
                for calendar in calendars
            ]
        except HttpError as error:
            return self._handle_http_error(error, "listing calendars")

    async def create_event(self, calendar_id: str, summary: str, start_datetime: str,
                          end_datetime: str, description: str = "", location: str = "",
                          attendees: Optional[List[str]] = None, timezone: str = DEFAULT_TIMEZONE) -> Dict[str, Any]:
        """Creates a new calendar event and reports any scheduling conflicts."""
        try:
            conflicts = await self._check_conflicts(calendar_id, start_datetime, end_datetime)
            
            # Check if this should be an all-day event
            start_dt = self._normalize_datetime(start_datetime)
            end_dt = self._normalize_datetime(end_datetime)
            
            is_all_day = self._is_all_day_event(start_dt, end_dt)
            
            if is_all_day:
                # All-day events use date field and end date should be the next day
                start_date = start_dt.date().isoformat()
                
                # For all-day events, if end time is 23:59:59 of same day, 
                # the end date should be the next day
                if (end_dt.hour == 23 and end_dt.minute == 59 and end_dt.second == 59 and
                    end_dt.date() == start_dt.date()):
                    # Add one day for Google Calendar all-day event format
                    end_date = (end_dt.date() + timedelta(days=1)).isoformat()
                else:
                    end_date = end_dt.date().isoformat()
                
                event = {
                    'summary': summary,
                    'location': location,
                    'description': description,
                    'start': {'date': start_date},
                    'end': {'date': end_date},
                }
                logger.info(f"Creating all-day event from {start_date} to {end_date}")
            else:
                # Timed events use dateTime field
                event = {
                    'summary': summary,
                    'location': location,
                    'description': description,
                    'start': {'dateTime': start_datetime, 'timeZone': timezone},
                    'end': {'dateTime': end_datetime, 'timeZone': timezone},
                }
                logger.info(f"Creating timed event from {start_datetime} to {end_datetime}")
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            created_event = await asyncio.to_thread(
                self.calendar_service.events().insert(calendarId=calendar_id, body=event).execute
            )
            
            logger.info(f"Calendar event created: {created_event['id']}")
            return self._create_conflict_response(created_event, conflicts)
            
        except HttpError as error:
            return self._handle_http_error(error, "creating event")

    async def list_events(self, calendar_id: str = 'primary', max_results: int = DEFAULT_MAX_RESULTS,
                         time_min: Optional[str] = None, time_max: Optional[str] = None) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """Lists upcoming events from a calendar."""
        try:
            if time_min is None:
                time_min = datetime.now(tz=tz.UTC).isoformat().replace('+00:00', 'Z')
            
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
            return [self._format_event_info(event) for event in events]
            
        except HttpError as error:
            return self._handle_http_error(error, "listing events")

    async def get_event(self, calendar_id: str, event_id: str) -> Union[Dict[str, Any], Dict[str, str]]:
        """Gets details of a specific calendar event."""
        try:
            event = await asyncio.to_thread(
                self.calendar_service.events().get(calendarId=calendar_id, eventId=event_id).execute
            )
            
            return self._format_event_info(event)
        except HttpError as error:
            return self._handle_http_error(error, f"getting event {event_id}")

    async def update_event(self, calendar_id: str, event_id: str, 
                          summary: Optional[str] = None,
                          description: Optional[str] = None,
                          location: Optional[str] = None,
                          start_datetime: Optional[str] = None,
                          end_datetime: Optional[str] = None,
                          timezone: str = DEFAULT_TIMEZONE) -> Dict[str, Any]:
        """Updates an existing calendar event and reports any scheduling conflicts."""
        try:
            event = await asyncio.to_thread(
                self.calendar_service.events().get(calendarId=calendar_id, eventId=event_id).execute
            )
            
            # Update provided fields
            updates = {
                'summary': summary,
                'description': description, 
                'location': location
            }
            
            for field, value in updates.items():
                if value is not None:
                    event[field] = value
            
            # Update datetime fields
            if start_datetime is not None:
                event['start'] = {'dateTime': start_datetime, 'timeZone': timezone}
            if end_datetime is not None:
                event['end'] = {'dateTime': end_datetime, 'timeZone': timezone}
            
            # Check for conflicts if time was changed
            conflicts = []
            if start_datetime is not None or end_datetime is not None:
                final_start = start_datetime or event['start'].get('dateTime', event['start'].get('date'))
                final_end = end_datetime or event['end'].get('dateTime', event['end'].get('date'))
                
                if final_start and final_end:
                    conflicts = await self._check_conflicts(calendar_id, final_start, final_end, exclude_event_id=event_id)
            
            updated_event = await asyncio.to_thread(
                self.calendar_service.events().update(
                    calendarId=calendar_id, eventId=event_id, body=event
                ).execute
            )
            
            logger.info(f"Calendar event updated: {event_id}")
            return self._create_conflict_response(updated_event, conflicts)
            
        except HttpError as error:
            return self._handle_http_error(error, f"updating event {event_id}")

    async def delete_event(self, calendar_id: str, event_id: str) -> Union[str, Dict[str, str]]:
        """Deletes a calendar event."""
        try:
            await asyncio.to_thread(
                self.calendar_service.events().delete(calendarId=calendar_id, eventId=event_id).execute
            )
            
            logger.info(f"Calendar event deleted: {event_id}")
            return f"Calendar event {event_id} deleted successfully."
        except HttpError as error:
            return self._handle_http_error(error, f"deleting event {event_id}")

    async def create_quick_event(self, calendar_id: str, text: str) -> Dict[str, Any]:
        """Creates an event using natural language and reports any scheduling conflicts."""
        try:
            event = await asyncio.to_thread(
                self.calendar_service.events().quickAdd(calendarId=calendar_id, text=text).execute
            )
            
            logger.info(f"Quick calendar event created: {event['id']}")
            
            # Check for conflicts after creation (Google parses the time for us)
            conflicts = []
            if 'start' in event and 'end' in event:
                start_time = event['start'].get('dateTime', event['start'].get('date'))
                end_time = event['end'].get('dateTime', event['end'].get('date'))
                
                if start_time and end_time:
                    conflicts = await self._check_conflicts(calendar_id, start_time, end_time, exclude_event_id=event['id'])
            
            return self._create_conflict_response(event, conflicts)
            
        except HttpError as error:
            return self._handle_http_error(error, "creating quick event")

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
        try:
            new_start = self._normalize_datetime(start_datetime)
            new_end = self._normalize_datetime(end_datetime)
            
            api_time_min = new_start.isoformat()
            api_time_max = new_end.isoformat()
            
            logger.info(f"Querying calendar events from {api_time_min} to {api_time_max}")
            
            events_result = await asyncio.to_thread(
                self.calendar_service.events().list(
                    calendarId=calendar_id,
                    timeMin=api_time_min,
                    timeMax=api_time_max,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute
            )
            
            events = events_result.get('items', [])
            conflicts = []
            
            for event in events:
                if self._should_skip_event(event, exclude_event_id):
                    continue
                
                event_start_str = event['start'].get('dateTime', event['start'].get('date'))
                event_end_str = event['end'].get('dateTime', event['end'].get('date'))
                
                if not event_start_str or not event_end_str:
                    continue
                
                event_start = self._normalize_datetime(event_start_str)
                event_end = self._normalize_datetime(event_end_str)
                
                logger.info(f"Checking conflict: New event ({new_start} to {new_end}) vs Existing '{event.get('summary')}' ({event_start} to {event_end})")
                
                # Check for overlap: events overlap if one starts before the other ends
                if self._events_overlap(new_start, new_end, event_start, event_end):
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
                    logger.info("Conflict detected")
                else:
                    logger.info("No conflict")
            
            logger.info(f"Conflict check completed: found {len(conflicts)} conflicts")
            return conflicts
            
        except Exception as error:
            logger.error(f"Error checking calendar conflicts: {error}")
            return []  # Return empty list on error - don't block event creation
    
    def _should_skip_event(self, event: Dict[str, Any], exclude_event_id: Optional[str]) -> bool:
        """Check if an event should be skipped during conflict checking."""
        return (
            (exclude_event_id and event.get('id') == exclude_event_id) or
            event.get('status') == 'cancelled'
        )
    
    def _events_overlap(self, start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
        """Check if two time ranges overlap."""
        return start1 < end2 and end1 > start2
    
    def _is_all_day_event(self, start_dt: datetime, end_dt: datetime) -> bool:
        """
        Determine if the given start and end datetime represent an all-day event.
        
        An all-day event is detected when:
        1. Start time is at 00:00:00 (midnight)
        2. End time is either:
           - 00:00:00 of the next day, OR 
           - 23:59:59 of the same day
        """
        # Check if start is at midnight (00:00:00)
        start_is_midnight = (start_dt.hour == 0 and start_dt.minute == 0 and start_dt.second == 0)
        
        if not start_is_midnight:
            return False
            
        # Check if end is at midnight of next day
        if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
            # Should be exactly one day later
            return (end_dt.date() - start_dt.date()).days == 1
            
        # Check if end is at 23:59:59 of the same day
        if (end_dt.hour == 23 and end_dt.minute == 59 and end_dt.second == 59 and
            end_dt.date() == start_dt.date()):
            return True
            
        return False