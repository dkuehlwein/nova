"""
Outlook Email Input Hook implementation.

Processes emails from Outlook (via MCP) and creates Nova tasks.
Uses the "Nova Processed" category in Outlook to track which emails
have been processed, preventing duplicates.
"""
import time
from typing import Dict, Any, List

from utils.logging import get_logger
from .base_hook import BaseInputHook
from .models import OutlookEmailHookConfig, NormalizedItem, ProcessingResult
from .outlook_processing.processor import OutlookProcessor

logger = get_logger(__name__)


class OutlookEmailHook(BaseInputHook):
    """
    Outlook email input hook that creates Nova tasks from emails.

    Unlike the Gmail hook which uses database tracking, this hook uses
    Outlook categories to track processed emails. This is more robust
    as the state persists in Outlook itself.

    Flow:
    1. Fetch unprocessed emails (exclude those with "Nova Processed" category)
    2. Create Nova tasks from each email
    3. Mark emails with "Nova Processed" category
    """

    def __init__(self, hook_name: str, config: OutlookEmailHookConfig):
        super().__init__(hook_name, config)
        self._processor: OutlookProcessor = None

    def _ensure_processor(self) -> OutlookProcessor:
        """Lazy initialization of Outlook processor."""
        if self._processor is None:
            self._processor = OutlookProcessor()
            logger.debug(f"Initialized Outlook processor for hook {self.hook_name}")
        return self._processor

    async def fetch_items(self) -> List[Dict[str, Any]]:
        """
        Fetch unprocessed emails from Outlook.

        The Outlook MCP handles filtering out already-processed emails
        (those with the "Nova Processed" category).

        Returns:
            List of email dictionaries
        """
        try:
            processor = self._ensure_processor()

            max_emails = self.config.hook_settings.max_per_fetch
            folder = self.config.hook_settings.folder

            logger.info(
                f"Fetching Outlook emails via hook {self.hook_name}",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "max_emails": max_emails,
                    "folder": folder
                }}
            )

            since_date = getattr(self.config.hook_settings, 'since_date', None)

            emails = await processor.fetcher.fetch_unprocessed_emails(
                max_emails=max_emails,
                folder=folder,
                since_date=since_date
            )

            logger.info(
                f"Fetched {len(emails)} unprocessed Outlook emails",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "count": len(emails)
                }}
            )

            return emails

        except Exception as e:
            logger.error(
                f"Failed to fetch Outlook emails in hook {self.hook_name}",
                exc_info=True,
                extra={"data": {"hook_name": self.hook_name, "error": str(e)}}
            )
            raise

    async def normalize_item(self, raw_item: Dict[str, Any]) -> NormalizedItem:
        """
        Convert Outlook email to NormalizedItem format.

        Outlook's response format is already clean, so minimal transformation needed.
        """
        try:
            email_id = raw_item.get("id", "")
            subject = raw_item.get("subject", "(No Subject)")

            return NormalizedItem(
                source_type="outlook_email",
                source_id=email_id,
                title=f"Process Outlook Email: {subject}",
                content=raw_item,
                created_at=None,  # Outlook dates are strings, handled in processor
                should_create_task=True,
                should_update_existing=False
            )

        except Exception as e:
            logger.error(
                f"Failed to normalize Outlook email in hook {self.hook_name}",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "email_id": raw_item.get("id", "unknown"),
                    "error": str(e)
                }}
            )
            raise

    async def should_create_task(self, item: NormalizedItem) -> bool:
        """Check if should create task from email."""
        return (
            self.config.enabled and
            self.config.create_tasks and
            item.should_create_task
        )

    async def should_update_task(self, item: NormalizedItem, existing_task_id: str) -> bool:
        """Outlook emails don't support task updates."""
        return False

    async def process_items(self) -> ProcessingResult:
        """
        Process Outlook emails and create Nova tasks.

        Overrides base class to use OutlookProcessor directly,
        which handles the full pipeline including marking emails.
        """
        start_time = time.time()
        result = ProcessingResult(hook_name=self.hook_name)

        try:
            logger.info(
                f"Starting Outlook email hook processing: {self.hook_name}",
                extra={"data": {"hook_name": self.hook_name}}
            )

            # Check if hook is enabled
            if not self.config.enabled:
                logger.info(f"Outlook email hook {self.hook_name} is disabled, skipping")
                return result

            # Use OutlookProcessor for the full pipeline
            processor = self._ensure_processor()
            since_date = getattr(self.config.hook_settings, 'since_date', None)
            processing_result = await processor.process_emails(
                max_emails=self.config.hook_settings.max_per_fetch,
                folder=self.config.hook_settings.folder,
                since_date=since_date
            )

            # Map OutlookProcessingResult to ProcessingResult
            result.items_processed = processing_result.emails_fetched
            result.tasks_created = processing_result.tasks_created
            result.tasks_updated = 0  # Outlook doesn't support updates
            result.errors = processing_result.errors
            result.processing_time_seconds = time.time() - start_time

            # Update internal stats
            self._stats["runs"] += 1
            if not processing_result.errors:
                self._stats["successes"] += 1
            else:
                self._stats["errors"] += 1

            logger.info(
                f"Outlook email hook processing completed: {self.hook_name}",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "emails_processed": result.items_processed,
                    "tasks_created": result.tasks_created,
                    "errors": len(result.errors),
                    "processing_time": result.processing_time_seconds
                }}
            )

            return result

        except Exception as e:
            result.processing_time_seconds = time.time() - start_time
            result.errors.append(f"Outlook hook processing failed: {str(e)}")

            self._stats["runs"] += 1
            self._stats["errors"] += 1

            logger.error(
                f"Outlook email hook processing failed: {self.hook_name}",
                exc_info=True,
                extra={"data": {
                    "hook_name": self.hook_name,
                    "error": str(e),
                    "processing_time": result.processing_time_seconds
                }}
            )

            raise

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for Outlook email hook."""
        try:
            processor = self._ensure_processor()
            outlook_health = await processor.health_check()

            # Get base health info
            health = await super().health_check()

            # Add Outlook-specific health info
            health.update({
                "hook_type": "outlook_email",
                "outlook_connected": outlook_health.get("healthy", False),
                "outlook_tools": outlook_health.get("tools_available", []),
                "uses_category_tracking": True,
                "category_name": "Nova Processed"
            })

            if not outlook_health.get("healthy"):
                health["healthy"] = False
                health["error"] = outlook_health.get("error", "Outlook MCP not healthy")

            return health

        except Exception as e:
            health = await super().health_check()
            health.update({
                "healthy": False,
                "error": str(e),
                "hook_type": "outlook_email"
            })
            return health
