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
from pathlib import Path

# Ensure project root is in sys.path so that 'backend' package can be imported
PROJECT_ROOT = Path(__file__).resolve().parent
# The tests directory is at PROJECT_ROOT/tests
# We want the parent (actual project root)
PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BACKEND_PATH = PROJECT_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from test_cleanup import TestDataCleaner

# Disable LangSmith tracing for tests to avoid noise and gRPC connection issues
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_API_KEY"] = ""
os.environ["LANGCHAIN_PROJECT"] = ""


# Auto-use fixture to initialize config registry for tests
@pytest.fixture(autouse=True)
def auto_init_config_registry():
    """
    Auto-initialize config registry for all tests.
    
    This fixture ensures that the config registry is properly initialized
    with all necessary managers before tests run.
    """
    try:
        # Initialize unified configuration system
        from utils.config_registry import initialize_configs
        initialize_configs()
    except Exception as e:
        # Log but don't fail - some tests might not need full config
        print(f"Warning: Config registry initialization failed: {e}")
    
    yield
    
    # Cleanup after test
    try:
        from utils.config_registry import config_registry
        config_registry._managers.clear()
        config_registry._initialized = False
    except Exception:
        pass  # Best effort cleanup


# Auto-use fixture to properly close database connections
@pytest_asyncio.fixture(autouse=True)
async def auto_cleanup_connections():
    """
    Auto-cleanup fixture that ensures database connections are properly closed.
    
    This prevents asyncio warnings about pending tasks when connection pools
    aren't cleanly shut down during test teardown.
    """
    # Start tracking connection pools created during this test
    from test_cleanup import start_connection_pool_tracking, cleanup_connection_pools, stop_connection_pool_tracking
    await start_connection_pool_tracking()
    
    # Let the test run
    yield
    
    # Proper async cleanup based on SQLAlchemy best practices
    try:
        # 1. Close all tracked connection pools (prevents "ignored exceptions")
        await cleanup_connection_pools()
        
        # 2. Stop tracking
        await stop_connection_pool_tracking()
        
        # 3. Close database manager's engine
        from database.database import db_manager
        if hasattr(db_manager, 'engine') and db_manager.engine:
            await db_manager.engine.dispose()
        
        # 4. Give a small delay for connection pool cleanup
        await asyncio.sleep(0.05)
        
    except Exception as e:
        # Don't fail tests if cleanup fails, but log for debugging
        from backend.utils.logging import get_logger
        logger = get_logger("test_cleanup")
        logger.debug(
            "Connection cleanup warning",
            extra={"data": {"error": str(e)}}
        )


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
            "DELETE FROM tasks WHERE title LIKE '%Test%'",
            "DELETE FROM processed_emails WHERE email_id LIKE '%test%'",  # Clean up test emails
            # Note: persons/projects are now memory-based, no database tables to clean
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
        from backend.utils.logging import get_logger
        logger = get_logger("test_cleanup")
        logger.warning(
            "Pre-test cleanup failed",
            extra={"data": {"error": str(e)}}
        )

    yield  # Let the test run
    
    # Clean up after test
    try:
        await cleanup_test_data()
    except Exception as e:
        from backend.utils.logging import get_logger
        logger = get_logger("test_cleanup")
        logger.warning(
            "Post-test cleanup failed",
            extra={"data": {"error": str(e)}}
        )


# Auto-use fixture for backup file cleanup
@pytest.fixture(autouse=True)
def auto_cleanup_backup_files():
    """
    Auto-cleanup fixture for backup files created during tests.
    
    Removes any .bak files and backup directories created during testing
    to prevent accumulation of test backup files.
    """
    import shutil
    from pathlib import Path
    
    def cleanup_backups():
        """Remove backup files and directories created during tests."""
        try:
            # Clean up backup directories that might be created during tests
            backup_dirs = [
                Path("configs/backups"),
                Path("backend/agent/prompts/backups"),
                Path("backups"),  # Legacy location
            ]
            
            for backup_dir in backup_dirs:
                if backup_dir.exists() and backup_dir.is_dir():
                    # Only remove if it contains test-related backup files
                    test_backups = list(backup_dir.glob("*test*")) + list(backup_dir.glob("*Test*"))
                    if test_backups:
                        for backup_file in test_backups:
                            if backup_file.is_file():
                                backup_file.unlink()
                    
                    # Remove directory if empty
                    try:
                        if not any(backup_dir.iterdir()):
                            backup_dir.rmdir()
                    except OSError:
                        pass  # Directory not empty or other issue
            
            # Clean up any .bak files in common test locations
            test_locations = [
                Path("configs"),
                Path("backend/agent/prompts"),
                Path("tests"),
                Path("."),  # Current directory
            ]
            
            for location in test_locations:
                if location.exists():
                    for bak_file in location.glob("**/*test*.bak"):
                        bak_file.unlink()
                    for bak_file in location.glob("**/*Test*.bak"):
                        bak_file.unlink()
                        
        except Exception as e:
            # Don't fail tests if backup cleanup fails
            print(f"Warning: Backup cleanup failed: {e}")
    
    # Clean up before test to ensure clean state
    cleanup_backups()
    
    yield  # Let the test run
    
    # Clean up after test
    cleanup_backups()


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
