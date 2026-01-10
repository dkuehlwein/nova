"""
Gmail Input Hook implementation.

Wraps the existing email processing system (EmailProcessor, EmailFetcher, etc.)
to work with the new hook architecture while preserving all existing functionality.
Uses Gmail API via MCP integration.
"""

from typing import Dict, Any, List

from utils.logging import get_logger
from .base_hook import BaseInputHook
from .models import GmailHookConfig, NormalizedItem
from .datetime_utils import parse_datetime

logger = get_logger(__name__)


class GmailInputHook(BaseInputHook):
    """
    Gmail input hook that wraps existing EmailProcessor functionality.

    This hook reuses all existing email processing components:
    - EmailProcessor for orchestration
    - EmailFetcher for MCP integration (Gmail API)
    - EmailNormalizer for format standardization
    - EmailTaskCreator for task creation

    Zero code rewrite - just adapts the interfaces!
    """

    def __init__(self, hook_name: str, config: GmailHookConfig):
        super().__init__(hook_name, config)
        
        # Import here to avoid circular dependencies
        self._email_processor = None
        self._email_fetcher = None
        self._email_normalizer = None
        self._email_task_creator = None
    
    def _ensure_email_components(self):
        """Lazy initialization of email processing components."""
        if self._email_processor is None:
            try:
                from input_hooks.email_processing.processor import EmailProcessor
                from input_hooks.email_processing.fetcher import EmailFetcher
                from input_hooks.email_processing.normalizer import EmailNormalizer
                from input_hooks.email_processing.task_creator import EmailTaskCreator

                # Extract thread consolidation settings from hook config (ADR-019)
                thread_enabled = getattr(self.config.hook_settings, 'thread_consolidation_enabled', False)
                stabilization_mins = getattr(self.config.hook_settings, 'thread_stabilization_minutes', 15)

                self._email_processor = EmailProcessor(
                    thread_consolidation_enabled=thread_enabled,
                    stabilization_minutes=stabilization_mins
                )
                self._email_fetcher = EmailFetcher()
                self._email_normalizer = EmailNormalizer()
                self._email_task_creator = EmailTaskCreator()

                logger.debug(
                    f"Initialized email components for hook {self.hook_name}",
                    extra={"data": {
                        "thread_consolidation_enabled": thread_enabled,
                        "stabilization_minutes": stabilization_mins
                    }}
                )

            except ImportError as e:
                logger.error(f"Failed to import email processing components: {e}")
                raise
    
    async def fetch_items(self) -> List[Dict[str, Any]]:
        """
        Fetch new emails using existing EmailProcessor.
        
        Delegates to the existing EmailProcessor.fetch_new_emails() method
        which handles MCP integration, user settings, and deduplication.
        """
        try:
            self._ensure_email_components()
            
            logger.info(
                f"Fetching emails via hook {self.hook_name}",
                extra={"data": {"hook_name": self.hook_name}}
            )
            
            # Use existing EmailProcessor with hook configuration
            # - Hook config-based settings
            # - MCP tool integration  
            # - Email fetching and normalization
            # - Deduplication against processed_emails table
            normalized_emails = await self._email_processor.fetch_new_emails(self.config)
            
            logger.info(
                f"Fetched {len(normalized_emails)} new emails via hook",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "email_count": len(normalized_emails)
                }}
            )
            
            return normalized_emails
            
        except Exception as e:
            logger.error(
                f"Failed to fetch emails in hook {self.hook_name}",
                exc_info=True,
                extra={"data": {"hook_name": self.hook_name, "error": str(e)}}
            )
            raise
    
    async def normalize_item(self, raw_item: Dict[str, Any]) -> NormalizedItem:
        """
        Convert email dict to NormalizedItem format.
        
        The raw_item here is already normalized by EmailProcessor.fetch_new_emails(),
        so we just need to wrap it in our NormalizedItem format.
        """
        try:
            # Extract key fields from the normalized email dict
            email_id = raw_item.get("id", "")
            subject = raw_item.get("subject", "No Subject")
            
            # Create standardized item
            normalized_item = NormalizedItem(
                source_type="email",
                source_id=email_id,
                title=f"Read Email: {subject}",
                content=raw_item,
                created_at=parse_datetime(raw_item.get("date"), source_type="email"),
                should_create_task=True,  # Emails always create tasks
                should_update_existing=False  # Emails don't update (for now)
            )
            
            return normalized_item
            
        except Exception as e:
            logger.error(
                f"Failed to normalize email item in hook {self.hook_name}",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "email_id": raw_item.get("id", "unknown"),
                    "error": str(e)
                }}
            )
            raise
    
    async def should_create_task(self, item: NormalizedItem) -> bool:
        """
        Check if should create task from email using hook configuration.
        """
        try:
            # Use hook configuration (new system)
            should_create = (
                self.config.enabled and  # Hook enabled
                self.config.create_tasks  # Hook config allows creation
            )
            
            logger.debug(
                f"Email task creation check via hook system: {should_create}",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "hook_enabled": self.config.enabled,
                    "hook_create_tasks": self.config.create_tasks,
                    "result": should_create
                }}
            )
            
            return should_create
            
        except Exception as e:
            logger.error(
                f"Error checking should_create_task for email hook",
                extra={"data": {"hook_name": self.hook_name, "error": str(e)}}
            )
            # Default to base class behavior
            return await super().should_create_task(item)
    
    async def should_update_task(self, item: NormalizedItem, existing_task_id: str) -> bool:
        """
        Check if should update existing task from email.
        
        For now, emails don't support updates (consistent with existing behavior).
        
        Args:
            item: The normalized email item
            existing_task_id: ID of existing task (unused for emails)
        """
        # Email hooks don't support task updates currently
        return False
    
    async def _create_task_from_item(self, item: NormalizedItem) -> str:
        """
        Create task from email using EmailProcessor.

        Uses EmailProcessor.process_email() to properly handle thread consolidation
        (ADR-019) when enabled. The processor handles:
        - Thread consolidation and stabilization windows
        - Task title formatting ("Read Email: {subject}" or "Email Thread: ...")
        - Task description with email metadata
        - Marking emails as processed
        """
        try:
            self._ensure_email_components()

            # Use EmailProcessor.process_email() which handles thread consolidation
            # This returns True if task was created/updated, False otherwise
            result = await self._email_processor.process_email(item.content, self.config)

            if result:
                # Task was created - we need to get the task_id from ProcessedItem
                # since process_email marks the email as processed with the task_id
                from database.database import db_manager
                from models.models import ProcessedItem
                from sqlalchemy import select

                async with db_manager.get_session() as session:
                    stmt = select(ProcessedItem.task_id).where(
                        ProcessedItem.source_type == "email",
                        ProcessedItem.source_id == item.source_id
                    )
                    result_row = await session.execute(stmt)
                    row = result_row.first()
                    task_id = str(row[0]) if row else None

                if task_id:
                    logger.info(
                        f"Created/updated email task via hook {self.hook_name}",
                        extra={"data": {
                            "hook_name": self.hook_name,
                            "email_id": item.source_id,
                            "task_id": task_id,
                            "subject": item.content.get("subject", "")[:100],
                            "thread_consolidation": self._email_processor.thread_consolidation_enabled
                        }}
                    )

                return task_id

            return None

        except Exception as e:
            logger.error(
                f"Failed to create task from email in hook {self.hook_name}",
                exc_info=True,
                extra={"data": {
                    "hook_name": self.hook_name,
                    "email_id": item.source_id,
                    "error": str(e)
                }}
            )
            raise
    
    async def _mark_item_processed(self, item: NormalizedItem, task_id: str) -> None:
        """
        Mark email as processed.

        NOTE: When using EmailProcessor.process_email() (with thread consolidation),
        the processor already handles marking as processed internally.
        This method is kept for compatibility with BaseInputHook but is now
        essentially a no-op since the processor handles it.
        """
        # EmailProcessor.process_email() already marks the email as processed
        # via _mark_email_processed() internally. We just log for visibility.
        logger.debug(
            f"Email already marked as processed by EmailProcessor",
            extra={"data": {
                "hook_name": self.hook_name,
                "email_id": item.source_id,
                "task_id": task_id
            }}
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for email hook."""
        try:
            self._ensure_email_components()
            
            # Perform basic health check via existing email fetcher
            await self._email_fetcher._health_check()
            
            # Get base health info
            health = await super().health_check()
            
            # Add email-specific health info
            health.update({
                "mcp_tools_available": True,  # If health_check passed
                "email_processor_ready": self._email_processor is not None,
                "hook_type": "gmail"
            })
            
            return health
            
        except Exception as e:
            health = await super().health_check()
            health.update({
                "healthy": False,
                "error": str(e),
                "hook_type": "gmail"
            })
            return health