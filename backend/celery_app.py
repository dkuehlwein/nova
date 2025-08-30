"""
Celery application configuration for Nova input hooks.

Hook-based task processing system supporting multiple input sources 
(email, calendar, etc.) through the hook registry system.
"""
from celery import Celery
from celery.signals import worker_ready, worker_shutdown, beat_init
from config import settings

# Create Celery instance with hook tasks
celery_app = Celery(
    "nova",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.hook_tasks"]  # Hook-based task system
)

# Celery configuration
celery_app.conf.update(
    # Task routing (updated dynamically by hook registry)
    task_routes={
        # Generic hook tasks
        "tasks.hook_tasks.process_hook_items": {"queue": "hooks"},
        "tasks.hook_tasks.process_single_item": {"queue": "hooks"},
        "tasks.hook_tasks.replay_failed_hook_task": {"queue": "hooks"},
        "tasks.hook_tasks.health_check_all_hooks": {"queue": "hooks"},
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
    
    # Beat schedule (configured dynamically by hooks)
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
    Update Celery Beat schedule using the hook system.
    
    This function generates schedules for all enabled hooks dynamically.
    """
    import os
    
    try:
        # Initialize configuration system first (required for hook registry)
        from utils.config_registry import initialize_configs
        initialize_configs()
        
        from input_hooks.hook_registry import input_hook_registry, initialize_hooks
        
        # Always initialize hooks to ensure fresh configuration (important for Beat process)
        print("Initializing hook registry for Beat scheduler...")
        initialize_hooks()
        
        # Get schedules from hook registry
        hook_schedules = input_hook_registry.get_celery_schedules()
        
        if hook_schedules:
            celery_app.conf.beat_schedule = hook_schedules
            print(f"Updated hook-based beat schedule for {len(hook_schedules)} hooks")
            
            # Log which hooks are scheduled
            for schedule_name in hook_schedules.keys():
                hook_name = schedule_name.replace("process-", "")
                hook = input_hook_registry.get_hook(hook_name)
                if hook:
                    interval = hook.config.polling_interval
                    print(f"  - {hook_name}: every {interval} seconds")
        else:
            celery_app.conf.beat_schedule = {}
            print("No enabled hooks found - cleared beat schedule")
        
        # Force PersistentScheduler to reload by removing the schedule file
        schedule_file = celery_app.conf.beat_schedule_filename
        if os.path.exists(schedule_file):
            os.remove(schedule_file)
            print(f"Removed persistent schedule file {schedule_file} to force reload")
            
    except Exception as e:
        print(f"Failed to update hook-based beat schedule: {e}")
        celery_app.conf.beat_schedule = {}


# Signal handlers for worker lifecycle
@worker_ready.connect
def worker_ready_handler(sender=None, **_kwargs):
    """Worker ready signal handler for hook system initialization."""
    print("Celery worker ready - initializing hook system")
    
    # Initialize unified configuration system
    try:
        from utils.config_registry import initialize_configs
        print("Initializing configuration system...")
        initialize_configs()
        print("Configuration system initialized successfully")
    except Exception as e:
        print(f"Failed to initialize configurations: {e}")
    
    # Initialize hook system
    try:
        from input_hooks.hook_registry import initialize_hooks
        print("Initializing input hook system...")
        initialize_hooks()
        print("Hook system initialized successfully")
    except Exception as e:
        print(f"Failed to initialize hook system: {e}")
    
    # Update beat schedule with hook configurations
    update_beat_schedule()


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **_kwargs):
    """Worker shutdown signal handler for cleanup."""
    print("Celery worker shutting down - cleaning up hook system")
    
    try:
        from input_hooks.hook_registry import cleanup_hooks
        cleanup_hooks()
        print("Hook system cleaned up successfully")
    except Exception as e:
        print(f"Error during hook system cleanup: {e}")


@beat_init.connect
def beat_init_handler(sender=None, **_kwargs):
    """Beat process initialization signal handler for hook system."""
    print("Celery Beat process starting - initializing hook system")
    
    # Initialize unified configuration system
    try:
        from utils.config_registry import initialize_configs
        print("Initializing configuration system for Beat...")
        initialize_configs()
        print("Configuration system initialized successfully")
    except Exception as e:
        print(f"Failed to initialize configurations: {e}")
    
    # Initialize hook system
    try:
        from input_hooks.hook_registry import initialize_hooks
        print("Initializing input hook system for Beat...")
        initialize_hooks()
        print("Hook system initialized successfully")
    except Exception as e:
        print(f"Failed to initialize hook system: {e}")
    
    # Update beat schedule with hook configurations
    print("Updating beat schedule from hook configurations...")
    update_beat_schedule()
    print("Beat initialization complete")


# Task for updating beat schedule dynamically
@celery_app.task(name="celery.update_beat_schedule") 
def update_beat_schedule_task():
    """
    Celery task to update beat schedule dynamically.
    
    This can be called when hook configurations change.
    """
    try:
        update_beat_schedule()
        return {"status": "success", "message": "Beat schedule updated"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Initialize beat schedule on module import for Celery Beat to pick up
# This is the standard approach for Celery beat schedules
try:
    print("Initializing beat schedule for Celery Beat...")
    update_beat_schedule()
    print("Beat schedule initialization completed")
except Exception as e:
    print(f"Failed to initialize beat schedule: {e}")
    # Set empty schedule as fallback
    celery_app.conf.beat_schedule = {}