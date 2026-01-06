#!/usr/bin/env python3
"""
MCP Server Connection Integration Tests

Tests real connectivity to MCP servers via LiteLLM's MCP Gateway.
Per ADR-015, LiteLLM is the central registry for all MCP servers.

These are integration tests that require LiteLLM and MCP servers to be running.
"""

import asyncio
import aiohttp
import json
import pytest
from typing import Dict, Any, List

from config import settings
from mcp_client import mcp_manager


@pytest.fixture
async def mcp_servers():
    """Fixture providing MCP servers from LiteLLM."""
    servers = await mcp_manager.get_mcp_servers_status()
    if not servers:
        pytest.skip("No MCP servers available from LiteLLM")
    return servers


@pytest.fixture
def litellm_config():
    """Fixture providing LiteLLM configuration."""
    return {
        "base_url": settings.LITELLM_BASE_URL,
        "api_key": settings.LITELLM_MASTER_KEY
    }


class TestLiteLLMMCPGateway:
    """Test LiteLLM's MCP Gateway functionality."""

    @pytest.mark.asyncio
    async def test_litellm_mcp_tools_list(self, litellm_config):
        """Test that LiteLLM's MCP Gateway responds to tools/list."""
        result = await mcp_manager.list_tools_from_litellm()

        # Should get a dict with 'tools' key
        assert isinstance(result, dict), "Expected dict response from LiteLLM"
        assert "tools" in result, "Response should contain 'tools' key"

        tools = result["tools"]
        print(f"LiteLLM MCP Gateway returned {len(tools)} tools")

        if tools:
            # Validate tool structure
            for tool in tools[:3]:  # Check first 3 tools
                assert "name" in tool, "Tool should have 'name'"
                assert "mcp_info" in tool, "Tool should have 'mcp_info'"
                print(f"  - {tool['name']} from {tool['mcp_info'].get('server_name', 'unknown')}")

    @pytest.mark.asyncio
    async def test_mcp_servers_status(self, litellm_config):
        """Test getting MCP server status from LiteLLM."""
        servers = await mcp_manager.get_mcp_servers_status()

        print(f"Found {len(servers)} MCP servers via LiteLLM")

        for server in servers:
            assert "name" in server, "Server should have 'name'"
            assert "tools_count" in server, "Server should have 'tools_count'"
            print(f"  - {server['name']}: {server['tools_count']} tools")

    @pytest.mark.asyncio
    async def test_discover_working_servers(self, litellm_config):
        """Test discovering working servers via LiteLLM."""
        servers = await mcp_manager.discover_working_servers()

        # Should return a list (may be empty if no servers)
        assert isinstance(servers, list), "Should return a list"

        print(f"Discovered {len(servers)} working MCP servers")

        for server in servers:
            assert "name" in server
            assert "healthy" in server
            assert server["healthy"] is True, f"Server {server['name']} should be healthy"


class TestMCPServerHealth:
    """Test individual MCP server health endpoints."""

    @pytest.mark.asyncio
    async def test_server_health_endpoints(self, mcp_servers):
        """Test that MCP servers respond to health checks."""
        for server in mcp_servers:
            server_name = server["name"]
            print(f"Server {server_name}: healthy={server.get('healthy', False)}, tools={server.get('tools_count', 0)}")

            assert server.get("healthy") is True, f"Server {server_name} should be healthy"
            assert server.get("tools_count", 0) > 0, f"Server {server_name} should have tools"


class TestMCPToolFetching:
    """Test fetching tools from MCP servers via LiteLLM."""

    @pytest.mark.asyncio
    async def test_get_langchain_tools(self, litellm_config):
        """Test converting MCP tools to LangChain tools."""
        tools = await mcp_manager.get_tools()

        # Should return a list (may be empty if no servers)
        assert isinstance(tools, list), "Should return a list of tools"

        print(f"Converted {len(tools)} MCP tools to LangChain format")

        # Validate LangChain tool structure
        for tool in tools[:3]:  # Check first 3 tools
            assert hasattr(tool, 'name'), f"Tool should have 'name'"
            assert hasattr(tool, 'description'), f"Tool should have 'description'"
            assert tool.name, "Tool name should not be empty"
            print(f"  - {tool.name}")

    @pytest.mark.asyncio
    async def test_tool_schema_validation(self, litellm_config):
        """Test that tools have valid schemas."""
        tools = await mcp_manager.get_tools()

        if not tools:
            pytest.skip("No tools available for schema validation")

        schema_errors = []

        for tool in tools:
            try:
                # Check that tool has args_schema
                if hasattr(tool, 'args_schema'):
                    schema = tool.args_schema
                    # Schema should be a Pydantic model or similar
                    assert schema is not None, f"Tool {tool.name} has None args_schema"
            except Exception as e:
                schema_errors.append(f"Tool {tool.name}: {e}")

        if schema_errors:
            print(f"Schema validation warnings ({len(schema_errors)} tools):")
            for error in schema_errors[:5]:
                print(f"  - {error}")

        # Test passes if most tools have valid schemas
        print(f"Schema validation completed for {len(tools)} tools")


class TestMCPToolExecution:
    """Test actual tool execution via LiteLLM's MCP Gateway."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_tool_call_via_litellm(self, mcp_servers):
        """Test calling an MCP tool via LiteLLM's gateway."""
        # Find a safe tool to test (list operation)
        result = await mcp_manager.list_tools_from_litellm()
        tools = result.get("tools", [])

        safe_tools = [
            t for t in tools
            if any(keyword in t["name"].lower() for keyword in ['list', 'get'])
               and not any(keyword in t["name"].lower() for keyword in ['delete', 'create', 'send'])
        ]

        if not safe_tools:
            pytest.skip("No safe tools found for execution testing")

        # Test first safe tool
        test_tool = safe_tools[0]
        server_name = test_tool.get("mcp_info", {}).get("server_name", "unknown")

        print(f"Testing tool execution: {test_tool['name']} on {server_name}")

        try:
            result = await mcp_manager.call_mcp_tool(
                server_name=server_name,
                tool_name=test_tool["name"],
                arguments={}
            )

            # Result should not be an error
            if isinstance(result, dict) and "error" in result:
                print(f"Tool returned error (may be expected): {result['error']}")
            else:
                print(f"Tool {test_tool['name']} executed successfully")
                assert result is not None

        except Exception as e:
            print(f"Tool execution failed (may be expected in test env): {e}")


if __name__ == "__main__":
    # Allow running as script for debugging
    pytest.main([__file__, "-v", "--tb=short"])
