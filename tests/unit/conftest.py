"""
Minimal conftest for unit tests that don't require database infrastructure.

This conftest overrides the autouse fixtures from the parent conftest.py
to allow unit tests to run without database connections.
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Add backend to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Track connection pools created during tests for cleanup
_test_pools = []


def _track_pool(pool):
    """Track a pool for cleanup."""
    if pool is not None:
        _test_pools.append(pool)
    return pool


async def _cleanup_pools():
    """Close all tracked pools."""
    for pool in _test_pools:
        try:
            if hasattr(pool, 'close'):
                await pool.close()
        except Exception:
            pass  # Ignore cleanup errors
    _test_pools.clear()


# Override autouse fixtures from parent conftest by making them no-ops
@pytest.fixture(autouse=True)
def auto_init_config_registry():
    """Skip config registry initialization for unit tests."""
    yield


@pytest.fixture(autouse=True)
def auto_track_async_pools(monkeypatch):
    """
    Automatically track and cleanup PostgreSQL connection pools.
    
    This fixture patches AsyncConnectionPool to track all created pools
    and ensures they're properly closed after each test to prevent
    "Task was destroyed but it is pending" warnings.
    """
    try:
        from psycopg_pool import AsyncConnectionPool
        
        original_init = AsyncConnectionPool.__init__
        
        def patched_init(self, *args, **kwargs):
            # Call original init
            result = original_init(self, *args, **kwargs)
            # Track this pool for cleanup
            _track_pool(self)
            return result
        
        monkeypatch.setattr(AsyncConnectionPool, '__init__', patched_init)
    except ImportError:
        # psycopg_pool not available, skip patching
        pass
    
    yield


@pytest.fixture(autouse=True)
async def auto_cleanup_connections():
    """Cleanup async connection pools created during tests."""
    yield
    # Cleanup any pools created during the test
    await _cleanup_pools()


@pytest.fixture(autouse=True)
async def auto_cleanup_checkpointer():
    """Skip checkpointer cleanup for unit tests."""
    yield


@pytest.fixture(autouse=True)
async def auto_cleanup_core_agent_data():
    """Skip core agent data cleanup for unit tests."""
    yield


@pytest.fixture(autouse=True)
def auto_cleanup_backup_files():
    """Skip backup file cleanup for unit tests."""
    yield


# Minimal event loop fixture for async tests
@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
