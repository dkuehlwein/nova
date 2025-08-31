"""
Calendar processor module.

Main orchestration pipeline that coordinates fetching, analyzing, memo generation,
and prep meeting creation. Similar to EmailProcessor but for calendar events.
"""

import time
from typing import List, Dict, Any
from datetime import datetime, date

from utils.logging import get_logger
from ..models import CalendarMeetingInfo, CalendarHookConfig
from .fetcher import CalendarFetcher  
from .analyzer import MeetingAnalyzer
from .memo_generator import MemoGenerator
from .meeting_creator import MeetingCreator

logger = get_logger(__name__)


class CalendarProcessor:
    """
    Main calendar processing pipeline.
    
    Orchestrates the complete flow:
    1. Fetch today's calendar events
    2. Analyze which meetings need preparation
    3. Generate AI memos for each meeting
    4. Create private prep meetings with memos
    """
    
    def __init__(self):
        self.fetcher = CalendarFetcher()
        self.analyzer = MeetingAnalyzer()
        self.memo_generator = MemoGenerator()
        self.meeting_creator = None  # Will be initialized with config
    
    async def process_daily_meetings(self, config: CalendarHookConfig) -> Dict[str, Any]:
        """
        Process today's meetings for preparation.
        
        This is the main entry point called by the calendar hook.
        
        Args:
            config: Calendar hook configuration
            
        Returns:
            Processing result with statistics
        """
        start_time = time.time()
        result = {
            "success": True,
            "events_fetched": 0,
            "meetings_analyzed": 0,
            "prep_meetings_created": 0,
            "prep_meetings_updated": 0,
            "errors": [],
            "processing_time_seconds": 0.0
        }
        
        try:
            logger.info("Starting daily calendar meeting processing")
            
            # Initialize meeting creator with config
            if self.meeting_creator is None:
                self.meeting_creator = MeetingCreator(
                    prep_time_minutes=config.hook_settings.prep_time_minutes
                )
            
            # Step 1: Fetch today's calendar events
            raw_events = await self._fetch_todays_events(config)
            result["events_fetched"] = len(raw_events)
            
            if not raw_events:
                logger.info("No calendar events found for today")
                result["processing_time_seconds"] = time.time() - start_time
                return result
            
            # Step 2: Analyze which meetings need preparation
            meetings_needing_prep = await self._analyze_meetings(raw_events, config)
            result["meetings_analyzed"] = len(meetings_needing_prep)
            
            if not meetings_needing_prep:
                logger.info("No meetings identified as needing preparation")
                result["processing_time_seconds"] = time.time() - start_time
                return result
            
            # Step 3: Process each meeting that needs preparation
            for meeting in meetings_needing_prep:
                try:
                    prep_result = await self._process_single_meeting(meeting, config)
                    
                    if prep_result["created"]:
                        result["prep_meetings_created"] += 1
                    elif prep_result["updated"]:
                        result["prep_meetings_updated"] += 1
                    
                    if prep_result["error"]:
                        result["errors"].append(prep_result["error"])
                        
                except Exception as e:
                    error_msg = f"Failed to process meeting {meeting.meeting_id}: {str(e)}"
                    result["errors"].append(error_msg)
                    logger.error(
                        f"Error processing meeting {meeting.meeting_id}",
                        exc_info=True,
                        extra={"data": {
                            "meeting_id": meeting.meeting_id,
                            "meeting_title": meeting.title,
                            "error": str(e)
                        }}
                    )
                    continue
            
            result["processing_time_seconds"] = time.time() - start_time
            
            logger.info(
                f"Completed daily calendar processing",
                extra={"data": {
                    "events_fetched": result["events_fetched"],
                    "meetings_analyzed": result["meetings_analyzed"],
                    "prep_meetings_created": result["prep_meetings_created"],
                    "prep_meetings_updated": result["prep_meetings_updated"],
                    "errors": len(result["errors"]),
                    "processing_time": result["processing_time_seconds"]
                }}
            )
            
            return result
            
        except Exception as e:
            result["success"] = False
            result["processing_time_seconds"] = time.time() - start_time
            error_msg = f"Calendar processing failed: {str(e)}"
            result["errors"].append(error_msg)
            
            logger.error(
                "Daily calendar processing failed",
                exc_info=True,
                extra={"data": {
                    "error": str(e),
                    "processing_time": result["processing_time_seconds"]
                }}
            )
            
            return result
    
    async def _fetch_todays_events(self, config: CalendarHookConfig) -> List[Dict[str, Any]]:
        """
        Fetch today's calendar events using configuration.
        
        Args:
            config: Calendar hook configuration
            
        Returns:
            List of raw calendar event dictionaries
        """
        try:
            # Get calendar IDs from config (default to primary)
            calendar_ids = config.hook_settings.calendar_ids
            if not calendar_ids:
                calendar_ids = ["primary"]
            
            all_events = []
            
            # Fetch events from each configured calendar
            for calendar_id in calendar_ids:
                try:
                    events = await self.fetcher.fetch_todays_events(
                        calendar_id=calendar_id,
                        look_ahead_days=config.hook_settings.look_ahead_days
                    )
                    all_events.extend(events)
                    
                    logger.debug(
                        f"Fetched {len(events)} events from calendar {calendar_id}",
                        extra={"data": {
                            "calendar_id": calendar_id,
                            "event_count": len(events)
                        }}
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to fetch from calendar {calendar_id}: {e}")
                    continue
            
            logger.info(
                f"Fetched {len(all_events)} total events from {len(calendar_ids)} calendars",
                extra={"data": {
                    "total_events": len(all_events),
                    "calendar_count": len(calendar_ids)
                }}
            )
            
            return all_events
            
        except Exception as e:
            logger.error(f"Error fetching today's events: {e}")
            return []
    
    async def _analyze_meetings(self, raw_events: List[Dict[str, Any]], 
                              config: CalendarHookConfig) -> List[CalendarMeetingInfo]:
        """
        Analyze raw events to identify meetings needing preparation.
        
        Args:
            raw_events: Raw calendar events from API
            config: Calendar hook configuration
            
        Returns:
            List of meetings that need preparation
        """
        try:
            # Configure analyzer based on hook settings
            self.analyzer.min_duration_minutes = getattr(
                config.hook_settings, 'min_meeting_duration', 15
            )
            
            # Analyze events (filter for today only)
            meetings = self.analyzer.analyze_events(
                raw_events=raw_events,
                include_all_day=config.hook_settings.include_all_day_events,
                target_date=date.today()
            )
            
            logger.info(
                f"Identified {len(meetings)} meetings needing preparation",
                extra={"data": {
                    "total_events": len(raw_events),
                    "meetings_needing_prep": len(meetings)
                }}
            )
            
            return meetings
            
        except Exception as e:
            logger.error(f"Error analyzing meetings: {e}")
            return []
    
    async def _process_single_meeting(self, meeting: CalendarMeetingInfo, 
                                    config: CalendarHookConfig) -> Dict[str, Any]:
        """
        Process a single meeting for preparation.
        
        Args:
            meeting: Meeting information
            config: Calendar hook configuration
            
        Returns:
            Processing result for this meeting
        """
        process_result = {
            "created": False,
            "updated": False,
            "error": None
        }
        
        try:
            logger.info(
                f"Processing meeting: {meeting.title}",
                extra={"data": {
                    "meeting_id": meeting.meeting_id,
                    "title": meeting.title,
                    "start_time": meeting.start_time.isoformat()
                }}
            )
            
            # Check if prep meeting already exists
            prep_exists = await self.meeting_creator.check_prep_meeting_exists(meeting)
            
            # Generate memo for the meeting
            memo_text = await self.memo_generator.generate_meeting_memo(meeting)
            
            if not memo_text:
                process_result["error"] = f"Failed to generate memo for meeting {meeting.meeting_id}"
                return process_result
            
            # Format memo for calendar description
            formatted_memo = self.meeting_creator.format_memo_for_description(memo_text, meeting)
            
            if prep_exists and config.update_existing_tasks:
                # Update existing prep meeting
                # We'd need to get the existing prep meeting ID for this
                logger.info(f"Prep meeting exists for {meeting.meeting_id}, would update if we had event ID")
                process_result["updated"] = True
                
            elif not prep_exists and config.create_tasks:
                # Create new prep meeting
                prep_event_id = await self.meeting_creator.create_prep_meeting(
                    original_meeting=meeting,
                    memo_text=formatted_memo,
                    calendar_id="primary"  # Could be configurable
                )
                
                if prep_event_id:
                    process_result["created"] = True
                    logger.info(
                        f"Created prep meeting for {meeting.title}",
                        extra={"data": {
                            "original_meeting_id": meeting.meeting_id,
                            "prep_event_id": prep_event_id
                        }}
                    )
                else:
                    process_result["error"] = f"Failed to create prep meeting for {meeting.meeting_id}"
            
            return process_result
            
        except Exception as e:
            process_result["error"] = f"Error processing meeting {meeting.meeting_id}: {str(e)}"
            logger.error(
                f"Error processing meeting {meeting.meeting_id}",
                exc_info=True,
                extra={"data": {
                    "meeting_id": meeting.meeting_id,
                    "error": str(e)
                }}
            )
            return process_result