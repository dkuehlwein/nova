"""
Integration tests for MS Graph auto-authentication flow (NOV-123).

Tests cross-system integration between:
- MCPClientManager auth detection / retry logic
- BrowserManager persistent context management
- authenticate_ms_graph browser automation

Unlike unit tests that mock internal methods, these tests exercise real class
instances and only mock at the outermost boundary (HTTP calls to LiteLLM,
Playwright browser launch). This catches integration bugs that mock-heavy
unit tests miss -- e.g. if _parse_auth_error signature changes, or if the
retry loop passes the wrong args to _execute_mcp_call.
"""

import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_sys_modules_cache():
    """Remove browser cache entries from sys.modules after each test."""
    yield
    keys_to_remove = [k for k in sys.modules if k.startswith("_nova_browser_")]
    for key in keys_to_remove:
        del sys.modules[key]


@pytest.fixture
def mcp_manager():
    """Create a real MCPClientManager with test settings.

    Uses a real instance (not mocked) so that internal method interactions
    are tested. Only the settings are overridden.
    """
    with patch("backend.mcp_client.settings") as mock_settings:
        mock_settings.LITELLM_BASE_URL = "http://localhost:4000"
        mock_settings.LITELLM_MASTER_KEY = "test-key"
        from backend.mcp_client import MCPClientManager
        mgr = MCPClientManager()
        # Pre-populate server_id cache to avoid a real HTTP lookup
        mgr._server_id_cache = {"ms_graph": "test-uuid-ms-graph"}
        yield mgr


# -- Realistic MCP response payloads (matching real LiteLLM + MS Graph server) --

# The MS Graph MCP server returns this dict when a 401/403 is encountered.
# LiteLLM wraps it in {"content": [{"type": "text", "text": "<json>"}]}.
MS_GRAPH_AUTH_ERROR_BODY = {
    "error": (
        "MS Graph authentication required. Your token may have expired "
        "or been revoked. Please re-authenticate."
    ),
    "auth_required": True,
    "auth_url": "http://localhost:8400/auth/start",
}

MS_GRAPH_SUCCESS_BODY = {
    "value": [
        {"subject": "Meeting notes", "from": {"emailAddress": {"address": "user@example.com"}}},
    ]
}


def _litellm_response(body: dict, status_code: int = 200) -> httpx.Response:
    """Build a realistic httpx.Response as returned by LiteLLM's /mcp-rest/tools/call."""
    content_payload = {
        "content": [{"type": "text", "text": json.dumps(body)}],
        "isError": False,
    }
    return httpx.Response(
        status_code=status_code,
        json=content_payload,
        request=httpx.Request("POST", "http://localhost:4000/mcp-rest/tools/call"),
    )


def _litellm_server_list_response(servers: list) -> httpx.Response:
    """Build a response for GET /v1/mcp/server."""
    return httpx.Response(
        status_code=200,
        json=servers,
        request=httpx.Request("GET", "http://localhost:4000/v1/mcp/server"),
    )


# ---------------------------------------------------------------------------
# 1. _parse_auth_error with real MCP response structures
# ---------------------------------------------------------------------------

