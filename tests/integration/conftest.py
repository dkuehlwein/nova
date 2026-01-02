"""
Pytest configuration for integration tests.

Integration tests test interactions between multiple services/components.
They require PostgreSQL, Redis, and often MCP servers running.

Inherits all fixtures from component tests.
"""

# Import all fixtures from component conftest
from tests.component.conftest import *
