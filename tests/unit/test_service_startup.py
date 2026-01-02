"""
Service Startup & Configuration Tests

Tests environment variable overrides for configuration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSettings:
    """Environment variable configuration tests."""

    def test_environment_variable_override(self, monkeypatch):
        """Test that environment variables can override config values."""
        monkeypatch.setenv("CHAT_AGENT_PORT", "9000")
        monkeypatch.setenv("CORE_AGENT_PORT", "9001")

        from config import Settings
        
        new_settings = Settings()
        assert new_settings.CHAT_AGENT_PORT == 9000
        assert new_settings.CORE_AGENT_PORT == 9001
