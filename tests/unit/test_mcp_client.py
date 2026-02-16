"""
MCP Client Unit Tests

Tests for the MCPClientManager class that interfaces with LiteLLM's MCP Gateway.

Key behavior tested:
- Tool names sent to LiteLLM must be prefixed with server_name
  (LiteLLM uses tool name, not server_id, for routing to the correct MCP server)
- get_tools() creates LangChain tools that call call_mcp_tool with prefixed names
- Auth error detection and auto-retry via Playwright (NOV-123)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.mcp_client import MCPClientManager, get_prefixed_tool_name


@pytest.fixture
def manager():
    """Create an MCPClientManager with mocked settings and pre-populated server cache."""
    with patch("backend.mcp_client.settings") as mock_settings:
        mock_settings.LITELLM_BASE_URL = "http://localhost:4000"
        mock_settings.LITELLM_MASTER_KEY = "test-key"
        mgr = MCPClientManager()
        mgr._server_id_cache = {"ms_graph": "fake-uuid-123"}
        yield mgr


def _make_mcp_response(text: str = '{"status": "success"}') -> MagicMock:
    """Create a mock HTTP response matching LiteLLM's MCP response format."""
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "content": [{"type": "text", "text": text}],
        "isError": False,
    }
    return response


def _extract_request_json(mock_client: AsyncMock) -> dict:
    """Extract the JSON body from a mock httpx client's post call."""
    call_kwargs = mock_client.post.call_args
    return call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")


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

    @pytest.mark.asyncio
    async def test_call_mcp_tool_sends_prefixed_name(self, manager):
        """call_mcp_tool must send the prefixed tool name to LiteLLM (NOV-115)."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_mcp_response()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await manager.call_mcp_tool(
                server_name="ms_graph",
                tool_name="send_email",
                arguments={"recipients": ["test@example.com"], "subject": "Test", "body": "Hello"},
            )

            request_json = _extract_request_json(mock_client)
            assert request_json["name"] == "ms_graph-send_email"

    @pytest.mark.asyncio
    async def test_call_mcp_tool_prefixes_for_different_servers(self, manager):
        """Verify prefixing works for various server names, not just ms_graph."""
        manager._server_id_cache["google_workspace"] = "gw-uuid-456"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_mcp_response()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await manager.call_mcp_tool(
                server_name="google_workspace",
                tool_name="send_email",
                arguments={"recipients": ["test@example.com"], "subject": "Test", "body": "Hello"},
            )

            request_json = _extract_request_json(mock_client)
            assert request_json["name"] == "google_workspace-send_email"


class TestGetToolsEndToEnd:
    """Test that get_tools() creates LangChain tools that produce prefixed HTTP requests."""

    @pytest.mark.asyncio
    async def test_tool_invocation_sends_prefixed_name_to_litellm(self, manager):
        """End-to-end: LangChain tool invocation must send prefixed name in HTTP request."""
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
                    "required": ["recipients", "subject", "body"],
                },
                "mcp_info": {"server_name": "ms_graph"},
            }],
        })

        tools = await manager.get_tools(force_refresh=True)
        assert len(tools) == 1
        assert tools[0].name == "ms_graph-send_email"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_mcp_response()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await tools[0].ainvoke({
                "recipients": ["test@example.com"],
                "subject": "Test",
                "body": "Hello",
            })

            request_json = _extract_request_json(mock_client)
            assert request_json["name"] == "ms_graph-send_email"


class TestParseAuthError:
    """Test _parse_auth_error detection of MS Graph auth errors (NOV-123)."""

    _AUTH_RESPONSE = {
        "error": "MS Graph authentication required.",
        "auth_required": True,
        "auth_url": "http://localhost:8400/auth/start",
    }

    def test_detects_auth_required_dict(self, manager):
        assert manager._parse_auth_error(self._AUTH_RESPONSE) == "http://localhost:8400/auth/start"

    def test_detects_auth_required_json_string(self, manager):
        assert manager._parse_auth_error(json.dumps(self._AUTH_RESPONSE)) == "http://localhost:8400/auth/start"

    def test_ignores_non_auth_error(self, manager):
        assert manager._parse_auth_error({"error": "Some other error"}) is None

    def test_ignores_success_response(self, manager):
        assert manager._parse_auth_error({"status": "success", "data": [1, 2, 3]}) is None

    def test_ignores_plain_string(self, manager):
        assert manager._parse_auth_error("Hello world") is None

    def test_ignores_non_json_string(self, manager):
        assert manager._parse_auth_error("not json {") is None

    def test_ignores_auth_required_false(self, manager):
        assert manager._parse_auth_error({"auth_required": False, "auth_url": "http://localhost:8400/auth/start"}) is None


class TestAutoAuthRetry:
    """Test call_mcp_tool auto-auth and retry behavior (NOV-123)."""

    _AUTH_ERROR = json.dumps({
        "error": "MS Graph authentication required.",
        "auth_required": True,
        "auth_url": "http://localhost:8400/auth/start",
    })

    @pytest.mark.asyncio
    async def test_auto_auth_and_retry_on_auth_error(self, manager):
        """When tool returns auth_required, auto-auth and retry."""
        success_response = json.dumps({"status": "success", "data": "emails"})
        manager._execute_mcp_call = AsyncMock(
            side_effect=[self._AUTH_ERROR, success_response]
        )

        with patch(
            "utils.ms_graph_auth_browser.authenticate_ms_graph",
            new_callable=AsyncMock,
            return_value={"success": True},
        ) as mock_auth:
            result = await manager.call_mcp_tool("ms_graph", "list_emails", {"folder": "inbox"})

            mock_auth.assert_called_once_with("http://localhost:8400/auth/start")
            assert manager._execute_mcp_call.call_count == 2
            assert result == success_response

    @pytest.mark.asyncio
    async def test_returns_original_error_when_auth_fails(self, manager):
        """When auto-auth fails, return the original auth error."""
        manager._execute_mcp_call = AsyncMock(return_value=self._AUTH_ERROR)

        with patch(
            "utils.ms_graph_auth_browser.authenticate_ms_graph",
            new_callable=AsyncMock,
            return_value={"success": False, "error": "MFA timeout"},
        ):
            result = await manager.call_mcp_tool("ms_graph", "list_emails", {})

            assert result == self._AUTH_ERROR
            assert manager._execute_mcp_call.call_count == 1

    @pytest.mark.asyncio
    async def test_no_auth_on_success(self, manager):
        """Successful tool calls should not trigger auto-auth."""
        success_response = json.dumps({"status": "success"})
        manager._execute_mcp_call = AsyncMock(return_value=success_response)

        with patch(
            "utils.ms_graph_auth_browser.authenticate_ms_graph",
            new_callable=AsyncMock,
        ) as mock_auth:
            result = await manager.call_mcp_tool("ms_graph", "list_emails", {})

            mock_auth.assert_not_called()
            assert result == success_response

    @pytest.mark.asyncio
    async def test_no_auth_on_non_auth_error(self, manager):
        """Non-auth errors should not trigger auto-auth."""
        error_response = {"error": "Internal server error"}
        manager._execute_mcp_call = AsyncMock(return_value=error_response)

        with patch(
            "utils.ms_graph_auth_browser.authenticate_ms_graph",
            new_callable=AsyncMock,
        ) as mock_auth:
            result = await manager.call_mcp_tool("ms_graph", "list_emails", {})

            mock_auth.assert_not_called()
            assert result == error_response
