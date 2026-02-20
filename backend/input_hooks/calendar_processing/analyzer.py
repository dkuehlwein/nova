"""
Meeting analyzer module.

Analyzes calendar events to determine if they need preparation and extracts
meeting information for memo generation.
"""

from datetime import datetime, date
from typing import Dict, Any, List, Optional

from utils.logging import get_logger
from ..models import CalendarMeetingInfo
from ..datetime_utils import parse_datetime

logger = get_logger(__name__)


class MeetingAnalyzer:
    """
    Analyzes calendar events to determine preparation needs.
    
    Filters events and extracts structured meeting information
    for the memo generation process.
    """
    
    def __init__(self, min_duration_minutes: int = 15):
        self.min_duration_minutes = min_duration_minutes
        
        # Keywords that suggest a meeting needs preparation
        self.prep_keywords = [
            'meeting', 'call', 'standup', 'sync', 'review', 'demo', 
            'presentation', 'discussion', 'interview', 'client',
            'strategy', 'planning', 'retrospective', 'kickoff'
        ]
        
        # Keywords that suggest meetings don't need prep
        self.skip_keywords = [
            'lunch', 'break', 'personal', 'holiday', 'vacation',
            'blocked', 'focus time', 'deep work', 'commute'
        ]
    
    def analyze_events(self, raw_events: List[Dict[str, Any]], 
                      include_all_day: bool = False,
                      target_date: Optional[date] = None) -> List[CalendarMeetingInfo]:
        """
        Analyze raw calendar events and extract meetings that need preparation.
        
        Args:
            raw_events: Raw events from Google Calendar API
            include_all_day: Whether to include all-day events
            target_date: Only analyze events on this date (defaults to today)
            
        Returns:
            List of CalendarMeetingInfo objects for meetings needing prep
        """
        if target_date is None:
            target_date = date.today()
            
        meetings_needing_prep = []
        
        for event in raw_events:
            try:
                meeting_info = self._analyze_single_event(event, include_all_day, target_date)
                if meeting_info and self._should_prepare_for_meeting(meeting_info):
                    meetings_needing_prep.append(meeting_info)
                    
            except Exception as e:
                logger.error(
                    "Failed to analyze event",
                    exc_info=True,
                    extra={"data": {"event_id": event.get('id', 'unknown'), "error": str(e)}}
                )
                continue
        
        logger.info(
            "Analyzed events for preparation needs",
            extra={"data": {
                "total_events": len(raw_events),
                "meetings_needing_prep": len(meetings_needing_prep)
            }}
        )
        
        return meetings_needing_prep
    
    def _analyze_single_event(self, event: Dict[str, Any], 
                             include_all_day: bool,
                             target_date: date) -> Optional[CalendarMeetingInfo]:
        """
        Analyze a single calendar event and extract meeting information.
        
        Args:
            event: Raw event from Google Calendar API
            include_all_day: Whether to include all-day events
            target_date: Only process events on this date
            
        Returns:
            CalendarMeetingInfo object or None if event should be skipped
        """
        try:
            # Extract basic event info
            event_id = event.get('id', '')
            title = event.get('summary', 'No Title')
            description = event.get('description', '')
            location = event.get('location', '')
            
            # Parse start and end times
            start_time = parse_datetime(event.get('start', {}), source_type="calendar", fallback_to_now=False)
            end_time = parse_datetime(event.get('end', {}), source_type="calendar", fallback_to_now=False)
            
            if not start_time or not end_time:
                logger.debug("Skipping event - invalid date/time", extra={"data": {"event_id": event_id}})
                return None
            
            # Filter by target date - only process events that occur on the target date
            event_date = start_time.date()
            if event_date != target_date:
                logger.debug("Skipping event, not on target date", extra={"data": {"event_id": event_id, "target_date": str(target_date), "event_date": str(event_date)}})
                return None
            
            # Check if it's an all-day event
            # For MCP format: all-day events have just date strings (no time)
            start_field = event.get('start', '')
            is_all_day = (isinstance(start_field, str) and 'T' not in start_field) or \
                        (isinstance(start_field, dict) and 'date' in start_field)
            
            if is_all_day and not include_all_day:
                logger.debug("Skipping all-day event", extra={"data": {"event_id": event_id}})
                return None
            
            # Calculate duration
            duration = end_time - start_time
            duration_minutes = int(duration.total_seconds() / 60)
            
            # Skip very short events
            if duration_minutes < self.min_duration_minutes:
                logger.debug(
                    "Skipping short event",
                    extra={"data": {"event_id": event_id, "duration_minutes": duration_minutes}}
                )
                return None
            
            # Extract attendees
            attendees = self._extract_attendees(event.get('attendees', []))
            
            # Extract organizer
            organizer_info = event.get('organizer', {})
            organizer = organizer_info.get('email', organizer_info.get('displayName', ''))
            
            meeting_info = CalendarMeetingInfo(
                meeting_id=event_id,
                title=title,
                attendees=attendees,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                location=location,
                description=description,
                organizer=organizer,
                calendar_id='primary'  # Default for now
            )
            
            logger.debug(
                "Parsed meeting info",
                extra={"data": {
                    "event_id": event_id,
                    "title": title,
                    "duration_minutes": duration_minutes,
                    "attendee_count": len(attendees)
                }}
            )
            
            return meeting_info
            
        except Exception as e:
            logger.error(
                "Error parsing event",
                exc_info=True,
                extra={"data": {"event_id": event.get('id', 'unknown'), "error": str(e)}}
            )
            return None
    
    def _should_prepare_for_meeting(self, meeting: CalendarMeetingInfo) -> bool:
        """
        Determine if a meeting needs preparation based on its characteristics.
        
        Args:
            meeting: CalendarMeetingInfo object
            
        Returns:
            True if meeting needs preparation, False otherwise
        """
        try:
            title_lower = meeting.title.lower()
            description_lower = meeting.description.lower()
            
            # Skip meetings that are already prep meetings (avoid double-prep)
            if title_lower.startswith('prep:'):
                logger.debug(
                    "Skipping meeting, already a prep meeting",
                    extra={"data": {"meeting_id": meeting.meeting_id}}
                )
                return False
            
            # Skip meetings with skip keywords
            for skip_word in self.skip_keywords:
                if skip_word in title_lower or skip_word in description_lower:
                    logger.debug(
                        "Skipping meeting, contains skip keyword",
                        extra={"data": {"meeting_id": meeting.meeting_id, "skip_keyword": skip_word}}
                    )
                    return False
            
            # Include meetings with prep keywords
            for prep_word in self.prep_keywords:
                if prep_word in title_lower or prep_word in description_lower:
                    logger.debug(
                        "Including meeting, contains prep keyword",
                        extra={"data": {"meeting_id": meeting.meeting_id, "prep_keyword": prep_word}}
                    )
                    return True
            
            # Include meetings with multiple attendees (likely collaborative)
            if len(meeting.attendee_emails) >= 2:  # Including you + others
                logger.debug(
                    "Including meeting, multiple attendees",
                    extra={"data": {"meeting_id": meeting.meeting_id, "attendee_count": len(meeting.attendee_emails)}}
                )
                return True
            
            # Include longer meetings (likely important)
            if meeting.duration_minutes >= 60:
                logger.debug(
                    "Including meeting, long duration",
                    extra={"data": {"meeting_id": meeting.meeting_id, "duration_minutes": meeting.duration_minutes}}
                )
                return True
            
            # Skip solo/personal meetings
            if len(meeting.attendee_emails) <= 1 and meeting.duration_minutes < 60:
                logger.debug(
                    "Skipping meeting, appears to be personal/solo time",
                    extra={"data": {"meeting_id": meeting.meeting_id}}
                )
                return False
            
            # Default: include if uncertain (err on side of preparation)
            logger.debug(
                "Including meeting, default inclusion",
                extra={"data": {"meeting_id": meeting.meeting_id}}
            )
            return True
            
        except Exception as e:
            logger.error("Error determining prep need for meeting", extra={"data": {"meeting_id": str(meeting.meeting_id), "error": str(e)}})
            # Default to including the meeting if there's an error
            return True
    
    def _extract_attendees(self, attendees_list: List[Dict[str, Any]]) -> List[str]:
        """
        Extract attendee information from Google Calendar API format.
        
        Args:
            attendees_list: List of attendee dictionaries from API
            
        Returns:
            List of attendee email addresses
        """
        attendees = []
        
        for attendee in attendees_list:
            if isinstance(attendee, dict):
                email = attendee.get('email', '')
                display_name = attendee.get('displayName', '')
                
                # Use email if available, otherwise display name
                if email:
                    attendees.append(email)
                elif display_name:
                    attendees.append(display_name)
            elif isinstance(attendee, str):
                attendees.append(attendee)
        
        return attendees