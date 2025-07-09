"""
Celery tasks for email processing with robust error handling.
"""
import asyncio
from typing import List, Dict, Any
from celery import current_task
from celery.exceptions import Retry
from celery_app import celery_app
from utils.logging import get_logger
from email_processing import EmailProcessor
from utils.redis_manager import publish_sync
from models.email import EmailProcessingEvent

logger = get_logger(__name__)

@celery_app.task(
    bind=True, 
    name="tasks.email_tasks.fetch_emails",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_backoff_max=300,  # Max 5 minutes between retries
    retry_jitter=True
)
def fetch_emails(self) -> Dict[str, Any]:
    """
    Fetch new emails and create tasks for them.
    
    Includes robust retry logic and dead letter queue handling.
    
    Returns:
        Dict with processing results and statistics
    """
    task_id = current_task.request.id if current_task else "unknown"
    
    logger.info(
        "Starting email fetch task",
        extra={"data": {
            "task_id": task_id,
            "retry_count": self.request.retries
        }}
    )
    
    try:
        # Run async email processing in sync context
        result = asyncio.run(_fetch_emails_async(task_id))
        
        logger.info(
            "Email fetch task completed successfully",
            extra={"data": {
                "task_id": task_id,
                "emails_processed": result.get("emails_processed", 0),
                "tasks_created": result.get("tasks_created", 0),
                "retry_count": self.request.retries
            }}
        )
        
        return result
        
    except Exception as e:
        retry_count = self.request.retries
        max_retries = self.max_retries
        
        logger.error(
            "Email fetch task failed",
            extra={"data": {
                "task_id": task_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "retry_count": retry_count,
                "max_retries": max_retries
            }}
        )
        
        # Publish failure event
        try:
            publish_sync(EmailProcessingEvent(
                event_type="email_processing_failed",
                data={
                    "task_id": task_id,
                    "error": str(e),
                    "retry_count": retry_count,
                    "is_final_failure": retry_count >= max_retries
                }
            ))
        except Exception as publish_error:
            logger.error(
                "Failed to publish email processing failure event",
                extra={"data": {"error": str(publish_error)}}
            )
        
        # If we've exhausted retries, handle dead letter queue scenario
        if retry_count >= max_retries:
            logger.critical(
                "Email fetch task exhausted all retries - entering dead letter queue",
                extra={"data": {
                    "task_id": task_id,
                    "final_error": str(e),
                    "total_retries": retry_count
                }}
            )
            
            # Store failure information for manual review/replay
            try:
                asyncio.run(_store_failed_task_info(task_id, str(e), retry_count))
            except Exception as store_error:
                logger.error(
                    "Failed to store dead letter queue information",
                    extra={"data": {"error": str(store_error)}}
                )
        
        # Re-raise for Celery retry mechanism
        raise

async def _fetch_emails_async(task_id: str) -> Dict[str, Any]:
    """
    Async implementation of email fetching with dynamic configuration checking.
    
    Args:
        task_id: Celery task ID for tracking
        
    Returns:
        Dict with processing results
    """
    processor = EmailProcessor()
    
    try:
        # Publish start event
        publish_sync(EmailProcessingEvent(
            event_type="email_processing_started",
            data={"task_id": task_id}
        ))
        
        # Fetch new emails (processor checks config dynamically)
        emails = await processor.fetch_new_emails()
        
        logger.info(
            "Fetched emails from provider",
            extra={"data": {
                "task_id": task_id,
                "email_count": len(emails)
            }}
        )
        
        # Process each email
        tasks_created = 0
        for email in emails:
            try:
                task_created = await processor.process_email(email)
                if task_created:
                    tasks_created += 1
                    
            except Exception as e:
                logger.error(
                    "Failed to process individual email",
                    extra={"data": {
                        "task_id": task_id,
                        "email_id": email.get("id"),
                        "email_subject": email.get("subject", "")[:100],
                        "error": str(e)
                    }}
                )
                # Continue processing other emails
                continue
        
        result = {
            "emails_processed": len(emails),
            "tasks_created": tasks_created,
            "task_id": task_id
        }
        
        # Publish completion event
        publish_sync(EmailProcessingEvent(
            event_type="email_processing_completed",
            data=result
        ))
        
        return result
        
    except Exception as e:
        # Publish failure event
        publish_sync(EmailProcessingEvent(
            event_type="email_processing_failed",
            data={
                "task_id": task_id,
                "error": str(e)
            }
        ))
        raise
    
    finally:
        # Always clean up processor resources
        try:
            await processor.close()
        except Exception as e:
            logger.error(
                "Error closing email processor",
                extra={"data": {"error": str(e)}}
            )

