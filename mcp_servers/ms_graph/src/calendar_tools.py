"""
Calendar Tools - Calendar operations via MS Graph API.

Provides tools matching google-workspace pattern for calendar operations.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union

from dateutil import parser as date_parser

if TYPE_CHECKING:
    from .service import MSGraphService

logger = logging.getLogger(__name__)


class CalendarTools:
    """Calendar operations via MS Graph API."""

    DEFAULT_TIMEZONE = "Europe/Berlin"

    def __init__(self, service: "MSGraphService"):
        """
        Initialize calendar tools.

        Args:
            service: MSGraphService instance for API access
        """
        self.service = service

    async def list_calendar_events(
        self,
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
        try:
            client = await self.service.ensure_client()

            # Calculate time range
            now = datetime.now(timezone.utc)
            end_time = now + timedelta(days=days_ahead)

            # Build query parameters
            params = {
                "$top": limit,
                "$select": "id,subject,start,end,location,attendees,isAllDay,organizer",
                "$orderby": "start/dateTime",
                "$filter": f"start/dateTime ge '{now.isoformat()}' and start/dateTime le '{end_time.isoformat()}'",
            }

            # Choose endpoint based on calendar_id
            if calendar_id and calendar_id != "primary":
                endpoint = f"/me/calendars/{calendar_id}/events"
            else:
                endpoint = "/me/events"

            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()

            # Transform to match expected format
            results = []
            for event in data.get("value", []):
                # Extract attendees
                attendees = [
                    a.get("emailAddress", {}).get("address", "")
                    for a in event.get("attendees", [])
                ]

                # Extract location
                location = event.get("location", {})
                location_str = location.get("displayName", "") if isinstance(location, dict) else ""

                results.append({
                    "id": event["id"],
                    "subject": event.get("subject") or "(No Subject)",
                    "start": event.get("start", {}).get("dateTime", ""),
                    "end": event.get("end", {}).get("dateTime", ""),
                    "location": location_str,
                    "attendees": attendees,
                    "is_all_day": event.get("isAllDay", False),
                    "organizer": event.get("organizer", {}).get("emailAddress", {}).get("address", ""),
                })

            return results

        except Exception as e:
            return self.service.handle_tool_error(e, "listing calendar events")

    async def create_event(
        self,
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
            Created event details
        """
        try:
            client = await self.service.ensure_client()

            # Parse datetimes
            start_dt = date_parser.parse(start_datetime)
            end_dt = date_parser.parse(end_datetime)

            # Build event payload
            event = {
                "subject": summary,
                "start": {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": self.DEFAULT_TIMEZONE,
                },
                "end": {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": self.DEFAULT_TIMEZONE,
                },
            }

            if description:
                event["body"] = {
                    "contentType": "Text",
                    "content": description,
                }

            if location:
                event["location"] = {
                    "displayName": location,
                }

            if attendees:
                event["attendees"] = [
                    {
                        "emailAddress": {"address": email},
                        "type": "required",
                    }
                    for email in attendees
                ]

            # Choose endpoint based on calendar_id
            if calendar_id and calendar_id != "primary":
                endpoint = f"/me/calendars/{calendar_id}/events"
            else:
                endpoint = "/me/events"

            response = await client.post(endpoint, json=event)
            response.raise_for_status()
            created = response.json()

            return {
                "status": "success",
                "message": f"Event created: {summary}",
                "event_id": created.get("id"),
                "subject": summary,
                "start": start_datetime,
                "end": end_datetime,
                "web_link": created.get("webLink", ""),
            }

        except Exception as e:
            return self.service.handle_tool_error(e, "creating event")

    async def update_event(
        self,
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
        try:
            client = await self.service.ensure_client()

            # Build update payload with only provided fields
            update_data = {}

            if summary is not None:
                update_data["subject"] = summary

            if start_datetime is not None:
                start_dt = date_parser.parse(start_datetime)
                update_data["start"] = {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": self.DEFAULT_TIMEZONE,
                }

            if end_datetime is not None:
                end_dt = date_parser.parse(end_datetime)
                update_data["end"] = {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": self.DEFAULT_TIMEZONE,
                }

            if description is not None:
                update_data["body"] = {
                    "contentType": "Text",
                    "content": description,
                }

            if location is not None:
                update_data["location"] = {
                    "displayName": location,
                }

            if not update_data:
                return {"error": "No fields provided to update"}

            # PATCH the event
            response = await client.patch(f"/me/events/{event_id}", json=update_data)
            response.raise_for_status()
            updated = response.json()

            return {
                "status": "success",
                "message": f"Event updated: {updated.get('subject', event_id)}",
                "event_id": event_id,
                "updated_fields": list(update_data.keys()),
            }

        except Exception as e:
            return self.service.handle_tool_error(e, "updating event")

    async def delete_event(self, event_id: str) -> Dict[str, str]:
        """
        Delete a calendar event by its ID.

        Args:
            event_id: The ID of the event to delete

        Returns:
            Confirmation of deletion
        """
        try:
            client = await self.service.ensure_client()

            response = await client.delete(f"/me/events/{event_id}")
            response.raise_for_status()

            return {
                "status": "success",
                "message": f"Event deleted: {event_id}",
                "event_id": event_id,
            }

        except Exception as e:
            return self.service.handle_tool_error(e, "deleting event")
