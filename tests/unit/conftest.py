"""
Minimal conftest for unit tests that don't require database infrastructure.

This conftest overrides the autouse fixtures from the parent conftest.py
to allow unit tests to run without database connections.
"""

import os
import sys
import pytest

# Add backend to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


# Override autouse fixtures from parent conftest by making them no-ops
@pytest.fixture(autouse=True)
def auto_init_config_registry():
    """Skip config registry initialization for unit tests."""
    yield


@pytest.fixture(autouse=True)
async def auto_cleanup_connections():
    """Skip connection cleanup for unit tests."""
    yield


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
