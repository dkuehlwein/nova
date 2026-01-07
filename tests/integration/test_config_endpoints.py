"""
Integration tests for configuration management endpoints.

NOTE: MCP server configuration is now managed by LiteLLM (ADR-015).
These tests focus on what config_endpoints.py actually supports:
- User profile configuration (via config_registry "user_profile" manager)

MCP server validation endpoints exist but require the deprecated mcp_servers
manager which is no longer initialized by default.
"""

import pytest


class TestConfigEndpointsIntegration:
    """
    Integration tests for config endpoints.

    NOTE: The MCP server validation endpoints (/api/config/validate, /api/config/backups)
    are deprecated since MCP servers are now managed via LiteLLM (ADR-015).

    User profile endpoints would require database setup for integration testing.
    These tests are placeholders for when user profile integration tests are needed.
    """

    @pytest.mark.skip(reason="MCP server config is now managed by LiteLLM (ADR-015), not config_registry")
    @pytest.mark.asyncio
    async def test_validate_mcp_configuration_deprecated(self):
        """
        MCP server validation is deprecated.

        MCP servers are now configured via LiteLLM's mcp_servers section
        in configs/litellm_config.yaml, not through the config_registry.
        """
        pass

    @pytest.mark.skip(reason="User profile endpoints require database setup")
    @pytest.mark.asyncio
    async def test_get_user_profile(self):
        """Test GET /api/config/user-profile endpoint."""
        pass

    @pytest.mark.skip(reason="User profile endpoints require database setup")
    @pytest.mark.asyncio
    async def test_update_user_profile(self):
        """Test PUT /api/config/user-profile endpoint."""
        pass
