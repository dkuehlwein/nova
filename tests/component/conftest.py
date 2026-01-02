"""
Pytest configuration and fixtures for component tests.

Component tests test a single component with its real database interactions.
They require PostgreSQL and/or Redis running.

Provides automatic cleanup of:
- Checkpointer data
- Core agent test data
- Database connections
- Backup files
"""

import os
import pytest
import pytest_asyncio
import asyncio
from pathlib import Path

from test_cleanup import TestDataCleaner


# Auto-use fixture to initialize config registry for tests
@pytest.fixture(autouse=True)
def auto_init_config_registry():
    """
    Auto-initialize config registry for all tests.

    This fixture ensures that the config registry is properly initialized
    with all necessary managers before tests run.
    """
    try:
        from utils.config_registry import initialize_configs
        initialize_configs()
    except Exception as e:
        print(f"Warning: Config registry initialization failed: {e}")

    yield

    # Cleanup after test
    try:
        from utils.config_registry import config_registry
        config_registry._managers.clear()
        config_registry._initialized = False
    except Exception:
        pass


# Auto-use fixture to properly close database connections
@pytest_asyncio.fixture(autouse=True)
async def auto_cleanup_connections():
    """
    Auto-cleanup fixture that ensures database connections are properly closed.

    This prevents asyncio warnings about pending tasks when connection pools
    aren't cleanly shut down during test teardown.
    """
    from test_cleanup import (
        start_connection_pool_tracking,
        cleanup_connection_pools,
        stop_connection_pool_tracking,
    )
    await start_connection_pool_tracking()

    yield

    try:
        await cleanup_connection_pools()
        await stop_connection_pool_tracking()

        from database.database import db_manager
        if hasattr(db_manager, 'engine') and db_manager.engine:
            await db_manager.engine.dispose()

        await asyncio.sleep(0.05)

    except Exception as e:
        from backend.utils.logging import get_logger
        logger = get_logger("test_cleanup")
        logger.debug("Connection cleanup warning", extra={"data": {"error": str(e)}})


# Auto-use fixture for all async tests to clean up checkpointer data
@pytest_asyncio.fixture(autouse=True)
async def auto_cleanup_checkpointer():
    """
    Auto-cleanup fixture that runs after every test.

    This fixture automatically cleans up any chat threads created
    during test execution to prevent checkpointer database growth.
    """
    cleaner = TestDataCleaner()
    await cleaner.record_initial_state()

    yield

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
    await cleaner.cleanup_all_threads()

    yield cleaner

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
        """Clean up test data with proper foreign key handling."""
        from database.database import db_manager
        from sqlalchemy import text

        cleanup_queries = [
            "DELETE FROM task_comments WHERE author = 'core_agent' OR content LIKE '%Test%'",
            "DELETE FROM tasks WHERE title LIKE '%Test%'",
            "DELETE FROM processed_emails WHERE email_id LIKE '%test%'",
        ]

        for query in cleanup_queries:
            try:
                async with db_manager.get_session() as session:
                    await session.execute(text(query))
                    await session.commit()
            except Exception:
                pass

    print("🧹 Running PRE-test cleanup...")
    try:
        await cleanup_test_data()
        print("✅ PRE-test cleanup completed")
    except Exception as e:
        from backend.utils.logging import get_logger
        logger = get_logger("test_cleanup")
        logger.warning("Pre-test cleanup failed", extra={"data": {"error": str(e)}})

    yield

    try:
        await cleanup_test_data()
    except Exception as e:
        from backend.utils.logging import get_logger
        logger = get_logger("test_cleanup")
        logger.warning("Post-test cleanup failed", extra={"data": {"error": str(e)}})


# Auto-use fixture for backup file cleanup
@pytest.fixture(autouse=True)
def auto_cleanup_backup_files():
    """
    Auto-cleanup fixture for backup files created during tests.

    Removes any .bak files and backup directories created during testing.
    """
    import shutil

    def cleanup_backups():
        """Remove backup files and directories created during tests."""
        try:
            backup_dirs = [
                Path("configs/backups"),
                Path("backend/agent/prompts/backups"),
                Path("backups"),
            ]

            for backup_dir in backup_dirs:
                if backup_dir.exists() and backup_dir.is_dir():
                    test_backups = list(backup_dir.glob("*test*")) + list(backup_dir.glob("*Test*"))
                    if test_backups:
                        for backup_file in test_backups:
                            if backup_file.is_file():
                                backup_file.unlink()

                    try:
                        if not any(backup_dir.iterdir()):
                            backup_dir.rmdir()
                    except OSError:
                        pass

            test_locations = [
                Path("configs"),
                Path("backend/agent/prompts"),
                Path("tests"),
                Path("."),
            ]

            for location in test_locations:
                if location.exists():
                    for bak_file in location.glob("**/*test*.bak"):
                        bak_file.unlink()
                    for bak_file in location.glob("**/*Test*.bak"):
                        bak_file.unlink()

        except Exception as e:
            print(f"Warning: Backup cleanup failed: {e}")

    cleanup_backups()
    yield
    cleanup_backups()


# Ensure asyncio tests work properly with proper cleanup
@pytest_asyncio.fixture(scope="session")
async def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()

    yield loop

    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    finally:
        loop.close()


@pytest.fixture(scope="session", autouse=True)
def disable_langsmith_tracing():
    """Disable LangSmith tracing for all tests."""
    original_tracing = os.environ.get("LANGCHAIN_TRACING_V2")
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

    yield

    if original_tracing is not None:
        os.environ["LANGCHAIN_TRACING_V2"] = original_tracing
    else:
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
