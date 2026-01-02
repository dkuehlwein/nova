"""
Root pytest configuration for Nova tests.

This file provides shared utilities and path setup for all test types.
NO autouse fixtures here - each test type directory has its own conftest
with appropriate fixtures for that isolation level.

Test Types:
- unit/: Isolated tests, no services required
- component/: Single component tests, require DB/Redis
- integration/: Multi-service workflow tests
- end2end/: Full Docker stack tests
"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path so that 'backend' package can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BACKEND_PATH = PROJECT_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

# Disable LangSmith tracing for tests to avoid noise and gRPC connection issues
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_API_KEY"] = ""
os.environ["LANGCHAIN_PROJECT"] = ""

# Import test cleanup utilities (available to all test types)
from test_cleanup import TestDataCleaner


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "unit: unit tests (isolated, no services)")
    config.addinivalue_line("markers", "component: component tests (need DB/Redis)")
    config.addinivalue_line("markers", "integration: integration tests (multi-service)")
    config.addinivalue_line("markers", "e2e: end-to-end tests (full Docker stack)")
    config.addinivalue_line("markers", "slow: marks tests as slow")
