"""
Input Hooks API Endpoints

Provides API endpoints for viewing, configuring, and triggering input hooks.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from utils.logging import get_logger
from utils.redis_manager import get_sync_redis

logger = get_logger("hooks_api")

# Redis key pattern for hook stats (must match hook_tasks.py)
HOOK_STATS_KEY = "hook:stats:{hook_name}"


def _get_hook_stats_from_redis(hook_name: str) -> dict:
    """Get hook statistics from Redis."""
    try:
        import json
        redis_client = get_sync_redis()
        if not redis_client:
            return {}

        key = HOOK_STATS_KEY.format(hook_name=hook_name)
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        return {}
    except Exception as e:
        logger.warning("Failed to get hook stats from Redis", extra={"data": {"error": str(e)}})
        return {}


def _get_all_hook_stats_from_redis(hook_names: list) -> dict:
    """Get stats for all hooks from Redis."""
    return {name: _get_hook_stats_from_redis(name) for name in hook_names}

router = APIRouter(prefix="/api/hooks", tags=["hooks"])


# Response models
class HookStatsResponse(BaseModel):
    """Statistics for a hook."""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    items_processed: int = 0
    tasks_created: int = 0
    tasks_updated: int = 0


class HookResponse(BaseModel):
    """Response model for a single hook."""
    name: str
    hook_type: str
    display_name: str  # Human-readable name for UI display
    enabled: bool
    polling_interval: int
    status: str = "idle"  # "idle", "running", "error", "disabled"
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    stats: HookStatsResponse = Field(default_factory=HookStatsResponse)
    last_error: Optional[str] = None
    hook_settings: Dict[str, Any] = Field(default_factory=dict)


class HooksListResponse(BaseModel):
    """Response model for listing all hooks."""
    hooks: List[HookResponse]


class HookConfigUpdate(BaseModel):
    """Request model for updating hook configuration."""
    enabled: Optional[bool] = None
    polling_interval: Optional[int] = Field(default=None, gt=0)


class TriggerResponse(BaseModel):
    """Response model for triggering a hook."""
    task_id: str
    hook_name: str
    status: str = "queued"
    queued_at: str


def _ensure_hooks_initialized():
    """Ensure the hook registry is initialized and return it."""
    from input_hooks.hook_registry import input_hook_registry, initialize_hooks

    if not input_hook_registry._initialized:
        logger.info("Initializing hook registry from API")
        initialize_hooks()

    return input_hook_registry


def _get_hook_status(hook, stats: dict) -> str:
    """Determine hook status based on config and stats."""
    if not hook.config.enabled:
        return "disabled"
    if stats.get("last_error"):
        return "error"
    return "idle"


def _calculate_next_run(last_run: Optional[datetime], interval: int, enabled: bool) -> Optional[str]:
    """Calculate next scheduled run time."""
    if not enabled:
        return None
    if not last_run:
        return datetime.now(timezone.utc).isoformat()
    next_time = last_run.timestamp() + interval
    return datetime.fromtimestamp(next_time, tz=timezone.utc).isoformat()


@router.get("/", response_model=HooksListResponse)
async def list_hooks():
    """
    List all registered hooks with their status and statistics.
    """
    try:
        input_hook_registry = _ensure_hooks_initialized()

        hooks_response = []
        hook_names = input_hook_registry.list_hooks()
        # Get stats from Redis (shared across processes)
        all_stats = _get_all_hook_stats_from_redis(hook_names)

        for hook_name in hook_names:
            hook = input_hook_registry.get_hook(hook_name)
            if not hook:
                continue

            stats = all_stats.get(hook_name, {})
            config = hook.config

            # Get last run time from stats
            last_run_str = stats.get("last_run")
            last_run_dt = None
            if last_run_str:
                try:
                    last_run_dt = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            hook_response = HookResponse(
                name=hook_name,
                hook_type=config.hook_type,
                display_name=config.display_name or hook_name,
                enabled=config.enabled,
                polling_interval=config.polling_interval,
                status=_get_hook_status(hook, stats),
                last_run=last_run_str,
                next_run=_calculate_next_run(last_run_dt, config.polling_interval, config.enabled),
                stats=HookStatsResponse(
                    total_runs=stats.get("total_runs", 0),
                    successful_runs=stats.get("successful_runs", 0),
                    failed_runs=stats.get("failed_runs", 0),
                    items_processed=stats.get("items_processed", 0),
                    tasks_created=stats.get("tasks_created", 0),
                    tasks_updated=stats.get("tasks_updated", 0),
                ),
                last_error=stats.get("last_error"),
                hook_settings=config.hook_settings.model_dump() if hasattr(config.hook_settings, 'model_dump') else dict(config.hook_settings),
            )
            hooks_response.append(hook_response)

        return HooksListResponse(hooks=hooks_response)

    except Exception as e:
        logger.error("Failed to list hooks", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list hooks: {str(e)}")


@router.get("/{hook_name}", response_model=HookResponse)
async def get_hook(hook_name: str):
    """
    Get details for a specific hook.
    """
    try:
        input_hook_registry = _ensure_hooks_initialized()

        hook = input_hook_registry.get_hook(hook_name)
        if not hook:
            raise HTTPException(status_code=404, detail=f"Hook '{hook_name}' not found")

        # Get stats from Redis (shared across processes)
        stats = _get_hook_stats_from_redis(hook_name)
        config = hook.config

        # Get last run time from stats
        last_run_str = stats.get("last_run")
        last_run_dt = None
        if last_run_str:
            try:
                last_run_dt = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return HookResponse(
            name=hook_name,
            hook_type=config.hook_type,
            display_name=config.display_name or hook_name,
            enabled=config.enabled,
            polling_interval=config.polling_interval,
            status=_get_hook_status(hook, stats),
            last_run=last_run_str,
            next_run=_calculate_next_run(last_run_dt, config.polling_interval, config.enabled),
            stats=HookStatsResponse(
                total_runs=stats.get("total_runs", 0),
                successful_runs=stats.get("successful_runs", 0),
                failed_runs=stats.get("failed_runs", 0),
                items_processed=stats.get("items_processed", 0),
                tasks_created=stats.get("tasks_created", 0),
                tasks_updated=stats.get("tasks_updated", 0),
            ),
            last_error=stats.get("last_error"),
            hook_settings=config.hook_settings.model_dump() if hasattr(config.hook_settings, 'model_dump') else dict(config.hook_settings),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get hook", exc_info=True, extra={"data": {"hook_name": hook_name}})
        raise HTTPException(status_code=500, detail=f"Failed to get hook: {str(e)}")


@router.patch("/{hook_name}", response_model=HookResponse)
async def update_hook(hook_name: str, update: HookConfigUpdate):
    """
    Update configuration for a specific hook.

    Updates the hook configuration and triggers a Celery beat schedule reload.
    """
    try:
        from utils.config_registry import config_registry

        input_hook_registry = _ensure_hooks_initialized()

        hook = input_hook_registry.get_hook(hook_name)
        if not hook:
            raise HTTPException(status_code=404, detail=f"Hook '{hook_name}' not found")

        # Get current config and update fields
        config_manager = config_registry.get_manager("input_hooks")
        if not config_manager:
            raise HTTPException(status_code=500, detail="Hook configuration manager not available")

        hooks_config = config_manager.get_config()
        current_config = hooks_config.hooks.get(hook_name)
        if not current_config:
            raise HTTPException(status_code=404, detail=f"Hook '{hook_name}' configuration not found")

        # Apply updates
        if update.enabled is not None:
            current_config.enabled = update.enabled
        if update.polling_interval is not None:
            current_config.polling_interval = update.polling_interval

        # Save updated config
        hooks_config.hooks[hook_name] = current_config
        config_manager.save_config(hooks_config)

        # Reload hook instance with new config
        input_hook_registry.update_hook_config(hook_name, current_config)

        logger.info(
            "Hook configuration updated",
            extra={"data": {
                "hook_name": hook_name,
                "enabled": current_config.enabled,
                "polling_interval": current_config.polling_interval,
            }}
        )

        # Return updated hook info
        return await get_hook(hook_name)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update hook", exc_info=True, extra={"data": {"hook_name": hook_name}})
        raise HTTPException(status_code=500, detail=f"Failed to update hook: {str(e)}")


@router.post("/{hook_name}/trigger", response_model=TriggerResponse)
async def trigger_hook(hook_name: str):
    """
    Manually trigger a hook to process items immediately.

    Queues a Celery task to process the hook's items.
    """
    try:
        from tasks.hook_tasks import process_hook_items

        input_hook_registry = _ensure_hooks_initialized()

        hook = input_hook_registry.get_hook(hook_name)
        if not hook:
            raise HTTPException(status_code=404, detail=f"Hook '{hook_name}' not found")

        # Queue the task
        result = process_hook_items.delay(hook_name)

        logger.info(
            "Hook manually triggered",
            extra={"data": {
                "hook_name": hook_name,
                "task_id": result.id,
            }}
        )

        return TriggerResponse(
            task_id=result.id,
            hook_name=hook_name,
            status="queued",
            queued_at=datetime.now(timezone.utc).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger hook", exc_info=True, extra={"data": {"hook_name": hook_name}})
        raise HTTPException(status_code=500, detail=f"Failed to trigger hook: {str(e)}")