class TestParseAuthErrorRealFormats:
    """Test _parse_auth_error against real-format MS Graph MCP server responses.

    These use the exact response structures produced by
    mcp_servers/ms_graph/src/service.py:auth_error_response() and wrapped
    by LiteLLM's content extraction in _execute_mcp_call.

    The unit tests use simplified dicts; these use the actual format to
    catch drift between the MCP server and the client parser.
    """

    def test_parses_auth_error_from_litellm_extracted_text(self, mcp_manager):
        """After _execute_mcp_call extracts the text field, _parse_auth_error
        receives a JSON string. This is the primary production path."""
        # _execute_mcp_call extracts content[0].text, which is a JSON string
        text_payload = json.dumps(MS_GRAPH_AUTH_ERROR_BODY)
        result = mcp_manager._parse_auth_error(text_payload)
        assert result == "http://localhost:8400/auth/start"

    def test_parses_auth_error_dict_with_full_error_message(self, mcp_manager):
        """When the result is already a dict (e.g. if content extraction
        returned the parsed object), _parse_auth_error still works."""
        result = mcp_manager._parse_auth_error(MS_GRAPH_AUTH_ERROR_BODY)
        assert result == "http://localhost:8400/auth/start"

    def test_parses_auth_error_with_extra_fields(self, mcp_manager):
        """MS Graph server may include extra fields (e.g. from handle_tool_error).
        _parse_auth_error should still detect auth_required."""
        extended = {
            **MS_GRAPH_AUTH_ERROR_BODY,
            "operation": "list_emails",
            "details": "Token expired at 2026-02-16T10:00:00Z",
        }
        result = mcp_manager._parse_auth_error(extended)
        assert result == "http://localhost:8400/auth/start"

    def test_ignores_successful_email_list(self, mcp_manager):
        """A successful MS Graph response should not trigger auth."""
        result = mcp_manager._parse_auth_error(json.dumps(MS_GRAPH_SUCCESS_BODY))
        assert result is None

    def test_ignores_non_auth_error_from_mcp(self, mcp_manager):
        """A non-auth error (e.g. 404 Not Found) should not trigger auth."""
        non_auth_error = {"error": "Mailbox not found", "code": "MailboxNotFound"}
        result = mcp_manager._parse_auth_error(json.dumps(non_auth_error))
        assert result is None

    def test_handles_nested_json_string(self, mcp_manager):
        """Edge case: double-serialized JSON (has happened in production)."""
        double_encoded = json.dumps(json.dumps(MS_GRAPH_AUTH_ERROR_BODY))
        # _parse_auth_error only does one json.loads, so double-encoded should
        # result in a string that doesn't match the dict check -> returns None
        result = mcp_manager._parse_auth_error(double_encoded)
        assert result is None

    def test_auth_error_with_different_port(self, mcp_manager):
        """Auth URL may use a different port in different environments."""
        body = {
            "error": "MS Graph authentication required.",
            "auth_required": True,
            "auth_url": "http://ms-graph-mcp:9000/auth/start",
        }
        result = mcp_manager._parse_auth_error(json.dumps(body))
        assert result == "http://ms-graph-mcp:9000/auth/start"


# ---------------------------------------------------------------------------
# 2. call_mcp_tool auto-auth retry integration
# ---------------------------------------------------------------------------

