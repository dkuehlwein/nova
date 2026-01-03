"""
Pytest configuration for integration tests.

Integration tests test interactions between multiple services/components.
They require PostgreSQL, Redis, and often MCP servers running.
"""

import pytest
# Note: component tests directory doesn't exist yet
# If/when created, can import fixtures from there

