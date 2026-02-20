"""
Shared datetime parsing utilities for input hooks.

Consolidates datetime parsing logic that was duplicated across components.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
from dateutil.parser import parse as dateutil_parse
from email.utils import parsedate_to_datetime

from utils.logging import get_logger

logger = get_logger(__name__)


def parse_datetime(
    datetime_input: Union[str, Dict[str, Any], None], 
    source_type: str = "generic",
    fallback_to_now: bool = True
) -> Optional[datetime]:
    """
    Universal datetime parser for all input hook types.
    
    Handles:
    - Email dates (RFC 2822 format): "Mon, 31 Aug 2025 10:00:00 +0200"
    - Calendar event strings: "2025-08-31T10:00:00+02:00" 
    - Google Calendar API objects: {"dateTime": "...", "timeZone": "..."} or {"date": "2025-08-31"}
    - ISO 8601 strings: "2025-08-31T10:00:00Z"
    - None values with optional fallback
    
    Args:
        datetime_input: The datetime value to parse (string, dict, or None)
        source_type: Source type for logging context ("email", "calendar", etc.)
        fallback_to_now: Whether to return current UTC time if parsing fails
        
    Returns:
        Parsed datetime object, current time (if fallback_to_now=True), or None
    """
    return _parse_datetime_impl(datetime_input, source_type, fallback_to_now)


def _parse_datetime_impl(
    datetime_input: Union[str, Dict[str, Any], None], 
    source_type: str = "generic",
    fallback_to_now: bool = True
) -> Optional[datetime]:
    """Internal implementation for datetime parsing."""
    if datetime_input is None:
        if fallback_to_now:
            return datetime.now(timezone.utc)
        return None
        
    try:
        if isinstance(datetime_input, str):
            # String format - try different parsers based on source type
            if source_type == "email":
                try:
                    # First try Python's built-in email date parser (RFC 2822 compliant)
                    return parsedate_to_datetime(datetime_input)
                except (ValueError, TypeError):
                    pass  # Fall through to dateutil
            
            # Use dateutil for ISO 8601, calendar events, and fallback
            return dateutil_parse(datetime_input)
            
        elif isinstance(datetime_input, dict):
            # Calendar API format (Google Calendar, Outlook, etc.)
            if 'dateTime' in datetime_input:
                # Timed event
                return dateutil_parse(datetime_input['dateTime'])
            elif 'date' in datetime_input:
                # All-day event - parse as date and set to start of day
                date_obj = dateutil_parse(datetime_input['date']).date()
                return datetime.combine(date_obj, datetime.min.time())
            else:
                logger.warning("Unknown datetime dict format", extra={"data": {"source_type": source_type, "datetime_input": datetime_input}})
                return None if not fallback_to_now else datetime.now(timezone.utc)
                
        else:
            logger.warning("Unknown datetime input type", extra={"data": {"source_type": source_type, "type": type(datetime_input).__name__}})
            return None if not fallback_to_now else datetime.now(timezone.utc)
            
    except Exception as e:
        logger.error("Failed to parse datetime", extra={"data": {"source_type": source_type, "datetime_input": datetime_input, "error": str(e)}})
        return None if not fallback_to_now else datetime.now(timezone.utc)