class TestCallMcpToolAutoAuthRetry:
    """Integration test for the full auto-auth retry flow in call_mcp_tool.

    Uses a real MCPClientManager instance. HTTP calls to LiteLLM are mocked
    at the httpx boundary (not by patching _execute_mcp_call), so the real
    request construction, response parsing, auth detection, and retry logic
    are all exercised.
    """

    def _mock_httpx_client(self, responses: list[httpx.Response]):
        """Create a mock httpx.AsyncClient that returns responses in order.

        Each call to client.post() pops the next response. This tests the
        real _execute_mcp_call code path including header construction,
        JSON body formatting, and response content extraction.
        """
        response_iter = iter(responses)

        mock_client = AsyncMock()

        async def mock_post(*args, **kwargs):
            return next(response_iter)

        mock_client.post = AsyncMock(side_effect=mock_post)
        return mock_client

    async def test_auth_error_triggers_browser_auth_and_retries(self, mcp_manager):
        """When LiteLLM returns an auth error, call_mcp_tool should:
        1. Parse the auth error from the response
        2. Call authenticate_ms_graph with the auth URL
        3. Retry the original tool call
        4. Return the retry result
        """
        auth_error_resp = _litellm_response(MS_GRAPH_AUTH_ERROR_BODY)
        success_resp = _litellm_response(MS_GRAPH_SUCCESS_BODY)

        mock_client = self._mock_httpx_client([auth_error_resp, success_resp])

        with patch("httpx.AsyncClient") as MockClientCls:
            MockClientCls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClientCls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "utils.ms_graph_auth_browser.authenticate_ms_graph",
                new_callable=AsyncMock,
                return_value={"success": True},
            ) as mock_auth:
                result = await mcp_manager.call_mcp_tool(
                    "ms_graph", "list_emails", {"folder": "inbox"}
                )

                # Auth was called with the correct URL
                mock_auth.assert_called_once_with("http://localhost:8400/auth/start")

                # Two HTTP calls were made: initial + retry
                assert mock_client.post.call_count == 2

                # The retry result is returned (parsed from content[0].text)
                parsed_result = json.loads(result)
                assert "value" in parsed_result

    async def test_auth_failure_returns_original_auth_error(self, mcp_manager):
        """When browser auth fails, the original auth error response is returned
        (not retried)."""
        auth_error_resp = _litellm_response(MS_GRAPH_AUTH_ERROR_BODY)

        mock_client = self._mock_httpx_client([auth_error_resp])

        with patch("httpx.AsyncClient") as MockClientCls:
            MockClientCls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClientCls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "utils.ms_graph_auth_browser.authenticate_ms_graph",
                new_callable=AsyncMock,
                return_value={"success": False, "error": "MFA timed out"},
            ):
                result = await mcp_manager.call_mcp_tool(
                    "ms_graph", "list_emails", {"folder": "inbox"}
                )

                # Only one HTTP call (no retry)
                assert mock_client.post.call_count == 1

                # Returns the auth error text (as extracted by _execute_mcp_call)
                parsed_result = json.loads(result)
                assert parsed_result["auth_required"] is True

    async def test_successful_call_skips_auth(self, mcp_manager):
        """When the first call succeeds, no auth flow is triggered."""
        success_resp = _litellm_response(MS_GRAPH_SUCCESS_BODY)

        mock_client = self._mock_httpx_client([success_resp])

        with patch("httpx.AsyncClient") as MockClientCls:
            MockClientCls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClientCls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "utils.ms_graph_auth_browser.authenticate_ms_graph",
                new_callable=AsyncMock,
            ) as mock_auth:
                result = await mcp_manager.call_mcp_tool(
                    "ms_graph", "list_emails", {"folder": "inbox"}
                )

                mock_auth.assert_not_called()
                assert mock_client.post.call_count == 1

                parsed_result = json.loads(result)
                assert "value" in parsed_result

    async def test_retry_uses_same_arguments_and_server_id(self, mcp_manager):
        """The retry call must use the exact same tool name, arguments, and
        server_id as the original call."""
        auth_error_resp = _litellm_response(MS_GRAPH_AUTH_ERROR_BODY)
        success_resp = _litellm_response(MS_GRAPH_SUCCESS_BODY)

        mock_client = self._mock_httpx_client([auth_error_resp, success_resp])

        with patch("httpx.AsyncClient") as MockClientCls:
            MockClientCls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClientCls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "utils.ms_graph_auth_browser.authenticate_ms_graph",
                new_callable=AsyncMock,
                return_value={"success": True},
            ):
                await mcp_manager.call_mcp_tool(
                    "ms_graph", "send_email",
                    {"recipients": ["a@b.com"], "subject": "Hi", "body": "Hello"}
                )

                # Both calls should have the same JSON body
                first_call = mock_client.post.call_args_list[0]
                retry_call = mock_client.post.call_args_list[1]

                first_json = first_call.kwargs.get("json") or first_call[1].get("json")
                retry_json = retry_call.kwargs.get("json") or retry_call[1].get("json")

                assert first_json["name"] == "ms_graph-send_email"
                assert retry_json["name"] == "ms_graph-send_email"
                assert first_json["arguments"] == retry_json["arguments"]
                assert first_json["server_id"] == retry_json["server_id"]

    async def test_non_auth_error_does_not_trigger_auth(self, mcp_manager):
        """A non-auth error (e.g. mailbox not found) should not trigger auth."""
        non_auth_error = {"error": "Mailbox not found", "code": "MailboxNotFound"}
        error_resp = _litellm_response(non_auth_error)

        mock_client = self._mock_httpx_client([error_resp])

        with patch("httpx.AsyncClient") as MockClientCls:
            MockClientCls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClientCls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "utils.ms_graph_auth_browser.authenticate_ms_graph",
                new_callable=AsyncMock,
            ) as mock_auth:
                result = await mcp_manager.call_mcp_tool(
                    "ms_graph", "list_emails", {}
                )

                mock_auth.assert_not_called()
                assert mock_client.post.call_count == 1

    async def test_server_id_lookup_integration(self, mcp_manager):
        """When server_id is not cached, call_mcp_tool fetches it from LiteLLM
        before making the tool call."""
        # Clear the pre-populated cache
        mcp_manager._server_id_cache.clear()

        server_list_resp = _litellm_server_list_response([
            {"server_name": "ms_graph", "alias": "ms-graph", "server_id": "real-uuid-456"},
        ])
        success_resp = _litellm_response(MS_GRAPH_SUCCESS_BODY)

        # get_server_id_by_name and _execute_mcp_call each open their own
        # httpx.AsyncClient context manager, so we need a mock that returns
        # a fresh mock_client per context entry, with the right method stubs.
        def make_mock_client():
            client = AsyncMock()
            client.get = AsyncMock(return_value=server_list_resp)
            client.post = AsyncMock(return_value=success_resp)
            return client

        clients = []

        async def enter_client(*args, **kwargs):
            c = make_mock_client()
            clients.append(c)
            return c

        with patch("httpx.AsyncClient") as MockClientCls:
            MockClientCls.return_value.__aenter__ = AsyncMock(side_effect=enter_client)
            MockClientCls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mcp_manager.call_mcp_tool(
                "ms_graph", "list_emails", {"folder": "inbox"}
            )

            # server_id should now be cached
            assert mcp_manager._server_id_cache.get("ms_graph") == "real-uuid-456"

            # Two clients: one for get_server_id_by_name (GET), one for _execute_mcp_call (POST)
            assert len(clients) == 2
            # The tool call should use the resolved server_id
            post_client = clients[1]
            post_call = post_client.post.call_args
            post_json = post_call.kwargs.get("json") or post_call[1].get("json")
            assert post_json["server_id"] == "real-uuid-456"


