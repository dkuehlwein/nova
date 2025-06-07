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
import logging
import os
import sys
import pytest
from typing import AsyncGenerator

# Add backend to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    
    async def get_thread_ids(self) -> set:
        """Get all current thread IDs from checkpointer."""
        try:
            pool = AsyncConnectionPool(
                self.database_url.replace('+asyncpg', ''),
                open=False
            )
            await pool.open()
            
            thread_ids = set()
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                
                async for checkpoint_tuple in checkpointer.alist(None):
                    if checkpoint_tuple.config and checkpoint_tuple.config.get("configurable", {}).get("thread_id"):
                        thread_id = checkpoint_tuple.config["configurable"]["thread_id"]
                        if thread_id:
                            thread_ids.add(thread_id)
            
            await pool.close()
            return thread_ids
            
        except Exception as e:
            logger.warning(f"Error getting thread IDs: {e}")
            return set()
    
    async def record_initial_state(self):
        """Record the thread IDs that exist before test execution."""
        self._thread_ids_before = await self.get_thread_ids()
        logger.debug(f"Recorded {len(self._thread_ids_before)} threads before test")
    
    async def cleanup_test_threads(self):
        """Clean up only the threads created during test execution."""
        self._thread_ids_after = await self.get_thread_ids()
        new_thread_ids = self._thread_ids_after - self._thread_ids_before
        
        if not new_thread_ids:
            logger.debug("No new threads to clean up")
            return
        
        logger.info(f"Cleaning up {len(new_thread_ids)} test threads")
        
        try:
            pool = AsyncConnectionPool(
                self.database_url.replace('+asyncpg', ''),
                open=False
            )
            await pool.open()
            
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                
                for thread_id in new_thread_ids:
                    try:
                        await checkpointer.adelete_thread(thread_id)
                        logger.debug(f"Cleaned up test thread: {thread_id}")
                    except Exception as e:
                        logger.warning(f"Failed to clean thread {thread_id}: {e}")
            
            await pool.close()
            logger.info(f"✅ Cleaned up {len(new_thread_ids)} test threads")
            
        except Exception as e:
            logger.error(f"Error during test cleanup: {e}")
    
    async def cleanup_all_threads(self):
        """Clean up all threads (for full cleanup)."""
        thread_ids = await self.get_thread_ids()
        
        if not thread_ids:
            logger.info("No threads to clean up")
            return
        
        logger.info(f"Cleaning up all {len(thread_ids)} threads")
        
        try:
            pool = AsyncConnectionPool(
                self.database_url.replace('+asyncpg', ''),
                open=False
            )
            await pool.open()
            
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                
                for thread_id in thread_ids:
                    try:
                        await checkpointer.adelete_thread(thread_id)
                        logger.debug(f"Cleaned up thread: {thread_id}")
                    except Exception as e:
                        logger.warning(f"Failed to clean thread {thread_id}: {e}")
            
            await pool.close()
            logger.info(f"✅ Cleaned up all {len(thread_ids)} threads")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def close(self):
        """Close database connections."""
        await self.engine.dispose()


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
            logger.info(f"Current threads in checkpointer: {len(thread_ids)}")
            if thread_ids:
                logger.info(f"Thread IDs: {', '.join(sorted(list(thread_ids))[:10])}{'...' if len(thread_ids) > 10 else ''}")
        
        elif args.all:
            await cleaner.cleanup_all_threads()
        
        else:
            parser.print_help()
            
    finally:
        await cleaner.close()


if __name__ == "__main__":
    asyncio.run(main()) 