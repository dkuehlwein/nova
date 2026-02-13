"""
MCP Client Unit Tests

Tests for the MCPClientManager class that interfaces with LiteLLM's MCP Gateway.

Key behavior tested:
- Tool names sent to LiteLLM must be prefixed with server_name
  (LiteLLM uses tool name, not server_id, for routing to the correct MCP server)
- get_tools() creates LangChain tools that call call_mcp_tool with prefixed names
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from backend.mcp_client import MCPClientManager, get_prefixed_tool_name


class TestGetPrefixedToolName:
    """Test the get_prefixed_tool_name utility function."""

    def test_basic_prefix(self):
        assert get_prefixed_tool_name("ms_graph", "send_email") == "ms_graph-send_email"

    def test_prefix_with_underscores(self):
        assert get_prefixed_tool_name("google_workspace", "list_emails") == "google_workspace-list_emails"

    def test_prefix_with_hyphen_server(self):
        assert get_prefixed_tool_name("outlook-mac", "read_email") == "outlook-mac-read_email"


class TestCallMcpToolPrefixing:
    """Test that call_mcp_tool sends prefixed tool names to LiteLLM.

    LiteLLM routes tool calls using the tool name (not server_id).
    When multiple servers register tools with the same base name (e.g., send_email),
    LiteLLM's last-write-wins mapping routes to the wrong server unless
    the prefixed name (e.g., ms_graph-send_email) is used.
    """

    @pytest.fixture
    def manager(self):
        """Create an MCPClientManager with mocked settings."""
        with patch("backend.mcp_client.settings") as mock_settings:
            mock_settings.LITELLM_BASE_URL = "http://localhost:4000"
            mock_settings.LITELLM_MASTER_KEY = "test-key"
            mgr = MCPClientManager()
            # Pre-populate server_id cache to skip the lookup call
            mgr._server_id_cache = {"ms_graph": "fake-uuid-123"}
            return mgr

    @pytest.mark.asyncio
    async def test_call_mcp_tool_sends_prefixed_name(self, manager):
        """
        call_mcp_tool must send the prefixed tool name (server_name-tool_name)
        to LiteLLM's /mcp-rest/tools/call endpoint.

        This is the core fix for NOV-115: unprefixed names cause LiteLLM to
        route to the wrong MCP server when multiple servers have same-named tools.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": '{"status": "success"}'}],
            "isError": False
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await manager.call_mcp_tool(
                server_name="ms_graph",
                tool_name="send_email",
                arguments={"recipients": ["test@example.com"], "subject": "Test", "body": "Hello"}
            )

            # Verify the POST call was made with the PREFIXED tool name
            mock_client_instance.post.assert_called_once()
            call_kwargs = mock_client_instance.post.call_args
            request_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")

            assert request_json["name"] == "ms_graph-send_email", (
                f"Expected prefixed tool name 'ms_graph-send_email' in request to LiteLLM, "
                f"but got '{request_json['name']}'. LiteLLM uses tool name (not server_id) "
                f"for routing, so unprefixed names cause routing collisions."
            )

    @pytest.mark.asyncio
    async def test_call_mcp_tool_prefixes_for_different_servers(self, manager):
        """
        Verify prefixing works for various server names, not just ms_graph.
        """
        manager._server_id_cache["google_workspace"] = "gw-uuid-456"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": '{"status": "success"}'}],
            "isError": False
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await manager.call_mcp_tool(
                server_name="google_workspace",
                tool_name="send_email",
                arguments={"recipients": ["test@example.com"], "subject": "Test", "body": "Hello"}
            )

            call_kwargs = mock_client_instance.post.call_args
            request_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")

            assert request_json["name"] == "google_workspace-send_email", (
                f"Expected 'google_workspace-send_email' but got '{request_json['name']}'"
            )


class TestGetToolsEndToEnd:
    """Test that get_tools() creates LangChain tools that produce prefixed HTTP requests."""

    @pytest.fixture
    def manager(self):
        """Create an MCPClientManager with mocked settings."""
        with patch("backend.mcp_client.settings") as mock_settings:
            mock_settings.LITELLM_BASE_URL = "http://localhost:4000"
            mock_settings.LITELLM_MASTER_KEY = "test-key"
            mgr = MCPClientManager()
            # Pre-populate server_id cache
            mgr._server_id_cache = {"ms_graph": "fake-uuid-123"}
            return mgr

    @pytest.mark.asyncio
    async def test_tool_invocation_sends_prefixed_name_to_litellm(self, manager):
        """
        End-to-end: when a LangChain tool from get_tools() is invoked,
        the HTTP request to LiteLLM must contain the prefixed tool name.

        This verifies the full chain: get_tools() -> LangChain tool -> call_mcp_tool -> HTTP POST.
        """
        # Mock list_tools_from_litellm to return a single tool
        manager.list_tools_from_litellm = AsyncMock(return_value={
            "tools": [{
                "name": "send_email",
                "description": "Send an email",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "recipients": {"type": "array"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["recipients", "subject", "body"]
                },
                "mcp_info": {"server_name": "ms_graph"}
            }]
        })

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": '{"status": "success"}'}],
            "isError": False
        }

        tools = await manager.get_tools(force_refresh=True)
        assert len(tools) == 1
        assert tools[0].name == "ms_graph-send_email"

        # Now invoke the tool, mocking the HTTP layer
        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await tools[0].ainvoke({
                "recipients": ["test@example.com"],
                "subject": "Test",
                "body": "Hello"
            })

            # Verify the HTTP POST to LiteLLM contains the prefixed name
            mock_client_instance.post.assert_called_once()
            call_kwargs = mock_client_instance.post.call_args
            request_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")

            assert request_json["name"] == "ms_graph-send_email", (
                f"Expected prefixed tool name 'ms_graph-send_email' in HTTP request "
                f"to LiteLLM, but got '{request_json['name']}'. The full chain from "
                f"LangChain tool invocation through to the HTTP request must use "
                f"prefixed names for correct LiteLLM routing."
            )