# ---------------------------------------------------------------------------
# 3. BrowserManager persistent context management
# ---------------------------------------------------------------------------

class TestBrowserManagerPersistentContext:
    """Integration tests for BrowserManager creating and managing persistent contexts.

    Uses a real BrowserManager instance with a temp directory for the profile.
    Playwright launch is mocked at the boundary, but the cache management,
    profile directory creation, cookie operations, and lifecycle management
    use real code paths.
    """

    @pytest.fixture
    def browser_mgr(self, tmp_path):
        """Create a BrowserManager that uses tmp_path for the profile directory."""
        from utils.browser_automation import BrowserManager

        mgr = BrowserManager("integration-test")
        # Override the base cache dir to use tmp_path
        with patch("utils.browser_automation._BASE_CACHE_DIR", tmp_path):
            yield mgr

    def _make_mock_playwright(self):
        """Create mock Playwright objects that simulate a real browser lifecycle."""
        mock_context = MagicMock()
        mock_context.browser.is_connected.return_value = True
        mock_context.close = AsyncMock()
        mock_context.storage_state = AsyncMock(return_value={"cookies": []})
        mock_context.add_cookies = AsyncMock()

        mock_pw = AsyncMock()
        mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)
        mock_pw.stop = AsyncMock()

        return mock_pw, mock_context

    async def test_creates_profile_directory(self, browser_mgr, tmp_path):
        """get_or_create_context creates the profile directory on disk."""
        mock_pw, mock_context = self._make_mock_playwright()

        with patch("utils.browser_automation._BASE_CACHE_DIR", tmp_path):
            with patch("playwright.async_api.async_playwright") as mock_apm:
                mock_apm.return_value = MagicMock()
                mock_apm.return_value.start = AsyncMock(return_value=mock_pw)

                await browser_mgr.get_or_create_context(headless=True)

                # Profile directory should exist
                profile_dir = tmp_path / "integration-test-chromium-profile"
                assert profile_dir.exists()
                assert profile_dir.is_dir()

    async def test_context_cached_across_calls(self, browser_mgr, tmp_path):
        """Second call to get_or_create_context returns the cached context
        without launching a new browser."""
        mock_pw, mock_context = self._make_mock_playwright()

        with patch("utils.browser_automation._BASE_CACHE_DIR", tmp_path):
            with patch("playwright.async_api.async_playwright") as mock_apm:
                mock_apm.return_value = MagicMock()
                mock_apm.return_value.start = AsyncMock(return_value=mock_pw)

                ctx1 = await browser_mgr.get_or_create_context(headless=True)
                ctx2 = await browser_mgr.get_or_create_context(headless=True)

                assert ctx1 is ctx2
                # Playwright should only have been launched once
                mock_pw.chromium.launch_persistent_context.assert_called_once()

    async def test_dead_context_recreated(self, browser_mgr, tmp_path):
        """When the cached context's browser disconnects, a new context is created."""
        mock_pw_old, mock_context_old = self._make_mock_playwright()
        mock_pw_new, mock_context_new = self._make_mock_playwright()

        with patch("utils.browser_automation._BASE_CACHE_DIR", tmp_path):
            with patch("playwright.async_api.async_playwright") as mock_apm:
                # First call: create context
                mock_apm.return_value = MagicMock()
                mock_apm.return_value.start = AsyncMock(return_value=mock_pw_old)

                ctx1 = await browser_mgr.get_or_create_context(headless=True)
                assert ctx1 is mock_context_old

                # Simulate browser death
                mock_context_old.browser.is_connected.return_value = False

                # Second call should create a new context
                mock_apm.return_value.start = AsyncMock(return_value=mock_pw_new)

                ctx2 = await browser_mgr.get_or_create_context(headless=True)
                assert ctx2 is mock_context_new
                assert ctx2 is not ctx1

                # Old context should have been cleaned up
                mock_context_old.close.assert_called_once()
                mock_pw_old.stop.assert_called_once()

    async def test_cookie_save_and_restore_roundtrip(self, browser_mgr, tmp_path):
        """Cookies saved by one context can be restored into another."""
        from utils.browser_automation import BrowserManager

        with patch("utils.browser_automation._BASE_CACHE_DIR", tmp_path):
            cookie_path = tmp_path / "integration-test-sso-state.json"

            # Simulate saving cookies from a context
            saved_state = {
                "cookies": [
                    {"name": "session_id", "domain": ".graph.microsoft.com", "value": "abc123"},
                    {"name": "refresh_tok", "domain": ".login.microsoftonline.com", "value": "xyz"},
                    {"name": "unrelated", "domain": ".other-site.com", "value": "nope"},
                ],
            }
            cookie_path.write_text(json.dumps(saved_state))

            # Create a new manager and restore cookies (filtering out unrelated domains)
            mock_context = AsyncMock()
            cache = browser_mgr._get_cache()
            cache.context = mock_context

            restored = await browser_mgr.restore_cookies(
                exclude_domains=["other-site.com"],
                state_path=cookie_path,
            )
            assert restored is True

            # Only MS-related cookies should have been added
            added_cookies = mock_context.add_cookies.call_args[0][0]
            assert len(added_cookies) == 2
            domains = {c["domain"] for c in added_cookies}
            assert ".other-site.com" not in domains

    async def test_close_cleans_up_and_allows_recreation(self, browser_mgr, tmp_path):
        """After close(), a subsequent get_or_create_context creates a fresh context."""
        mock_pw1, mock_ctx1 = self._make_mock_playwright()
        mock_pw2, mock_ctx2 = self._make_mock_playwright()

        with patch("utils.browser_automation._BASE_CACHE_DIR", tmp_path):
            with patch("playwright.async_api.async_playwright") as mock_apm:
                # Create first context
                mock_apm.return_value = MagicMock()
                mock_apm.return_value.start = AsyncMock(return_value=mock_pw1)

                ctx1 = await browser_mgr.get_or_create_context(headless=True)
                assert ctx1 is mock_ctx1

                # Close it
                await browser_mgr.close()
                mock_ctx1.close.assert_called_once()
                mock_pw1.stop.assert_called_once()

                # Cache should be cleared
                cache = browser_mgr._get_cache()
                assert cache.context is None
                assert cache.playwright_obj is None

                # Create again - should launch a new browser
                mock_apm.return_value.start = AsyncMock(return_value=mock_pw2)
                ctx2 = await browser_mgr.get_or_create_context(headless=True)
                assert ctx2 is mock_ctx2
                assert ctx2 is not ctx1

    async def test_namespace_isolation(self, tmp_path):
        """Two BrowserManagers with different namespaces have separate caches."""
        from utils.browser_automation import BrowserManager

        mgr_a = BrowserManager("ms-graph")
        mgr_b = BrowserManager("lam-flow")

        with patch("utils.browser_automation._BASE_CACHE_DIR", tmp_path):
            # Set up context in mgr_a
            mock_ctx_a = MagicMock()
            mock_ctx_a.browser.is_connected.return_value = True
            cache_a = mgr_a._get_cache()
            cache_a.context = mock_ctx_a

            # mgr_b should have its own empty cache
            cache_b = mgr_b._get_cache()
            assert cache_b.context is None
            assert cache_a.context is mock_ctx_a

    async def test_corrupt_profile_retry(self, browser_mgr, tmp_path):
        """If the persistent context launch fails (corrupt profile), BrowserManager
        wipes the profile directory and retries."""
        mock_pw = AsyncMock()
        mock_context = MagicMock()
        mock_context.browser.is_connected.return_value = True

        # First launch fails, second succeeds (after profile wipe)
        mock_pw.chromium.launch_persistent_context = AsyncMock(
            side_effect=[RuntimeError("profile corrupt"), mock_context]
        )
        mock_pw.stop = AsyncMock()

        with patch("utils.browser_automation._BASE_CACHE_DIR", tmp_path):
            with patch("playwright.async_api.async_playwright") as mock_apm:
                mock_apm.return_value = MagicMock()
                mock_apm.return_value.start = AsyncMock(return_value=mock_pw)

                ctx = await browser_mgr.get_or_create_context(headless=True)

                assert ctx is mock_context
                # launch_persistent_context called twice (fail + retry)
                assert mock_pw.chromium.launch_persistent_context.call_count == 2
