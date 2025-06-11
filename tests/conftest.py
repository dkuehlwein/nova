"""
Pytest configuration and fixtures for Nova backend tests.

Provides automatic cleanup of checkpointer data AND core agent test data 
to prevent database growth during test runs.

Disables LangSmith tracing during tests to prevent gRPC connection issues.
"""

import sys
import os
import pytest
import pytest_asyncio
import asyncio

# Add the backend directory to the Python path
backend_path = os.path.join(os.path.dirname(__file__), '../backend')
sys.path.insert(0, backend_path)

from test_cleanup import TestDataCleaner

# Disable LangSmith tracing for tests to avoid noise
os.environ["LANGSMITH_TRACING"] = "false"


# Auto-use fixture to properly close database connections
@pytest_asyncio.fixture(autouse=True)
async def auto_cleanup_connections():
    """
    Auto-cleanup fixture that ensures database connections are properly closed.
    
    This prevents asyncio warnings about pending tasks when connection pools
    aren't cleanly shut down during test teardown.
    """
    # Let the test run
    yield
    
    # Proper async cleanup based on SQLAlchemy best practices
    try:
        from database.database import db_manager
        
        # Close the database manager's engine properly to prevent connection pool warnings
        if hasattr(db_manager, 'engine') and db_manager.engine:
            # Dispose of the engine to close all connections
            await db_manager.engine.dispose()
        
        # Give a small delay for connection pool cleanup without aggressive task cancellation
        await asyncio.sleep(0.05)
        
    except Exception as e:
        # Don't fail tests if cleanup fails, but log for debugging
        import logging
        logging.getLogger(__name__).debug(f"Connection cleanup warning: {e}")


# Auto-use fixture for all async tests to clean up checkpointer data
@pytest_asyncio.fixture(autouse=True)
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
@pytest_asyncio.fixture
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


# Auto-use fixture for core agent tests to clean up test data
@pytest_asyncio.fixture(autouse=True)
async def auto_cleanup_core_agent_data():
    """
    Auto-cleanup fixture for core agent test data.
    
    Cleans up test tasks, persons, projects, and agent status created during tests.
    Runs BEFORE and AFTER every test to prevent test data accumulation.
    """
    
    async def cleanup_test_data():
        """Clean up test data with proper foreign key handling"""
        from database.database import db_manager
        from sqlalchemy import text
        
        # Order matters for foreign key constraints - clean child tables first
        cleanup_queries = [
            "DELETE FROM task_comments WHERE author = 'core_agent' OR content LIKE '%Test%'",
            "DELETE FROM task_person WHERE task_id IN (SELECT id FROM tasks WHERE title LIKE '%Test%')",
            "DELETE FROM task_project WHERE task_id IN (SELECT id FROM tasks WHERE title LIKE '%Test%')",
            "DELETE FROM tasks WHERE title LIKE '%Test%'",
            "DELETE FROM persons WHERE email LIKE '%test%'",
            "DELETE FROM projects WHERE name LIKE '%Test%'",
            # Note: agent_status is preserved - needed for core agent to function
        ]
        
        # Process each query in separate transaction to avoid abort issues
        for query in cleanup_queries:
            try:
                async with db_manager.get_session() as session:
                    await session.execute(text(query))
                    await session.commit()
            except Exception:
                # Individual table cleanup failed - continue with others
                pass
    
    # Clean up before test to ensure clean state
    print("🧹 Running PRE-test cleanup...")
    try:
        await cleanup_test_data()
        print("✅ PRE-test cleanup completed")
    except Exception as e:
        print(f"Warning: Pre-test cleanup failed: {e}")

    yield  # Let the test run
    
    # Clean up after test
    try:
        await cleanup_test_data()
    except Exception as e:
        print(f"Warning: Post-test cleanup failed: {e}")


# Mark all tests as asyncio by default if they're async
def pytest_configure(config):
    """Configure pytest for async tests."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


# Ensure asyncio tests work properly with proper cleanup
@pytest_asyncio.fixture(scope="session")
async def event_loop():
    """Create an instance of the default event loop for the test session with proper cleanup."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    
    yield loop
    
    # Properly close the loop and clean up pending tasks
    try:
        # Cancel any remaining tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        
        # Wait for cancellation to complete
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
            
    finally:
        loop.close()


@pytest.fixture(scope="session", autouse=True)
def disable_langsmith_tracing():
    """Disable LangSmith tracing for all tests to avoid gRPC issues."""
    # Save original values
    original_tracing = os.environ.get("LANGCHAIN_TRACING_V2")

    
    # Disable tracing during tests
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

    
    yield
    
    # Restore original values after tests
    if original_tracing is not None:
        os.environ["LANGCHAIN_TRACING_V2"] = original_tracing
    else:
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
