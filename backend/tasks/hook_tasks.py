"""
Generic Celery tasks for the input hooks system.

Provides centralized task processing for all hook types, replacing the
email-specific tasks with a generic, extensible approach.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from celery import current_task
from celery.exceptions import Retry

from celery_app import celery_app
from utils.logging import get_logger
from utils.redis_manager import publish_sync
from input_hooks.hook_registry import input_hook_registry
from models.events import NovaEvent
from input_hooks.models import ProcessingResult

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="tasks.hook_tasks.process_hook_items",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_backoff_max=300,  # Max 5 minutes between retries
    retry_jitter=True
)
def process_hook_items(self, hook_name: str) -> Dict[str, Any]:
    """
    Generic task to process items from any input hook.
    
    This replaces email-specific tasks with a unified approach that works
    for email, calendar, Slack, and any future input sources.
    
    Args:
        hook_name: Name of the hook to process (e.g., "email", "calendar")
        
    Returns:
        Dict with processing results and statistics
    """
    task_id = current_task.request.id if current_task else "unknown"
    
    logger.info(
        f"Starting hook processing task: {hook_name}",
        extra={"data": {
            "hook_name": hook_name,
            "task_id": task_id,
            "retry_count": self.request.retries
        }}
    )
    
    try:
        # Run async hook processing in sync context
        result = asyncio.run(_process_hook_items_async(hook_name, task_id))
        
        logger.info(
            f"Hook processing task completed: {hook_name}",
            extra={"data": {
                "hook_name": hook_name,
                "task_id": task_id,
                "items_processed": result.get("items_processed", 0),
                "tasks_created": result.get("tasks_created", 0),
                "tasks_updated": result.get("tasks_updated", 0),
                "errors": len(result.get("errors", [])),
                "processing_time": result.get("processing_time_seconds", 0),
                "retry_count": self.request.retries
            }}
        )
        
        return result
        
    except Exception as e:
        retry_count = self.request.retries
        max_retries = self.max_retries
        
        logger.error(
            f"Hook processing task failed: {hook_name}",
            exc_info=True,
            extra={"data": {
                "hook_name": hook_name,
                "task_id": task_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "retry_count": retry_count,
                "max_retries": max_retries
            }}
        )
        
        # Publish failure event for monitoring
        try:
            event = NovaEvent(
                type="hook_processing_failed",
                source="celery-worker",
                data={
                    "hook_name": hook_name,
                    "task_id": task_id,
                    "error": str(e),
                    "retry_count": retry_count,
                    "is_final_failure": retry_count >= max_retries,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            publish_sync(event)
        except Exception as publish_error:
            logger.error(
                f"Failed to publish hook processing failure event for {hook_name}",
                extra={"data": {"error": str(publish_error)}}
            )
        
        # Store failure information for dead letter queue handling
        if retry_count >= max_retries:
            logger.critical(
                f"Hook processing task exhausted all retries: {hook_name}",
                extra={"data": {
                    "hook_name": hook_name,
                    "task_id": task_id,
                    "final_error": str(e),
                    "total_retries": retry_count
                }}
            )
            
            try:
                asyncio.run(_store_failed_hook_task_info(hook_name, task_id, str(e), retry_count))
            except Exception as store_error:
                logger.error(
                    f"Failed to store dead letter queue information for {hook_name}",
                    extra={"data": {"error": str(store_error)}}
                )
        
        # Re-raise for Celery retry mechanism
        raise


async def _process_hook_items_async(hook_name: str, task_id: str) -> Dict[str, Any]:
    """
    Async implementation of hook processing.
    
    Args:
        hook_name: Name of the hook to process
        task_id: Celery task ID for tracking
        
    Returns:
        Dict with processing results
    """
    try:
        # Get the hook from registry
        hook = input_hook_registry.get_hook(hook_name)
        if not hook:
            available_hooks = input_hook_registry.list_hooks()
            raise ValueError(f"Hook '{hook_name}' not found. Available hooks: {available_hooks}")
        
        # Publish processing start event
        event = NovaEvent(
            type="hook_processing_started",
            source="celery-worker",
            data={
                "hook_name": hook_name,
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        publish_sync(event)
        
        # Process items using the hook's pipeline
        result = await hook.process_items()
        
        logger.info(
            f"Hook items processed successfully: {hook_name}",
            extra={"data": {
                "hook_name": hook_name,
                "task_id": task_id,
                "items_processed": result.items_processed,
                "tasks_created": result.tasks_created,
                "tasks_updated": result.tasks_updated,
                "errors": len(result.errors)
            }}
        )
        
        # Convert ProcessingResult to dict for Celery serialization
        result_dict = {
            "hook_name": result.hook_name,
            "items_processed": result.items_processed,
            "tasks_created": result.tasks_created,
            "tasks_updated": result.tasks_updated,
            "errors": result.errors,
            "processing_time_seconds": result.processing_time_seconds,
            "timestamp": result.timestamp.isoformat(),
            "task_id": task_id
        }
        
        # Publish completion event
        event = NovaEvent(
            type="hook_processing_completed",
            source="celery-worker",
            data=result_dict
        )
        publish_sync(event)
        
        return result_dict
        
    except Exception as e:
        # Publish failure event
        event = NovaEvent(
            type="hook_processing_failed",
            source="celery-worker",
            data={
                "hook_name": hook_name,
                "task_id": task_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        publish_sync(event)
        raise


@celery_app.task(
    bind=True,
    name="tasks.hook_tasks.process_single_item",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30}
)
def process_single_item(self, hook_name: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single item from any hook (for manual processing or retries).
    
    Args:
        hook_name: Name of the hook
        item_data: Raw item data to process
        
    Returns:
        Dict with processing result
    """
    task_id = current_task.request.id if current_task else "unknown"
    
    logger.info(
        f"Processing single item from hook: {hook_name}",
        extra={"data": {
            "hook_name": hook_name,
            "task_id": task_id,
            "item_keys": list(item_data.keys()) if isinstance(item_data, dict) else "unknown",
            "retry_count": self.request.retries
        }}
    )
    
    try:
        result = asyncio.run(_process_single_item_async(hook_name, task_id, item_data))
        
        logger.info(
            f"Single item processing completed: {hook_name}",
            extra={"data": {
                "hook_name": hook_name,
                "task_id": task_id,
                "success": result.get("success", False)
            }}
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Single item processing failed: {hook_name}",
            exc_info=True,
            extra={"data": {
                "hook_name": hook_name,
                "task_id": task_id,
                "error": str(e),
                "retry_count": self.request.retries
            }}
        )
        raise


