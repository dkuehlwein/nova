"""
Email Input Hook implementation.

Wraps the existing email processing system (EmailProcessor, EmailFetcher, etc.)
to work with the new hook architecture while preserving all existing functionality.
"""

from typing import Dict, Any, List

from utils.logging import get_logger
from .base_hook import BaseInputHook
from .models import EmailHookConfig, NormalizedItem
from .datetime_utils import parse_datetime

logger = get_logger(__name__)


class EmailInputHook(BaseInputHook):
    """
    Email input hook that wraps existing EmailProcessor functionality.
    
    This hook reuses all existing email processing components:
    - EmailProcessor for orchestration
    - EmailFetcher for MCP integration  
    - EmailNormalizer for format standardization
    - EmailTaskCreator for task creation
    
    Zero code rewrite - just adapts the interfaces!
    """
    
    def __init__(self, hook_name: str, config: EmailHookConfig):
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
                
                self._email_processor = EmailProcessor()
                self._email_fetcher = EmailFetcher()
                self._email_normalizer = EmailNormalizer()
                self._email_task_creator = EmailTaskCreator()
                
                logger.debug(f"Initialized email components for hook {self.hook_name}")
                
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
        Create task from email using existing EmailTaskCreator.
        
        Overrides base class to use existing email task creation logic.
        """
        try:
            self._ensure_email_components()
            
            # Use existing EmailTaskCreator which handles:
            # - Task title formatting ("Read Email: {subject}")
            # - Task description with email metadata  
            # - Email-specific content parsing
            task_id = await self._email_task_creator.create_task_from_email(item.content)
            
            if task_id:
                logger.info(
                    f"Created email task via hook {self.hook_name}",
                    extra={"data": {
                        "hook_name": self.hook_name,
                        "email_id": item.source_id,
                        "task_id": task_id,
                        "subject": item.content.get("subject", "")[:100]
                    }}
                )
            
            return task_id
            
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
        Mark email as processed using existing EmailProcessor logic.
        
        This ensures compatibility with existing processed_emails table
        and any existing deduplication logic.
        """
        try:
            # Use existing EmailTaskCreator metadata creation
            self._ensure_email_components()
            
            metadata = await self._email_task_creator._create_metadata(item.content)
            
            # Use existing EmailProcessor method for marking as processed
            await self._email_processor._mark_email_processed(
                item.source_id, metadata, task_id
            )
            
            logger.debug(
                f"Marked email as processed via hook",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "email_id": item.source_id,
                    "task_id": task_id
                }}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to mark email as processed via hook",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "email_id": item.source_id,
                    "task_id": task_id,
                    "error": str(e)
                }}
            )
            # Fallback to parent class method
            await super()._mark_item_processed(item, task_id)
    
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
                "hook_type": "email"
            })
            
            return health
            
        except Exception as e:
            health = await super().health_check()
            health.update({
                "healthy": False,
                "error": str(e),
                "hook_type": "email"
            })
            return health