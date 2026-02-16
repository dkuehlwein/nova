"""
Unit tests for MS Graph auto-auth browser module (NOV-123).

Tests the authenticate_ms_graph flow with mocked Playwright interactions.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


@pytest.fixture(autouse=True)
def clean_sys_modules_cache():
    """Remove browser cache entries from sys.modules after each test."""
    yield
    keys_to_remove = [k for k in sys.modules if k.startswith("_nova_browser_")]
    for key in keys_to_remove:
        del sys.modules[key]


def _make_mock_page(content_text: str = "", url: str = "http://localhost:8400/auth/start"):
    """Create a mock Playwright page with configurable content."""
    page = AsyncMock()
    page.url = url
    page.content = AsyncMock(return_value=f"<html><body>{content_text}</body></html>")
    page.query_selector = AsyncMock(return_value=None)
    page.close = AsyncMock()
    return page


class TestAuthenticateMsGraph:
    """Tests for authenticate_ms_graph function."""

    async def test_already_authenticated(self):
        """If the auth page shows 'Already Authenticated', return success immediately."""
        from utils.ms_graph_auth_browser import authenticate_ms_graph

        mock_page = _make_mock_page("Already Authenticated")
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch(
            "utils.ms_graph_auth_browser._browser_manager"
        ) as mock_mgr:
            mock_mgr.get_or_create_context = AsyncMock(return_value=mock_context)
            mock_mgr.save_cookies = AsyncMock()

            result = await authenticate_ms_graph("http://localhost:8400/auth/start")

            assert result["success"] is True

    async def test_sign_in_button_clicked(self):
        """If a 'Sign in with Microsoft' link is found, click it."""
        from utils.ms_graph_auth_browser import authenticate_ms_graph

        mock_link = AsyncMock()
        mock_page = _make_mock_page("Sign in to Microsoft 365")
        mock_page.query_selector = AsyncMock(return_value=mock_link)
        # After clicking, the wait_for_function should find success text
        mock_page.wait_for_function = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch(
            "utils.ms_graph_auth_browser._browser_manager"
        ) as mock_mgr:
            mock_mgr.get_or_create_context = AsyncMock(return_value=mock_context)
            mock_mgr.save_cookies = AsyncMock()

            result = await authenticate_ms_graph("http://localhost:8400/auth/start")

            assert result["success"] is True
            mock_link.click.assert_called_once()
            mock_mgr.save_cookies.assert_called_once()

    async def test_timeout_returns_error(self):
        """If the OAuth flow times out, return an error."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        from utils.ms_graph_auth_browser import authenticate_ms_graph

        mock_page = _make_mock_page("Sign in page content")
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.wait_for_function = AsyncMock(
            side_effect=PlaywrightTimeout("timeout")
        )
        # After timeout, check for error page - page content doesn't have "error"
        mock_page.content = AsyncMock(
            return_value="<html><body>Sign in page content</body></html>"
        )

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch(
            "utils.ms_graph_auth_browser._browser_manager"
        ) as mock_mgr:
            mock_mgr.get_or_create_context = AsyncMock(return_value=mock_context)

            result = await authenticate_ms_graph(
                "http://localhost:8400/auth/start", mfa_timeout_ms=1000
            )

            assert result["success"] is False
            assert "timed out" in result["error"].lower()

    async def test_playwright_not_installed(self):
        """If Playwright is not installed, return a clear error."""
        import utils.ms_graph_auth_browser as mod

        async def mock_auth(auth_url, **kwargs):
            return {
                "success": False,
                "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            }

        with patch.object(mod, "authenticate_ms_graph", mock_auth):
            result = await mod.authenticate_ms_graph(
                "http://localhost:8400/auth/start"
            )
            assert result["success"] is False
            assert "playwright" in result["error"].lower()

    async def test_page_closed_in_finally(self):
        """Page is always closed, even on success."""
        from utils.ms_graph_auth_browser import authenticate_ms_graph

        mock_page = _make_mock_page("Already Authenticated")
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch(
            "utils.ms_graph_auth_browser._browser_manager"
        ) as mock_mgr:
            mock_mgr.get_or_create_context = AsyncMock(return_value=mock_context)
            mock_mgr.save_cookies = AsyncMock()

            await authenticate_ms_graph("http://localhost:8400/auth/start")

            mock_page.close.assert_called_once()

    async def test_exception_returns_error(self):
        """General exceptions are caught and returned as errors."""
        from utils.ms_graph_auth_browser import authenticate_ms_graph

        with patch(
            "utils.ms_graph_auth_browser._browser_manager"
        ) as mock_mgr:
            mock_mgr.get_or_create_context = AsyncMock(
                side_effect=RuntimeError("browser failed")
            )

            result = await authenticate_ms_graph("http://localhost:8400/auth/start")

            assert result["success"] is False
            assert "browser failed" in result["error"]