@celery_app.task(
    bind=True, 
    name="tasks.email_tasks.process_single_email",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30}
)
def process_single_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single email (for manual processing or retries).
    
    Args:
        email_data: Email data dictionary
        
    Returns:
        Dict with processing result
    """
    task_id = current_task.request.id if current_task else "unknown"
    
    logger.info(
        "Processing single email",
        extra={"data": {
            "task_id": task_id,
            "email_id": email_data.get("id"),
            "email_subject": email_data.get("subject", "")[:100],
            "retry_count": self.request.retries
        }}
    )
    
    try:
        result = asyncio.run(_process_single_email_async(task_id, email_data))
        
        logger.info(
            "Single email processing completed",
            extra={"data": {
                "task_id": task_id,
                "email_id": email_data.get("id"),
                "task_created": result.get("task_created", False)
            }}
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Single email processing failed",
            extra={"data": {
                "task_id": task_id,
                "email_id": email_data.get("id"),
                "error": str(e),
                "retry_count": self.request.retries
            }}
        )
        raise

async def _process_single_email_async(task_id: str, email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async implementation of single email processing.
    
    Args:
        task_id: Celery task ID
        email_data: Email data dictionary
        
    Returns:
        Dict with processing result
    """
    processor = EmailProcessor()
    
    try:
        task_created = await processor.process_email(email_data)
        
        return {
            "task_created": task_created,
            "email_id": email_data.get("id"),
            "task_id": task_id
        }
        
    except Exception as e:
        logger.error(
            "Failed to process email",
            extra={"data": {
                "task_id": task_id,
                "email_id": email_data.get("id"),
                "error": str(e)
            }}
        )
        raise
    
    finally:
        try:
            await processor.close()
        except Exception as e:
            logger.error(
                "Error closing email processor",
                extra={"data": {"error": str(e)}}
            )

async def _store_failed_task_info(task_id: str, error: str, retry_count: int) -> None:
    """
    Store information about failed tasks for dead letter queue handling.
    
    This allows for manual review and potential replay of failed tasks.
    """
    from database.database import db_manager
    from datetime import datetime
    
    try:
        # Store in Redis for monitoring dashboard
        failed_task_data = {
            "task_id": task_id,
            "error": error,
            "retry_count": retry_count,
            "failed_at": datetime.utcnow().isoformat(),
            "task_type": "email_fetch"
        }
        
        # Publish to dead letter queue monitoring
        publish_sync(EmailProcessingEvent(
            event_type="email_task_dead_letter",
            data=failed_task_data
        ))
        
        logger.info(
            "Stored dead letter queue information",
            extra={"data": failed_task_data}
        )
        
    except Exception as e:
        logger.error(
            "Failed to store dead letter queue information",
            extra={"data": {
                "task_id": task_id,
                "error": str(e)
            }}
        )

@celery_app.task(name="tasks.email_tasks.replay_failed_email_task")
def replay_failed_email_task(original_task_id: str) -> Dict[str, Any]:
    """
    Replay a failed email processing task.
    
    This can be called manually or via monitoring dashboard to retry
    tasks that ended up in the dead letter queue.
    
    Args:
        original_task_id: The original failed task ID
        
    Returns:
        Dict with replay result
    """
    new_task_id = current_task.request.id if current_task else "unknown"
    
    logger.info(
        "Replaying failed email task",
        extra={"data": {
            "new_task_id": new_task_id,
            "original_task_id": original_task_id
        }}
    )
    
    try:
        # Trigger a fresh email fetch
        result = fetch_emails.delay()
        
        return {
            "replay_task_id": result.id,
            "original_task_id": original_task_id,
            "status": "replay_initiated"
        }
        
    except Exception as e:
        logger.error(
            "Failed to replay email task",
            extra={"data": {
                "original_task_id": original_task_id,
                "error": str(e)
            }}
        )
        raise 