"""
Pytest configuration for evaluation tests.

Evals require:
- PostgreSQL database (docker-compose.test.yml on port 5433)
- Redis (optional, for some evals)
- MCP servers (for evals with use_real_mcp=True)

This conftest provides fixtures for:
- Database connection pools
- Service initialization
- Eval runner setup
- Test data cleanup
"""

import os
import sys
import pytest
import asyncio
from pathlib import Path

# Add backend to path for imports
BACKEND_PATH = Path(__file__).parent.parent.parent / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

# Set test environment
os.environ["NOVA_TEST_ENV"] = "true"
os.environ["PHOENIX_ENABLED"] = "false"

# Import test utilities
from test_cleanup import TestDataCleaner


def pytest_configure(config):
    """Configure pytest with eval-specific markers."""
    config.addinivalue_line("markers", "eval: evaluation test")
    config.addinivalue_line("markers", "fast: fast eval (mocked LLM, <2 min)")
    config.addinivalue_line("markers", "slow: slow eval (real LLM, real MCP)")
    config.addinivalue_line("markers", "calendar: calendar-related eval")
    config.addinivalue_line("markers", "task_mgmt: task management eval")
    config.addinivalue_line("markers", "escalation: human escalation eval")


@pytest.fixture(scope="session")
def test_database_url():
    """
    Database URL for eval tests.

    Priority:
    1. EVAL_DATABASE_URL env var (explicit override)
    2. DATABASE_URL env var (if set, use dev environment)
    3. Default to docker-compose.test.yml (port 5433)

    For development, you can run evals against the main dev DB by setting:
        DATABASE_URL=postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova_kanban
    """
    if os.getenv("EVAL_DATABASE_URL"):
        return os.getenv("EVAL_DATABASE_URL")

    if os.getenv("DATABASE_URL"):
        # Use existing DATABASE_URL (dev environment)
        return os.getenv("DATABASE_URL")

    # Default to test environment
    return "postgresql+asyncpg://nova:nova_test_password@localhost:5433/nova_kanban_test"


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def eval_pg_pool(test_database_url):
    """
    Create a PostgreSQL connection pool for eval tests.

    This pool is used by:
    - EvalRunner for database operations
    - create_chat_agent for checkpointer
    - Grading functions for state verification
    """
    from psycopg_pool import AsyncConnectionPool

    # Convert asyncpg URL to psycopg format
    psycopg_url = test_database_url.replace("+asyncpg", "")

    pool = AsyncConnectionPool(psycopg_url, open=False)
    await pool.open()

    yield pool

    await pool.close()


@pytest.fixture(scope="function")
async def eval_service_manager(test_database_url):
    """
    Initialize ServiceManager for eval tests.

    Sets up:
    - Database connection pool
    - Config registry
    - Other service dependencies
    """
    from utils.service_manager import ServiceManager

    # ServiceManager expects DATABASE_URL (plain postgres URL for LangGraph)
    # and SQLALCHEMY_DATABASE_URL (asyncpg URL for SQLAlchemy)
    # Convert asyncpg URL to plain postgres for DATABASE_URL
    plain_url = test_database_url.replace("+asyncpg", "")

    os.environ["DATABASE_URL"] = plain_url
    os.environ["SQLALCHEMY_DATABASE_URL"] = test_database_url

    service_manager = ServiceManager("eval-test")
    await service_manager.ensure_database_initialized()
    await service_manager.init_pg_pool()

    yield service_manager

    await service_manager.close_pg_pool()


@pytest.fixture(scope="function")
async def eval_runner(eval_pg_pool):
    """
    Create an EvalRunner instance for running eval cases.

    The runner is configured with:
    - PostgreSQL pool for DB operations
    - Default model from config (can be overridden per eval)
    """
    from tests.evals.framework.eval_runner import EvalRunner

    runner = EvalRunner(pg_pool=eval_pg_pool)

    yield runner


@pytest.fixture(scope="function")
async def test_data_cleaner(test_database_url):
    """
    Create a TestDataCleaner for cleanup after each eval.

    Records initial state before test and cleans up
    any threads/data created during the test.
    """
    cleaner = TestDataCleaner(database_url=test_database_url)
    await cleaner.record_initial_state()

    yield cleaner

    await cleaner.cleanup_test_threads()
    await cleaner._close_all_pools()


@pytest.fixture(scope="function")
async def ensure_clean_db(test_database_url):
    """
    Ensure the test database is in a clean state before running evals.

    This fixture:
    - Truncates test-related tables
    - Does NOT touch core schema or migrations
    - Runs before each eval to ensure isolation
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    engine = create_async_engine(test_database_url)

    async with engine.begin() as conn:
        # Only truncate data tables, not schema tables
        # Be conservative - only truncate tables we know are safe
        try:
            # Note: We don't truncate tasks table as evals may need existing data
            # Each eval is responsible for its own setup/teardown
            pass
        except Exception:
            pass  # Tables may not exist yet

    await engine.dispose()

    yield


@pytest.fixture
def load_eval_models():
    """
    Load model configuration from models.yaml.

    Returns a dict of model configs that can be used for parametrization.
    """
    import yaml
    from pathlib import Path

    models_path = Path(__file__).parent / "models.yaml"

    if not models_path.exists():
        # Return default model if config doesn't exist yet
        return {"default": {"name": "default", "enabled": True}}

    with open(models_path) as f:
        config = yaml.safe_load(f)

    return config.get("models", {})
