"""
Pytest configuration and fixtures for Nova backend tests.

Provides automatic cleanup of checkpointer data to prevent
database growth during test runs.
"""

import sys
import os
import pytest
import asyncio

# Add the backend directory to the Python path
backend_path = os.path.join(os.path.dirname(__file__), '../backend')
sys.path.insert(0, backend_path)

from test_cleanup import TestDataCleaner


# Auto-use fixture for all async tests to clean up checkpointer data
@pytest.fixture(autouse=True)
async def auto_cleanup_checkpointer():
    """
    Auto-cleanup fixture that runs after every test.
    
    This fixture automatically cleans up any chat threads created
    during test execution to prevent checkpointer database growth.
    """
    cleaner = TestDataCleaner()
    
    # Record initial state before test
    await cleaner.record_initial_state()
    
    yield
    
    # Clean up only threads created during this test
    await cleaner.cleanup_test_threads()
    await cleaner.close()


# Optional: Fixture for tests that need to start with a completely clean state
@pytest.fixture
async def clean_slate_checkpointer():
    """
    Fixture that ensures checkpointer is completely clean before test.
    
    Use this for tests that need to start with a guaranteed clean state.
    Example:
        async def test_something(clean_slate_checkpointer):
            # Test runs with completely clean checkpointer
            pass
    """
    cleaner = TestDataCleaner()
    
    # Clean everything before test
    await cleaner.cleanup_all_threads()
    
    yield cleaner
    
    # Clean everything after test too
    await cleaner.cleanup_all_threads()
    await cleaner.close()


# Mark all tests as asyncio by default if they're async
def pytest_configure(config):
    """Configure pytest for async tests."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


# Ensure asyncio tests work properly
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close() 