"""
Base input hook abstract class.

Provides the foundation for all input source hooks, extending Nova's proven
BaseConfigManager pattern with hook-specific functionality.
"""

import time
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy import select, and_

from utils.base_config_manager import BaseConfigManager
from utils.logging import get_logger
from database.database import db_manager
from tools.task_tools import create_task_tool, update_task_tool
from .models import HookConfig, ProcessingResult, NormalizedItem, TaskTemplate

logger = get_logger(__name__)


class BaseInputHook(BaseConfigManager[HookConfig]):
    """
    Base class for all input source hooks.
    
    Extends BaseConfigManager to provide:
    - Configuration management with hot-reload
    - Common processing pipeline
    - Task creation/updating logic  
    - Error handling and logging
    - Database integration for deduplication
    """
    
    def __init__(self, hook_name: str, config: HookConfig):
        self.hook_name = hook_name
        
        # Store config before calling super() so _load_config_data can access it
        self._provided_config = config
        
        # Create a dummy path that exists - hooks get config from registry, not files
        # But BaseConfigManager needs a path for its internal mechanics
        dummy_path = Path("/dev/null")  # Always exists on Unix systems
        super().__init__(dummy_path, hook_name)
        
        # Hook-specific state
        self._stats = {"runs": 0, "successes": 0, "errors": 0}
    
    # Configuration management methods (BaseConfigManager integration)
    def _load_config_data(self) -> Dict[str, Any]:
        """Load config data - hooks get config from registry, not files."""
        return self._serialize_config(self._provided_config)
    
    def _save_config_data(self, data: Dict[str, Any]) -> None:
        """Save config data - managed by registry, not by individual hooks."""
        # Config saving is handled by the hook registry
        pass
    
    def _create_config_instance(self, data: Dict[str, Any]) -> HookConfig:
        """Create config instance from data."""
        return self._provided_config  # Use the config provided by registry
    
    def _serialize_config(self, config: HookConfig) -> Dict[str, Any]:
        """Serialize config to dict."""
        return config.model_dump() if hasattr(config, 'model_dump') else config.dict()
    
    def _validate_config_data(self, data: Dict[str, Any]) -> Any:
        """Validate config data."""
        from utils.base_config_manager import ValidationResult
        return ValidationResult(valid=True)  # Registry handles validation
    
    @property 
    def config(self) -> HookConfig:
        """Get current hook configuration."""
        return self.get_config()
    
    # Abstract methods that each hook must implement
    @abstractmethod
    async def fetch_items(self) -> List[Dict[str, Any]]:
        """
        Fetch new items from the input source.
        
        Returns:
            List of raw item dictionaries from the source system
        """
        pass
    
    @abstractmethod
    async def normalize_item(self, raw_item: Dict[str, Any]) -> NormalizedItem:
        """
        Convert a raw item to the standardized NormalizedItem format.
        
        Args:
            raw_item: Raw item dict from fetch_items()
            
        Returns:
            NormalizedItem with standardized fields
        """
        pass
    
    # Optional methods with default implementations
    async def should_create_task(self, item: NormalizedItem) -> bool:
        """
        Determine if an item should create a new task.
        
        Args:
            item: Normalized item
            
        Returns:
            True if should create task
        """
        return self.config.create_tasks and item.should_create_task
    
    async def should_update_task(self, item: NormalizedItem, existing_task_id: str) -> bool:
        """
        Determine if an item should update an existing task.
        
        Args:
            item: Normalized item
            existing_task_id: ID of existing task
            
        Returns:
            True if should update task
        """
        return self.config.update_existing_tasks and item.should_update_existing
    
    # Main processing pipeline
    async def process_items(self) -> ProcessingResult:
        """
        Main processing pipeline for the hook.
        
        This is the entry point called by Celery tasks. Follows the pattern:
        1. Fetch items from source
        2. Normalize each item
        3. Check for existing tasks (deduplication)
        4. Create or update tasks as needed
        5. Record processing results
        
        Returns:
            ProcessingResult with statistics
        """
        start_time = time.time()
        result = ProcessingResult(hook_name=self.hook_name)
        
        try:
            logger.info(
                "Starting hook processing",
                extra={"data": {"hook_name": self.hook_name}}
            )
            
            # Check if hook is enabled
            if not self.config.enabled:
                logger.info("Hook is disabled, skipping", extra={"data": {"hook_name": self.hook_name}})
                return result
            
            # Fetch raw items from source
            raw_items = await self.fetch_items()
            logger.info(
                "Fetched raw items from hook",
                extra={"data": {"hook_name": self.hook_name, "item_count": len(raw_items)}}
            )
            
            # Process each item
            for raw_item in raw_items:
                try:
                    await self._process_single_item(raw_item, result)
                except Exception as e:
                    error_msg = f"Failed to process item: {str(e)}"
                    result.errors.append(error_msg)
                    logger.error(
                        "Item processing error",
                        extra={"data": {
                            "hook_name": self.hook_name,
                            "error": error_msg,
                            "item_keys": list(raw_item.keys()) if isinstance(raw_item, dict) else "unknown"
                        }}
                    )
                    continue
            
            result.items_processed = len(raw_items)
            result.processing_time_seconds = time.time() - start_time
            
            # Update stats
            self._stats["runs"] += 1
            self._stats["successes"] += 1
            
            logger.info(
                "Hook processing completed",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "items_processed": result.items_processed,
                    "tasks_created": result.tasks_created,
                    "tasks_updated": result.tasks_updated,
                    "errors": len(result.errors),
                    "processing_time": result.processing_time_seconds
                }}
            )
            
            return result
            
        except Exception as e:
            result.processing_time_seconds = time.time() - start_time
            result.errors.append(f"Hook processing failed: {str(e)}")
            
            self._stats["runs"] += 1
            self._stats["errors"] += 1
            
            logger.error(
                "Hook processing failed",
                exc_info=True,
                extra={"data": {
                    "hook_name": self.hook_name,
                    "error": str(e),
                    "processing_time": result.processing_time_seconds
                }}
            )
            
            raise
    
    async def _process_single_item(self, raw_item: Dict[str, Any], result: ProcessingResult) -> None:
        """Process a single raw item through the pipeline."""
        
        # Normalize the item
        normalized_item = await self.normalize_item(raw_item)
        
        # Check if already processed (deduplication)
        existing_task_id = await self._find_existing_task(normalized_item)
        
        if existing_task_id:
            # Item already has a task - check if should update
            if await self.should_update_task(normalized_item, existing_task_id):
                success = await self._update_task_from_item(normalized_item, existing_task_id)
                if success:
                    result.tasks_updated += 1
                    await self._mark_item_updated(normalized_item, existing_task_id)
        else:
            # New item - check if should create task
            if await self.should_create_task(normalized_item):
                task_id = await self._create_task_from_item(normalized_item)
                if task_id:
                    result.tasks_created += 1
                    await self._mark_item_processed(normalized_item, task_id)
    
    async def _create_task_from_item(self, item: NormalizedItem) -> Optional[str]:
        """Create a Nova task from a normalized item."""
        try:
            # Use template or default formatting
            template = self.config.task_template or TaskTemplate()
            
            task_title = template.title_format.format(
                title=item.title,
                source_type=item.source_type,
                **item.content
            )
            
            task_description = template.description_format.format(
                title=item.title,
                content=self._format_content_for_description(item.content),
                source_type=item.source_type,
                source_id=item.source_id,
                **item.content
            )
            
            # Combine template tags with hook-specific tags
            tags = list(template.tags) + [item.source_type, self.hook_name]
            
            # Create the task using existing tool
            result_json = await create_task_tool(
                title=task_title,
                description=task_description,
                tags=tags,
                status=template.status,
                priority=template.priority
            )
            
            # Extract task ID from result
            task_id = self._extract_task_id_from_result(result_json)
            
            if task_id:
                logger.info(
                    "Created task from hook item",
                    extra={"data": {
                        "hook_name": self.hook_name,
                        "source_id": item.source_id,
                        "task_id": task_id,
                        "task_title": task_title
                    }}
                )
            
            return task_id
            
        except Exception as e:
            logger.error(
                "Failed to create task from hook item",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "source_id": item.source_id,
                    "error": str(e)
                }}
            )
            raise
    
    async def _update_task_from_item(self, item: NormalizedItem, task_id: str) -> bool:
        """Update an existing Nova task from a normalized item."""
        try:
            template = self.config.task_template or TaskTemplate()
            
            # Format updated content
            updated_description = template.description_format.format(
                title=item.title,
                content=self._format_content_for_description(item.content),
                source_type=item.source_type,
                source_id=item.source_id,
                **item.content
            )
            
            # Update the task
            result_json = await update_task_tool(
                task_id=task_id,
                description=updated_description,
                # Could add other updatable fields here
            )
            
            logger.info(
                "Updated task from hook item",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "source_id": item.source_id,
                    "task_id": task_id
                }}
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to update task from hook item",
                extra={"data": {
                    "hook_name": self.hook_name,
                    "source_id": item.source_id,
                    "task_id": task_id,
                    "error": str(e)
                }}
            )
            return False
    
    async def _find_existing_task(self, item: NormalizedItem) -> Optional[str]:
        """Find existing task for this item (deduplication)."""
        try:
            async with db_manager.get_session() as session:
                # First check the new processed_items table when it exists
                try:
                    from models.models import ProcessedItem
                    stmt = select(ProcessedItem.task_id).where(
                        and_(
                            ProcessedItem.source_type == item.source_type,
                            ProcessedItem.source_id == item.source_id
                        )
                    )
                    result = await session.execute(stmt)
                    row = result.first()
                    if row:
                        return row[0]
                except:
                    # ProcessedItem table doesn't exist yet, continue to fallback
                    pass
                
                # Fallback: check existing email table if this is an email
                if item.source_type == "email":
                    from models.models import ProcessedEmail
                    stmt = select(ProcessedEmail.task_id).where(
                        ProcessedEmail.email_id == item.source_id
                    )
                    result = await session.execute(stmt)
                    row = result.first()
                    if row:
                        return row[0]
                
                return None
                
        except Exception as e:
            logger.error(
                "Error checking for existing task",
                extra={"data": {"source_type": item.source_type, "source_id": item.source_id, "error": str(e)}}
            )
            return None
    
    async def _mark_item_processed(self, item: NormalizedItem, task_id: str) -> None:
        """Mark item as processed in database."""
        try:
            async with db_manager.get_session() as session:
                # Try to use new processed_items table
                try:
                    from models.models import ProcessedItem
                    processed_item = ProcessedItem(
                        source_type=item.source_type,
                        source_id=item.source_id,
                        source_metadata=item.content,
                        task_id=task_id,
                        processed_at=datetime.utcnow()
                    )
                    session.add(processed_item)
                    await session.commit()
                    return
                except:
                    # ProcessedItem table doesn't exist, fall back to email table if applicable
                    await session.rollback()
                
                # Fallback for email items
                if item.source_type == "email":
                    from models.models import ProcessedEmail
                    # Extract email metadata from content
                    processed_email = ProcessedEmail(
                        email_id=item.source_id,
                        thread_id=item.content.get("thread_id", ""),
                        subject=item.content.get("subject", ""),
                        sender=item.content.get("from", ""),
                        processed_at=datetime.utcnow(),
                        task_id=task_id
                    )
                    session.add(processed_email)
                    await session.commit()
                
        except Exception as e:
            logger.error(
                "Failed to mark item as processed",
                extra={"data": {
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "task_id": task_id,
                    "error": str(e)
                }}
            )
    
    async def _mark_item_updated(self, item: NormalizedItem, task_id: str) -> None:
        """Mark item as updated in database."""
        try:
            async with db_manager.get_session() as session:
                # Update timestamp in processed_items if it exists
                try:
                    from models.models import ProcessedItem
                    from sqlalchemy import update
                    
                    stmt = update(ProcessedItem).where(
                        and_(
                            ProcessedItem.source_type == item.source_type,
                            ProcessedItem.source_id == item.source_id
                        )
                    ).values(
                        last_updated_at=datetime.utcnow(),
                        source_metadata=item.content
                    )
                    await session.execute(stmt)
                    await session.commit()
                    return
                except:
                    # ProcessedItem table doesn't exist yet
                    await session.rollback()
                    pass
                
                # For emails, we don't update the processed_emails table
                # as it's primarily for deduplication
                
        except Exception as e:
            logger.error(
                "Failed to mark item as updated",
                extra={"data": {
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "task_id": task_id,
                    "error": str(e)
                }}
            )
    
    def _format_content_for_description(self, content: Dict[str, Any]) -> str:
        """Format content dict for task description."""
        # Simple formatting - can be overridden by subclasses
        if isinstance(content, dict):
            if "content" in content:
                return str(content["content"])
            elif "body" in content:
                return str(content["body"])
            elif "description" in content:
                return str(content["description"])
            else:
                # Format key-value pairs nicely
                lines = []
                for key, value in content.items():
                    if key not in ["id", "source_type", "metadata"] and value:
                        lines.append(f"**{key.title()}:** {value}")
                return "\n".join(lines)
        return str(content)
    
    def _extract_task_id_from_result(self, result_json: str) -> Optional[str]:
        """Extract task ID from task creation result."""
        try:
            import json
            if "Task created successfully:" in result_json:
                # Extract the JSON part after the prefix
                json_part = result_json.split("Task created successfully:", 1)[1].strip()
                task_data = json.loads(json_part)
                return task_data.get("id")
            return None
        except Exception as e:
            logger.error("Failed to extract task ID from result", extra={"data": {"error": str(e)}})
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get hook statistics."""
        return self._stats.copy()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for this hook."""
        try:
            # Basic health check - can be overridden by subclasses
            return {
                "hook_name": self.hook_name,
                "enabled": self.config.enabled,
                "healthy": True,
                "last_run": self._stats.get("last_run"),
                "error_count": self._stats["errors"]
            }
        except Exception as e:
            return {
                "hook_name": self.hook_name,
                "healthy": False,
                "error": str(e)
            }