async def _process_single_item_async(hook_name: str, task_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async implementation of single item processing.
    
    Args:
        hook_name: Name of the hook
        task_id: Celery task ID
        item_data: Raw item data to process
        
    Returns:
        Dict with processing result
    """
    try:
        # Get the hook from registry
        hook = input_hook_registry.get_hook(hook_name)
        if not hook:
            raise ValueError(f"Hook '{hook_name}' not found")
        
        # Create a minimal ProcessingResult for single item
        result = ProcessingResult(hook_name=hook_name)
        
        # Process the single item through the hook's pipeline
        await hook._process_single_item(item_data, result)
        
        return {
            "hook_name": hook_name,
            "task_id": task_id,
            "success": True,
            "tasks_created": result.tasks_created,
            "tasks_updated": result.tasks_updated,
            "errors": result.errors,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "hook_name": hook_name,
            "task_id": task_id,
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@celery_app.task(name="tasks.hook_tasks.replay_failed_hook_task")
def replay_failed_hook_task(hook_name: str, original_task_id: str) -> Dict[str, Any]:
    """
    Replay a failed hook processing task.
    
    This can be called manually or via monitoring dashboard to retry
    hook tasks that ended up in the dead letter queue.
    
    Args:
        hook_name: Name of the hook to replay
        original_task_id: The original failed task ID
        
    Returns:
        Dict with replay result
    """
    new_task_id = current_task.request.id if current_task else "unknown"
    
    logger.info(
        f"Replaying failed hook task: {hook_name}",
        extra={"data": {
            "hook_name": hook_name,
            "new_task_id": new_task_id,
            "original_task_id": original_task_id
        }}
    )
    
    try:
        # Trigger a fresh hook processing task
        result = process_hook_items.delay(hook_name)
        
        return {
            "hook_name": hook_name,
            "replay_task_id": result.id,
            "original_task_id": original_task_id,
            "status": "replay_initiated",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(
            f"Failed to replay hook task: {hook_name}",
            exc_info=True,
            extra={"data": {
                "hook_name": hook_name,
                "original_task_id": original_task_id,
                "error": str(e)
            }}
        )
        raise


@celery_app.task(name="tasks.hook_tasks.health_check_all_hooks")
def health_check_all_hooks() -> Dict[str, Any]:
    """
    Perform health check on all registered hooks.
    
    Returns:
        Dict with health status for all hooks
    """
    task_id = current_task.request.id if current_task else "unknown"
    
    logger.info(
        "Starting health check for all hooks",
        extra={"data": {"task_id": task_id}}
    )
    
    try:
        # Run async health check
        health_results = asyncio.run(input_hook_registry.health_check_all())
        
        # Add summary information
        total_hooks = len(health_results)
        healthy_hooks = sum(1 for result in health_results.values() if result.get("healthy", False))
        
        summary = {
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_hooks": total_hooks,
                "healthy_hooks": healthy_hooks,
                "unhealthy_hooks": total_hooks - healthy_hooks,
                "health_percentage": (healthy_hooks / total_hooks * 100) if total_hooks > 0 else 100
            },
            "hooks": health_results
        }
        
        logger.info(
            f"Hook health check completed: {healthy_hooks}/{total_hooks} healthy",
            extra={"data": {
                "task_id": task_id,
                "total_hooks": total_hooks,
                "healthy_hooks": healthy_hooks
            }}
        )
        
        return summary
        
    except Exception as e:
        logger.error(
            "Hook health check failed",
            exc_info=True,
            extra={"data": {"task_id": task_id, "error": str(e)}}
        )
        raise


async def _store_failed_hook_task_info(hook_name: str, task_id: str, error: str, retry_count: int) -> None:
    """
    Store information about failed hook tasks for dead letter queue handling.
    
    This allows for manual review and potential replay of failed tasks.
    """
    try:
        failed_task_data = {
            "hook_name": hook_name,
            "task_id": task_id,
            "error": error,
            "retry_count": retry_count,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "task_type": "hook_processing"
        }
        
        # Publish to dead letter queue monitoring
        event = NovaEvent(
            type="hook_task_dead_letter",
            source="celery-worker",
            data=failed_task_data
        )
        publish_sync(event)
        
        logger.info(
            f"Stored dead letter queue information for hook: {hook_name}",
            extra={"data": failed_task_data}
        )
        
    except Exception as e:
        logger.error(
            f"Failed to store dead letter queue information for hook: {hook_name}",
            extra={"data": {
                "hook_name": hook_name,
                "task_id": task_id,
                "error": str(e)
            }}
        )