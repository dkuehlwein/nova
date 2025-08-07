"""
Celery application configuration for Nova email processing with dynamic scheduling.
"""
import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from config import settings

# Create Celery instance
celery_app = Celery(
    "nova",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.email_tasks"]
)


# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        "tasks.email_tasks.fetch_emails": {"queue": "email"},
        "tasks.email_tasks.process_single_email": {"queue": "email"},
        "tasks.email_tasks.replay_failed_email_task": {"queue": "email"},
    },
    
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_always_eager=False,
    task_eager_propagates=True,
    task_store_eager_result=True,
    
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Result backend
    result_expires=3600,  # 1 hour
    
    # Beat schedule (will be configured dynamically)
    beat_schedule={},
    beat_schedule_filename="celerybeat-schedule",
    
    # Enhanced retry configuration
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    task_retry_backoff=True,
    task_retry_backoff_max=300,  # 5 minutes
    task_retry_jitter=True,
    
    # Dead letter queue configuration
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,
    
    # Logging
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

def update_beat_schedule():
    """
    Update Celery Beat schedule based on current configuration.
    
    This function can be called to dynamically update the email polling schedule
    without restarting Celery Beat.
    """
    try:
        # Import here to avoid circular import
        import asyncio
        from database.database import db_manager
        from database.database import UserSettingsService
        
        # Get user settings synchronously - email processing controlled by Tier 3 user settings
        try:
            user_settings = UserSettingsService.get_user_settings_sync()
            
            if user_settings and user_settings.email_polling_enabled:
                schedule_interval = user_settings.email_polling_interval
                
                celery_app.conf.beat_schedule = {
                    "fetch-emails": {
                        "task": "tasks.email_tasks.fetch_emails",
                        "schedule": schedule_interval,
                        "options": {"queue": "email"},
                    },
                }
                
                print(f"Updated email fetch schedule: every {schedule_interval} seconds (from user settings)")
            else:
                # User has disabled email polling or no settings exist
                celery_app.conf.beat_schedule = {}
                print("Email polling disabled in user settings - cleared beat schedule")
                
        except Exception as db_error:
            # Database not available or settings not created yet - disable email processing
            print(f"Could not load user settings, email processing disabled: {db_error}")
            celery_app.conf.beat_schedule = {}
            
    except Exception as e:
        # Fallback to default schedule if config loading fails
        print(f"Config loading failed, using default schedule: {e}")
        celery_app.conf.beat_schedule = {
            "fetch-emails": {
                "task": "tasks.email_tasks.fetch_emails",
                "schedule": 300.0,  # 5 minutes default
                "options": {"queue": "email"},
            },
        }

# Signal handlers for worker lifecycle
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handle worker ready signal."""
    print("Celery worker ready - initializing configs and updating beat schedule")
    
    # Initialize unified configuration system (following start_website.py pattern)
    try:
        from utils.config_registry import initialize_configs
        print("Initializing unified configuration system...")
        initialize_configs()
        print("Configuration managers initialized successfully")
    except Exception as e:
        print(f"Failed to initialize configurations: {e}")
        # Don't raise - let worker continue with default settings
    
    # Start Redis event listener for email settings changes
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_in_executor(None, start_email_settings_listener)
        print("Started Redis email settings listener")
    except Exception as e:
        print(f"Failed to start Redis email settings listener: {e}")
    
    update_beat_schedule()

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Handle worker shutdown signal."""
    print("Celery worker shutting down")

# Custom task for dynamic schedule updates
@celery_app.task(name="celery.update_beat_schedule")
def update_beat_schedule_task():
    """
    Task to update beat schedule dynamically.
    
    This can be called from the API to update email polling settings
    without restarting Celery Beat.
    """
    try:
        update_beat_schedule()
        
        # Send signal to beat scheduler to reload
        from celery import current_app
        current_app.control.broadcast('pool_restart', arguments={'reload': True})
        
        return {"status": "success", "message": "Beat schedule updated"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Task for dead letter queue monitoring
@celery_app.task(name="celery.monitor_dead_letter_queue")
def monitor_dead_letter_queue():
    """
    Monitor and report on dead letter queue status.
    
    This task can be scheduled to run periodically to check for
    failed tasks that need attention.
    """
    try:
        from utils.redis_manager import get_redis_client
        import asyncio
        
        async def _check_failed_tasks():
            # Get failed task count from Redis
            redis_client = get_redis_client()
            
            # Check for failed tasks in the last 24 hours
            failed_tasks_key = "nova:email:failed_tasks:24h"
            failed_count = await redis_client.scard(failed_tasks_key)
            
            # Check pending tasks in email queue
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            scheduled_tasks = inspect.scheduled()
            
            email_queue_count = 0
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    email_queue_count += len([t for t in tasks if 'email' in t.get('delivery_info', {}).get('routing_key', '')])
            
            return {
                "failed_tasks_24h": failed_count,
                "email_queue_pending": email_queue_count,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        from datetime import datetime
        result = asyncio.run(_check_failed_tasks())
        
        # Log monitoring results
        from utils.logging import get_logger
        logger = get_logger(__name__)
        
        logger.info(
            "Dead letter queue monitoring check",
            extra={"data": result}
        )
        
        return result
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

def start_email_settings_listener():
    """
    Start a Redis listener for email settings changes.
    Runs in a separate thread to listen for configuration updates.
    """
    import asyncio
    
    async def listen_for_email_settings():
        try:
            from utils.redis_manager import get_redis
            from models.events import NovaEvent
            import json
            
            redis_client = get_redis()
            print("Starting Redis email settings listener...")
            
            async for message in redis_client.subscribe(channel="nova_events"):
                try:
                    # Parse the event
                    event_data = json.loads(message)
                    event = NovaEvent.model_validate(event_data)
                    
                    if event.type == "email_settings_updated":
                        print(f"Received email settings update event: {event.id}")
                        
                        # Update the beat schedule with new settings
                        update_beat_schedule()
                        
                        print("Updated Celery Beat schedule based on email settings change")
                        
                except Exception as e:
                    print(f"Error processing email settings event: {e}")
                    
        except Exception as e:
            print(f"Email settings listener error: {e}")
    
    # Run the async listener
    try:
        asyncio.run(listen_for_email_settings())
    except Exception as e:
        print(f"Failed to start async email settings listener: {e}")

# Initialize beat schedule on import
update_beat_schedule()

if __name__ == "__main__":
    celery_app.start() 