#!/usr/bin/env python3
"""
Test Cleanup Utility for Nova

This script provides automatic cleanup for tests to prevent
checkpointer data accumulation during test runs.

Can be used as:
1. Pytest fixture for automatic cleanup
2. Standalone script for manual cleanup
3. Integration with CI/CD pipelines
"""

import asyncio
import os
import sys
import pytest
import weakref
from typing import AsyncGenerator, Set
from unittest.mock import patch, AsyncMock

# Add backend to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from backend.utils.logging import get_logger

logger = get_logger("test_cleanup")


class TestConnectionPoolTracker:
    """Tracks connection pools created during tests for proper cleanup."""
    
    def __init__(self):
        self._pools: Set[AsyncConnectionPool] = set()
        self._original_pool_init = None
        self._patching = False
    
    def start_tracking(self):
        """Start tracking AsyncConnectionPool creation."""
        if self._patching:
            return
            
        self._original_pool_init = AsyncConnectionPool.__init__
        
        def tracked_init(pool_self, *args, **kwargs):
            # Call original __init__
            self._original_pool_init(pool_self, *args, **kwargs)
            # Track this pool
            self._pools.add(pool_self)
            logger.debug(f"Tracking new AsyncConnectionPool, total tracked: {len(self._pools)}")
        
        AsyncConnectionPool.__init__ = tracked_init
        self._patching = True
        logger.debug("Started tracking AsyncConnectionPool creation")
    
    def stop_tracking(self):
        """Stop tracking AsyncConnectionPool creation."""
        if not self._patching:
            return
            
        AsyncConnectionPool.__init__ = self._original_pool_init
        self._patching = False
        logger.debug("Stopped tracking AsyncConnectionPool creation")
    
    async def close_all_tracked_pools(self):
        """Close all tracked pools."""
        if not self._pools:
            return
        
        logger.debug(f"Closing {len(self._pools)} tracked AsyncConnectionPools")
        
        # Create list to avoid modifying set during iteration
        pools_to_close = list(self._pools)
        
        for pool in pools_to_close:
            try:
                # Check if pool is still open before trying to close
                if hasattr(pool, '_closed') and not pool._closed:
                    await asyncio.wait_for(pool.close(), timeout=3.0)
                elif not hasattr(pool, '_closed'):
                    # Fallback for pools without _closed attribute
                    await asyncio.wait_for(pool.close(), timeout=3.0)
                logger.debug("Successfully closed tracked pool")
            except asyncio.TimeoutError:
                logger.warning("Tracked pool close timed out after 3 seconds")
            except Exception as e:
                logger.debug(f"Error closing tracked pool: {e}")
            finally:
                # Remove from tracking even if close failed
                self._pools.discard(pool)
        
        logger.debug("✅ All tracked pools closed")


# Global tracker instance for tests
_test_pool_tracker = TestConnectionPoolTracker()


