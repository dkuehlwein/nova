"""
Task data caching utilities using Redis.
Provides fast access to frequently requested task data with automatic invalidation.
"""

import json
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from database.database import db_manager
from models.models import Task, TaskStatus
from utils.redis_manager import get_redis
from utils.logging import get_logger

logger = get_logger("task_cache")

# Cache keys and TTL settings
CACHE_KEYS = {
    "task_counts": "nova:task_counts",
    "dashboard_data": "nova:dashboard_data",
}

# Cache TTL (Time To Live) in seconds
CACHE_TTL = {
    "task_counts": 60,  # 1 minute for fast-changing data
    "dashboard_data": 30,  # 30 seconds for dashboard
}


async def get_cached_task_counts() -> Optional[Dict[str, int]]:
    """Get task counts from Redis cache."""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return None
        
        cache_key = CACHE_KEYS["task_counts"]
        cached_data = await redis_client.get(cache_key)
        
        if cached_data:
            logger.debug("Task counts cache hit")
            return json.loads(cached_data)
        
        logger.debug("Task counts cache miss")
        return None
        
    except Exception as e:
        logger.error("Error getting cached task counts", extra={"data": {"error": str(e)}})
        return None


async def set_cached_task_counts(counts: Dict[str, int]) -> bool:
    """Set task counts in Redis cache."""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return False
        
        cache_key = CACHE_KEYS["task_counts"]
        ttl = CACHE_TTL["task_counts"]
        
        await redis_client.setex(
            cache_key,
            ttl,
            json.dumps(counts)
        )
        
        logger.debug("Cached task counts", extra={"data": {"ttl": ttl}})
        return True
        
    except Exception as e:
        logger.error("Error setting cached task counts", extra={"data": {"error": str(e)}})
        return False


async def get_task_counts_with_cache() -> Dict[str, int]:
    """Get task counts with Redis cache fallback to database."""
    # Try cache first
    cached_counts = await get_cached_task_counts()
    if cached_counts:
        return cached_counts
    
    # Cache miss - get from database
    async with db_manager.get_session() as session:
        task_count_query = select(Task.status, func.count(Task.id)).group_by(Task.status)
        result = await session.execute(task_count_query)
        status_counts = dict(result.all())
        
        # Convert enum keys to strings for JSON serialization
        task_counts = {status.value: count for status, count in status_counts.items()}
        
        # Ensure all status types are represented
        for status in TaskStatus:
            if status.value not in task_counts:
                task_counts[status.value] = 0
        
        # Cache the results
        await set_cached_task_counts(task_counts)
        
        logger.info("Retrieved task counts from database", extra={"data": {"task_counts": task_counts}})
        return task_counts


async def get_cached_dashboard_data() -> Optional[Dict[str, Any]]:
    """Get complete dashboard data from Redis cache."""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return None
        
        cache_key = CACHE_KEYS["dashboard_data"]
        cached_data = await redis_client.get(cache_key)
        
        if cached_data:
            logger.debug("Dashboard data cache hit")
            return json.loads(cached_data)
        
        logger.debug("Dashboard data cache miss")
        return None
        
    except Exception as e:
        logger.error("Error getting cached dashboard data", extra={"data": {"error": str(e)}})
        return None


async def set_cached_dashboard_data(data: Dict[str, Any]) -> bool:
    """Set dashboard data in Redis cache."""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return False
        
        cache_key = CACHE_KEYS["dashboard_data"]
        ttl = CACHE_TTL["dashboard_data"]
        
        # Add cache metadata
        cache_data = {
            **data,
            "cached_at": datetime.utcnow().isoformat(),
            "cache_ttl": ttl
        }
        
        # Custom serializer for proper handling of Pydantic models
        def json_serializer(obj):
            if hasattr(obj, 'model_dump'):
                return obj.model_dump()
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)
        
        await redis_client.setex(
            cache_key,
            ttl,
            json.dumps(cache_data, default=json_serializer)
        )
        
        logger.debug("Cached dashboard data", extra={"data": {"ttl": ttl}})
        return True
        
    except Exception as e:
        logger.error("Error setting cached dashboard data", extra={"data": {"error": str(e)}})
        return False


async def invalidate_task_cache():
    """Invalidate all task-related cache entries."""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return
        
        # Delete all task-related cache keys
        for cache_key in CACHE_KEYS.values():
            await redis_client.delete(cache_key)
        
        logger.info("Task cache invalidated")
        
    except Exception as e:
        logger.error("Error invalidating task cache", extra={"data": {"error": str(e)}})


async def get_tasks_by_status_with_cache(use_cache: bool = True) -> Dict[str, list]:
    """Get tasks organized by status with optional caching."""
    if not use_cache:
        return await _get_tasks_by_status_from_db()
    
    # For now, we don't cache full task data due to size
    # Only cache task counts for performance
    return await _get_tasks_by_status_from_db()


async def _get_tasks_by_status_from_db() -> Dict[str, list]:
    """Get tasks by status directly from database."""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.comments))
            .order_by(Task.updated_at.desc())
        )
        tasks = result.scalars().all()
        
        # Initialize all status categories
        tasks_by_status = {}
        for status in TaskStatus:
            tasks_by_status[status.value] = []
        
        # Group tasks by status
        for task in tasks:
            task_data = {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "summary": task.summary,
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "tags": task.tags or [],
                "needs_decision": task.status == TaskStatus.NEEDS_REVIEW,
                "decision_type": "task_review" if task.status == TaskStatus.NEEDS_REVIEW else None,
                "persons": task.person_emails or [],
                "projects": task.project_names or [],
                "comments_count": len(task.comments)
            }
            
            tasks_by_status[task.status.value].append(task_data)
        
        return tasks_by_status


# Background task to warm cache
async def warm_task_cache():
    """Warm the task cache by pre-loading frequently accessed data."""
    try:
        logger.info("Warming task cache...")
        
        # Pre-load task counts
        await get_task_counts_with_cache()
        
        logger.info("Task cache warmed successfully")
        
    except Exception as e:
        logger.error("Error warming task cache", extra={"data": {"error": str(e)}})