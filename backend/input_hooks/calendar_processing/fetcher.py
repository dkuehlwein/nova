"""
Calendar fetcher module.

Handles fetching calendar events from Google Calendar via MCP tools.
Similar to EmailFetcher but focused on calendar events.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from utils.logging import get_logger
from mcp_client import mcp_manager

logger = get_logger(__name__)


class CalendarFetcher:
    """
    Fetches calendar events from Google Calendar via MCP tools.

    Handles the MCP integration for calendar data retrieval,
    similar to how EmailFetcher handles email MCP integration.
    """

    def __init__(self):
        # Tool name follows ADR-015 MCP Tool Namespacing: server_name-tool_name
        self.tool_name = "google_workspace-list_events"
        
    async def fetch_todays_events(self, calendar_id: str = "primary", 
                                 look_ahead_days: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch today's calendar events.
        
        Args:
            calendar_id: Calendar to fetch from (default: "primary")
            look_ahead_days: Number of days to look ahead (default: 1 = today only)
            
        Returns:
            List of raw calendar event dictionaries from Google Calendar API
        """
        try:
            # Calculate time range (today only by default)
            now = datetime.now(timezone.utc)
            start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_period = start_of_today + timedelta(days=look_ahead_days)
            
            # Format for Google Calendar API
            time_min = start_of_today.isoformat().replace('+00:00', 'Z')
            time_max = end_of_period.isoformat().replace('+00:00', 'Z')
            
            logger.info(
                f"Fetching calendar events from {calendar_id}",
                extra={"data": {
                    "calendar_id": calendar_id,
                    "time_min": time_min,
                    "time_max": time_max,
                    "look_ahead_days": look_ahead_days
                }}
            )
            
            # Get calendar MCP tools
            tools = await mcp_manager.get_tools()
            calendar_tool = None

            # Find calendar list events tool (prefixed per ADR-015)
            for tool in tools:
                tool_name = getattr(tool, 'name', '')
                # Look for the prefixed name: google_workspace-list_events
                if tool_name == self.tool_name:
                    calendar_tool = tool
                    break
                # Fallback: any tool with calendar and list in the name
                if 'list' in tool_name.lower() and 'event' in tool_name.lower():
                    calendar_tool = tool

            if not calendar_tool:
                logger.error("No calendar list events tool found in MCP servers")
                return []
            
            # Call the calendar tool (remove time_max and max_results - not supported)
            tool_result = await calendar_tool.ainvoke({
                "calendar_id": calendar_id,
                "time_min": time_min,
            })
            
            # Parse the result - should be a list of event dictionaries
            events = []
            if isinstance(tool_result, list):
                events = tool_result
            elif isinstance(tool_result, dict) and "events" in tool_result:
                events = tool_result["events"]
            elif isinstance(tool_result, str):
                # Sometimes results come back as JSON strings
                import json
                try:
                    parsed = json.loads(tool_result)
                    if isinstance(parsed, list):
                        events = parsed
                    elif isinstance(parsed, dict) and "events" in parsed:
                        events = parsed["events"]
                except json.JSONDecodeError:
                    logger.warning("Failed to parse tool result as JSON", extra={"data": {"tool_result": tool_result}})
                    return []
            else:
                logger.warning("Unexpected calendar result format", extra={"data": {"type": type(tool_result)}})
                return []
            
            logger.info(
                f"Successfully fetched {len(events)} calendar events",
                extra={"data": {
                    "calendar_id": calendar_id,
                    "event_count": len(events)
                }}
            )
            
            return events
            
        except Exception as e:
            logger.error(
                f"Failed to fetch calendar events: {str(e)}",
                exc_info=True,
                extra={"data": {
                    "calendar_id": calendar_id,
                    "error": str(e)
                }}
            )
            return []
    
    async def fetch_specific_event(self, calendar_id: str, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific calendar event by ID.
        
        Args:
            calendar_id: Calendar containing the event
            event_id: Event ID to fetch
            
        Returns:
            Event dictionary or None if not found
        """
        try:
            logger.info(
                f"Fetching specific calendar event",
                extra={"data": {
                    "calendar_id": calendar_id,
                    "event_id": event_id
                }}
            )
            
            # Get calendar MCP tools
            tools = await mcp_manager.get_tools()
            get_event_tool = None

            # Find calendar get event tool (prefixed per ADR-015)
            for tool in tools:
                if hasattr(tool, 'name'):
                    name_lower = tool.name.lower()
                    # Match google_workspace-get_event or similar
                    if 'get' in name_lower and 'event' in name_lower:
                        get_event_tool = tool
                        break
            
            if not get_event_tool:
                logger.error("No calendar get event tool found in MCP servers")
                return None
            
            # Call the tool
            tool_result = await get_event_tool.ainvoke({
                "calendar_id": calendar_id,
                "event_id": event_id
            })
            
            logger.debug(
                f"Successfully fetched calendar event {event_id}",
                extra={"data": {"event_id": event_id}}
            )
            
            return tool_result
            
        except Exception as e:
            logger.error(
                f"Failed to fetch calendar event {event_id}: {str(e)}",
                exc_info=True,
                extra={"data": {
                    "calendar_id": calendar_id,
                    "event_id": event_id,
                    "error": str(e)
                }}
            )
            return None
    