class TestDataCleaner:
    """Utility for cleaning up test data from checkpointer."""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova_kanban'
        )
        self.engine = create_async_engine(self.database_url)
        self._thread_ids_before = set()
        self._thread_ids_after = set()
        # Track pools created by this cleaner for proper cleanup
        self._pools: Set[AsyncConnectionPool] = set()
    
    async def _create_pool(self) -> AsyncConnectionPool:
        """Create and track a connection pool."""
        pool = AsyncConnectionPool(
            self.database_url.replace('+asyncpg', ''),
            open=False
        )
        await pool.open()
        self._pools.add(pool)
        return pool
    
    async def _close_all_pools(self):
        """Close all pools created by this cleaner."""
        if not self._pools:
            return
        
        logger.debug(f"Closing {len(self._pools)} pools created by TestDataCleaner")
        
        # Create list to avoid modifying set during iteration
        pools_to_close = list(self._pools)
        
        for pool in pools_to_close:
            try:
                # Check if pool is still open before trying to close
                if hasattr(pool, '_closed') and not pool._closed:
                    await asyncio.wait_for(pool.close(), timeout=3.0)
                elif not hasattr(pool, '_closed'):
                    # Fallback for pools without _closed attribute
                    await asyncio.wait_for(pool.close(), timeout=3.0)
                logger.debug("Successfully closed TestDataCleaner pool")
            except asyncio.TimeoutError:
                logger.warning("TestDataCleaner pool close timed out after 3 seconds")
            except Exception as e:
                logger.debug(f"Error closing TestDataCleaner pool: {e}")
            finally:
                # Remove from tracking even if close failed
                self._pools.discard(pool)
    
    async def get_thread_ids(self) -> set:
        """Get all current thread IDs from checkpointer."""
        try:
            pool = await self._create_pool()
            
            thread_ids = set()
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                
                async for checkpoint_tuple in checkpointer.alist(None):
                    if checkpoint_tuple.config and checkpoint_tuple.config.get("configurable", {}).get("thread_id"):
                        thread_id = checkpoint_tuple.config["configurable"]["thread_id"]
                        if thread_id:
                            thread_ids.add(thread_id)
            
            return thread_ids
            
        except Exception as e:
            logger.warning(
                "Error getting thread IDs",
                extra={"data": {"error": str(e)}}
            )
            return set()
    
    async def record_initial_state(self):
        """Record the thread IDs that exist before test execution."""
        self._thread_ids_before = await self.get_thread_ids()
        logger.debug(
            "Recorded threads before test",
            extra={"data": {"thread_count": len(self._thread_ids_before)}}
        )
    
    async def cleanup_test_threads(self):
        """Clean up only the threads created during test execution."""
        self._thread_ids_after = await self.get_thread_ids()
        new_thread_ids = self._thread_ids_after - self._thread_ids_before
        
        if not new_thread_ids:
            logger.debug("No new threads to clean up")
            return
        
        logger.info(
            "Cleaning up test threads",
            extra={"data": {"thread_count": len(new_thread_ids)}}
        )
        
        try:
            pool = await self._create_pool()
            
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                
                for thread_id in new_thread_ids:
                    try:
                        await checkpointer.adelete_thread(thread_id)
                        logger.debug(
                            "Cleaned up test thread",
                            extra={"data": {"thread_id": thread_id}}
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to clean thread",
                            extra={"data": {"thread_id": thread_id, "error": str(e)}}
                        )
            
            logger.info(
                "✅ Cleaned up test threads",
                extra={"data": {"thread_count": len(new_thread_ids)}}
            )
            
        except Exception as e:
            logger.error(
                "Error during test cleanup",
                exc_info=True,
                extra={"data": {"error": str(e)}}
            )
    
    async def cleanup_all_threads(self):
        """Clean up all threads (for full cleanup)."""
        thread_ids = await self.get_thread_ids()
        
        if not thread_ids:
            logger.info("No threads to clean up")
            return
        
        logger.info(
            "Cleaning up all threads",
            extra={"data": {"thread_count": len(thread_ids)}}
        )
        
        try:
            pool = await self._create_pool()
            
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                
                for thread_id in thread_ids:
                    try:
                        await checkpointer.adelete_thread(thread_id)
                        logger.debug(
                            "Cleaned up thread",
                            extra={"data": {"thread_id": thread_id}}
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to clean thread",
                            extra={"data": {"thread_id": thread_id, "error": str(e)}}
                        )
            
            logger.info(
                "✅ Cleaned up all threads",
                extra={"data": {"thread_count": len(thread_ids)}}
            )
            
        except Exception as e:
            logger.error(
                "Error during cleanup",
                exc_info=True,
                extra={"data": {"error": str(e)}}
            )
    
    async def close(self):
        """Close database connections and all pools."""
        # Close all pools first
        await self._close_all_pools()
        
        # Then close SQLAlchemy engine
        await self.engine.dispose()


# Functions for test fixture use
async def start_connection_pool_tracking():
    """Start tracking connection pools for tests."""
    _test_pool_tracker.start_tracking()


async def cleanup_connection_pools():
    """Close all tracked connection pools. Used by tests."""
    await _test_pool_tracker.close_all_tracked_pools()


async def stop_connection_pool_tracking():
    """Stop tracking connection pools for tests."""
    _test_pool_tracker.stop_tracking()


# Pytest fixtures for automatic test cleanup
@pytest.fixture
async def clean_checkpointer():
    """Pytest fixture that cleans up only test-created threads."""
    cleaner = TestDataCleaner()
    
    # Record initial state before test
    await cleaner.record_initial_state()
    
    yield cleaner
    
    # Clean up only threads created during test
    await cleaner.cleanup_test_threads()
    await cleaner.close()


@pytest.fixture
async def force_clean_checkpointer():
    """Pytest fixture that cleans up ALL threads (use with caution)."""
    cleaner = TestDataCleaner()
    
    yield cleaner
    
    # Clean up all threads
    await cleaner.cleanup_all_threads()
    await cleaner.close()


# Context manager for manual use
class CheckpointerCleaner:
    """Context manager for cleaning checkpointer data."""
    
    def __init__(self, clean_all: bool = False):
        self.clean_all = clean_all
        self.cleaner = TestDataCleaner()
    
    async def __aenter__(self):
        if not self.clean_all:
            await self.cleaner.record_initial_state()
        return self.cleaner
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.clean_all:
            await self.cleaner.cleanup_all_threads()
        else:
            await self.cleaner.cleanup_test_threads()
        await self.cleaner.close()


# CLI interface
async def main():
    """CLI interface for manual cleanup."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Data Cleanup for Nova')
    parser.add_argument('--all', action='store_true', help='Clean all threads (not just test ones)')
    parser.add_argument('--stats', action='store_true', help='Show current thread statistics')
    
    args = parser.parse_args()
    
    cleaner = TestDataCleaner()
    
    try:
        if args.stats:
            thread_ids = await cleaner.get_thread_ids()
            logger.info(
                "Current threads in checkpointer",
                extra={"data": {"thread_count": len(thread_ids)}}
            )
            if thread_ids:
                sample_ids = sorted(list(thread_ids))[:10]
                logger.info(
                    "Thread IDs sample",
                    extra={
                        "data": {
                            "sample_ids": sample_ids,
                            "truncated": len(thread_ids) > 10,
                            "total_count": len(thread_ids)
                        }
                    }
                )
        
        elif args.all:
            await cleaner.cleanup_all_threads()
        
        else:
            parser.print_help()
            
    finally:
        await cleaner.close()


if __name__ == "__main__":
    asyncio.run(main()) 