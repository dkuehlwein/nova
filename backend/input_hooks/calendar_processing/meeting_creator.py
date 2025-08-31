"""
Meeting creator module.

Creates private preparation meetings in Google Calendar with AI-generated memos
as meeting descriptions. These prep meetings are scheduled before the actual meetings.
"""

from datetime import timedelta
from typing import Optional

from utils.logging import get_logger
from mcp_client import mcp_manager
from ..models import CalendarMeetingInfo

logger = get_logger(__name__)


class MeetingCreator:
    """
    Creates private preparation meetings in Google Calendar.
    
    Schedules prep meetings before actual meetings with AI-generated 
    memos as the meeting description. These are private to you only.
    """
    
    def __init__(self, prep_time_minutes: int = 15):
        self.prep_time_minutes = prep_time_minutes
        self.prep_title_prefix = "PREP:"
        
    async def create_prep_meeting(self, original_meeting: CalendarMeetingInfo, 
                                 memo_text: str, 
                                 calendar_id: str = "primary") -> Optional[str]:
        """
        Create a private preparation meeting with memo as description.
        
        Args:
            original_meeting: The meeting to prepare for
            memo_text: AI-generated memo content
            calendar_id: Calendar to create the prep meeting in
            
        Returns:
            Event ID of created prep meeting, or None if failed
        """
        try:
            # Calculate prep meeting time (before original meeting)
            prep_start_time = original_meeting.start_time - timedelta(minutes=self.prep_time_minutes)
            prep_end_time = original_meeting.start_time
            
            # Create prep meeting title
            prep_title = f"{self.prep_title_prefix} {original_meeting.title}"
            
            # Format times for Google Calendar API
            prep_start_iso = prep_start_time.isoformat()
            prep_end_iso = prep_end_time.isoformat()
            
            logger.info(
                f"Creating prep meeting for: {original_meeting.title}",
                extra={"data": {
                    "original_meeting_id": original_meeting.meeting_id,
                    "prep_start": prep_start_iso,
                    "prep_title": prep_title
                }}
            )
            
            # Get calendar MCP tools
            tools = await mcp_manager.get_tools()
            create_event_tool = None
            
            # Find calendar create event tool
            for tool in tools:
                if hasattr(tool, 'name') and 'calendar' in tool.name.lower() and 'create' in tool.name.lower():
                    create_event_tool = tool
                    break
            
            if not create_event_tool:
                logger.error("No calendar create event tool found in MCP servers")
                return None
            
            # Create the prep meeting
            tool_result = await create_event_tool.ainvoke({
                "calendar_id": calendar_id,
                "summary": prep_title,
                "start_datetime": prep_start_iso,
                "end_datetime": prep_end_iso,
                "description": memo_text,
                "location": f"Prep for: {original_meeting.location}" if original_meeting.location else "",
            })
            
            # Extract event ID from result
            event_id = self._extract_event_id(tool_result)
            
            if event_id:
                logger.info(
                    f"Successfully created prep meeting: {event_id}",
                    extra={"data": {
                        "prep_event_id": event_id,
                        "original_meeting_id": original_meeting.meeting_id,
                        "prep_title": prep_title
                    }}
                )
                return event_id
            else:
                logger.warning(f"Created prep meeting but couldn't extract event ID")
                return None
                
        except Exception as e:
            logger.error(
                f"Error creating prep meeting for {original_meeting.meeting_id}: {str(e)}",
                exc_info=True,
                extra={"data": {
                    "original_meeting_id": original_meeting.meeting_id,
                    "error": str(e)
                }}
            )
            return None
    
    async def check_prep_meeting_exists(self, original_meeting: CalendarMeetingInfo, 
                                       calendar_id: str = "primary") -> bool:
        """
        Check if a prep meeting already exists for the given meeting.
        
        This helps avoid creating duplicate prep meetings.
        
        Args:
            original_meeting: The meeting to check prep meeting for
            calendar_id: Calendar to search in
            
        Returns:
            True if prep meeting already exists, False otherwise
        """
        try:
            # Calculate expected prep meeting time range
            prep_start_time = original_meeting.start_time - timedelta(minutes=self.prep_time_minutes + 5)
            prep_end_time = original_meeting.start_time + timedelta(minutes=5)
            
            # Format for API search
            time_min = prep_start_time.isoformat()
            time_max = prep_end_time.isoformat()
            
            # Get calendar MCP tools
            tools = await mcp_manager.get_tools()
            list_events_tool = None
            
            # Find calendar list events tool
            for tool in tools:
                if hasattr(tool, 'name') and 'calendar' in tool.name.lower() and 'list' in tool.name.lower():
                    list_events_tool = tool
                    break
            
            if not list_events_tool:
                logger.warning("No calendar list events tool found for checking existing prep meetings")
                return False
            
            # Search for events in the prep time window
            tool_result = await list_events_tool.ainvoke({
                "calendar_id": calendar_id,
                "time_min": time_min,
                "time_max": time_max,
                "max_results": 10
            })
            
            # Check if any events are prep meetings for this specific meeting
            events = []
            if isinstance(tool_result, list):
                events = tool_result
            elif isinstance(tool_result, dict) and "events" in tool_result:
                events = tool_result["events"]
            expected_title = f"{self.prep_title_prefix} {original_meeting.title}"
            
            for event in events:
                event_title = event.get('summary', '')
                if event_title == expected_title:
                    logger.debug(
                        f"Found existing prep meeting for {original_meeting.meeting_id}",
                        extra={"data": {
                            "existing_event_id": event.get('id'),
                            "prep_title": event_title
                        }}
                    )
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for existing prep meeting: {e}")
            # Return False to allow creation attempt if check fails
            return False
    
    async def update_prep_meeting(self, prep_event_id: str, 
                                 updated_memo: str,
                                 calendar_id: str = "primary") -> bool:
        """
        Update an existing prep meeting with new memo content.
        
        Args:
            prep_event_id: ID of the prep meeting to update
            updated_memo: New memo content
            calendar_id: Calendar containing the prep meeting
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            logger.info(
                f"Updating prep meeting {prep_event_id} with new memo",
                extra={"data": {"prep_event_id": prep_event_id}}
            )
            
            # Get calendar MCP tools  
            tools = await mcp_manager.get_tools()
            update_event_tool = None
            
            # Find calendar update event tool
            for tool in tools:
                if hasattr(tool, 'name') and 'calendar' in tool.name.lower() and 'update' in tool.name.lower():
                    update_event_tool = tool
                    break
            
            if not update_event_tool:
                logger.error("No calendar update event tool found in MCP servers")
                return False
                
            tool_result = await update_event_tool.ainvoke({
                "calendar_id": calendar_id,
                "event_id": prep_event_id,
                "description": updated_memo
            })
            
            logger.info(f"Successfully updated prep meeting {prep_event_id}")
            return True
                
        except Exception as e:
            logger.error(f"Error updating prep meeting {prep_event_id}: {e}")
            return False
    
    def _extract_event_id(self, api_result) -> Optional[str]:
        """
        Extract event ID from Google Calendar API result.
        
        Args:
            api_result: Result from calendar creation API
            
        Returns:
            Event ID string or None if not found
        """
        try:
            if isinstance(api_result, dict):
                # Direct event object
                if 'id' in api_result:
                    return api_result['id']
                
                # Wrapped result
                if 'event_id' in api_result:
                    return api_result['event_id']
                
                # Check nested structures
                if 'event' in api_result and isinstance(api_result['event'], dict):
                    return api_result['event'].get('id')
            
            elif isinstance(api_result, str):
                # Sometimes the result might be just the ID string
                return api_result
            
            logger.warning(f"Couldn't extract event ID from result: {type(api_result)}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting event ID: {e}")
            return None
    
    def format_memo_for_description(self, memo_text: str, original_meeting: CalendarMeetingInfo) -> str:
        """
        Format the memo text for use as a calendar event description.
        
        Args:
            memo_text: Raw memo text from AI generation
            original_meeting: Original meeting info
            
        Returns:
            Formatted description for calendar event
        """
        try:
            # Add header with original meeting info
            header = f"MEETING PREPARATION\n{'=' * 50}\n"
            header += f"For: {original_meeting.title}\n"
            header += f"Original Time: {original_meeting.start_time.strftime('%I:%M %p')}\n"
            header += f"Duration: {original_meeting.duration_minutes} minutes\n\n"
            
            # Add the memo content
            formatted_description = header + memo_text
            
            # Add footer
            footer = f"\n\n{'=' * 50}\n"
            footer += f"Generated by Nova Calendar Hook\n"
            footer += f"Prep meeting: {self.prep_time_minutes} minutes before actual meeting"
            
            return formatted_description + footer
            
        except Exception as e:
            logger.error(f"Error formatting memo description: {e}")
            # Return original memo if formatting fails
            return memo_text