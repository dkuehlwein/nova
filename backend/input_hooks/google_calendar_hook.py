"""
Google Calendar Input Hook implementation.

Wraps the calendar processing system to work with Nova's hook architecture.
Creates private preparation meetings instead of Nova tasks to keep the task list clean.
Uses Google Calendar API via MCP integration.
"""

from typing import Dict, Any, List
from datetime import datetime

from utils.logging import get_logger
from .base_hook import BaseInputHook
from .models import GoogleCalendarHookConfig, NormalizedItem, CalendarMeetingInfo
from .calendar_processing.processor import CalendarProcessor

logger = get_logger(__name__)


class GoogleCalendarInputHook(BaseInputHook):
    """
    Google Calendar input hook that creates preparation meetings.

    Unlike other hooks that create Nova tasks, this hook creates private
    preparation meetings in your calendar with AI-generated memos as content.
    This keeps Nova's task system clean while providing meeting preparation.
    """

    def __init__(self, hook_name: str, config: GoogleCalendarHookConfig):
        super().__init__(hook_name, config)
        
        # Calendar processing components
        self._calendar_processor = None
        
        # Track prep meetings we've created (for deduplication)
        self._processed_meetings = set()
    
    def _ensure_calendar_components(self):
        """Lazy initialization of calendar processing components."""
        if self._calendar_processor is None:
            try:
                self._calendar_processor = CalendarProcessor()
                logger.debug(f"Initialized calendar processor for hook {self.hook_name}")
                
            except Exception as e:
                logger.error(f"Failed to initialize calendar components: {e}")
                raise
    
    async def fetch_items(self) -> List[Dict[str, Any]]:
        """
        Fetch today's meetings and process them for preparation.
        
        Unlike other hooks that return raw items for processing,
        calendar hook processes meetings directly and returns
        a summary of what was done.
        
        Returns:
            List containing processing summary (for compatibility)
        """
        try:
            self._ensure_calendar_components()
            
            logger.info(
                f"Processing daily meetings via calendar hook {self.hook_name}",
                extra={"data": {"hook_name": self.hook_name}}
            )
            
            # Process today's meetings directly (different from other hooks)
            processing_result = await self._calendar_processor.process_daily_meetings(self.config)
            
            logger.info(
                f"Calendar hook processing completed",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "events_fetched": processing_result["events_fetched"],
                    "prep_meetings_created": processing_result["prep_meetings_created"],
                    "errors": len(processing_result["errors"])
                }}
            )
            
            # Return processing summary wrapped as items (for hook compatibility)
            # This prevents the base hook from trying to create tasks
            return [{"processing_summary": processing_result}]
            
        except Exception as e:
            logger.error(
                f"Failed to process calendar meetings in hook {self.hook_name}",
                exc_info=True,
                extra={"data": {"hook_name": self.hook_name, "error": str(e)}}
            )
            raise
    
    async def normalize_item(self, raw_item: Dict[str, Any]) -> NormalizedItem:
        """
        Convert processing summary to NormalizedItem format.
        
        Since calendar hook processes meetings directly in fetch_items(),
        this method just wraps the processing summary.
        
        Args:
            raw_item: Processing summary from fetch_items()
            
        Returns:
            NormalizedItem representing the processing summary
        """
        try:
            processing_summary = raw_item.get("processing_summary", {})
            
            # Create a summary of what was processed
            events_count = processing_summary.get("events_fetched", 0)
            prep_meetings_created = processing_summary.get("prep_meetings_created", 0)
            prep_meetings_updated = processing_summary.get("prep_meetings_updated", 0)
            errors_count = len(processing_summary.get("errors", []))
            
            title = f"Calendar Processing: {events_count} events, {prep_meetings_created} prep meetings created"
            
            # Create normalized item that won't create tasks
            normalized_item = NormalizedItem(
                source_type="calendar",
                source_id=f"daily_processing_{datetime.now().strftime('%Y%m%d')}",
                title=title,
                content=processing_summary,
                created_at=datetime.utcnow(),
                should_create_task=False,  # Don't create Nova tasks
                should_update_existing=False
            )
            
            return normalized_item
            
        except Exception as e:
            logger.error(
                f"Failed to normalize calendar processing summary",
                extra={"data": {"hook_name": self.hook_name, "error": str(e)}}
            )
            raise
    
    async def should_create_task(self, item: NormalizedItem) -> bool:
        """
        Calendar hook doesn't create Nova tasks.
        
        It creates preparation meetings instead, which is handled
        in the calendar processing pipeline.
        
        Args:
            item: Normalized item (processing summary)
            
        Returns:
            Always False - no Nova tasks created by calendar hook
        """
        return False
    
    async def should_update_task(self, item: NormalizedItem, existing_task_id: str) -> bool:
        """
        Calendar hook doesn't update Nova tasks.
        
        Updates are handled by updating preparation meetings directly.
        
        Args:
            item: Normalized item
            existing_task_id: ID of existing task (unused)
            
        Returns:
            Always False - no Nova task updates
        """
        return False
    
    async def process_items(self) -> "ProcessingResult":
        """
        Override the base processing to handle calendar-specific flow.
        
        Calendar hook processes meetings directly rather than following
        the standard fetch -> normalize -> create tasks flow.
        
        Returns:
            ProcessingResult with calendar-specific statistics
        """
        from .models import ProcessingResult
        import time
        
        start_time = time.time()
        result = ProcessingResult(hook_name=self.hook_name)
        
        try:
            logger.info(
                f"Starting calendar hook processing: {self.hook_name}",
                extra={"data": {"hook_name": self.hook_name}}
            )
            
            # Check if hook is enabled
            if not self.config.enabled:
                logger.info(f"Calendar hook {self.hook_name} is disabled, skipping")
                return result
            
            # Process calendar meetings directly
            self._ensure_calendar_components()
            processing_summary = await self._calendar_processor.process_daily_meetings(self.config)
            
            # Update result with calendar-specific stats
            result.items_processed = processing_summary.get("events_fetched", 0)
            
            # Calendar hook creates prep meetings, not Nova tasks
            # But we track them in a custom way
            prep_meetings_created = processing_summary.get("prep_meetings_created", 0)
            prep_meetings_updated = processing_summary.get("prep_meetings_updated", 0)
            
            # For reporting purposes, treat prep meetings as "tasks"
            result.tasks_created = prep_meetings_created
            result.tasks_updated = prep_meetings_updated
            
            # Add any errors from processing
            processing_errors = processing_summary.get("errors", [])
            result.errors.extend(processing_errors)
            
            result.processing_time_seconds = time.time() - start_time
            
            # Update stats
            self._stats["runs"] += 1
            if processing_summary.get("success", True):
                self._stats["successes"] += 1
            else:
                self._stats["errors"] += 1
            
            logger.info(
                f"Calendar hook processing completed: {self.hook_name}",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "events_processed": result.items_processed,
                    "prep_meetings_created": result.tasks_created,
                    "prep_meetings_updated": result.tasks_updated,
                    "errors": len(result.errors),
                    "processing_time": result.processing_time_seconds
                }}
            )
            
            return result
            
        except Exception as e:
            result.processing_time_seconds = time.time() - start_time
            result.errors.append(f"Calendar hook processing failed: {str(e)}")
            
            self._stats["runs"] += 1
            self._stats["errors"] += 1
            
            logger.error(
                f"Calendar hook processing failed: {self.hook_name}",
                exc_info=True,
                extra={"data": {
                    "hook_name": self.hook_name,
                    "error": str(e),
                    "processing_time": result.processing_time_seconds
                }}
            )
            
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for calendar hook."""
        try:
            self._ensure_calendar_components()
            
            # Get base health info from BaseInputHook
            health = await super().health_check()
            
            # Add calendar-specific health info
            health.update({
                "hook_type": "google_calendar",
                "creates_prep_meetings": True,
                "creates_nova_tasks": False,
                "status": "Google Calendar MCP tools accessible"
            })
            
            return health
            
        except Exception as e:
            health = await super().health_check()
            health.update({
                "healthy": False,
                "error": str(e),
                "hook_type": "google_calendar"
            })
            return health