"""
Unit tests for the shared browser automation utility (NOV-123).

Tests BrowserManager context creation/caching, cookie save/restore,
and namespace isolation. All Playwright calls are mocked.
"""

import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


@pytest.fixture
def browser_manager():
    """Create a BrowserManager instance for testing."""
    from utils.browser_automation import BrowserManager

    return BrowserManager("test-namespace")


@pytest.fixture(autouse=True)
def clean_sys_modules_cache():
    """Remove any browser cache entries from sys.modules after each test."""
    yield
    keys_to_remove = [k for k in sys.modules if k.startswith("_nova_browser_")]
    for key in keys_to_remove:
        del sys.modules[key]


class TestBrowserManagerInit:
    """BrowserManager initialization and properties."""

    def test_namespace_stored(self, browser_manager):
        assert browser_manager.namespace == "test-namespace"

    def test_profile_dir_uses_namespace(self, browser_manager):
        expected = Path.home() / ".cache" / "nova" / "test-namespace-chromium-profile"
        assert browser_manager.profile_dir == expected

    def test_cookie_storage_path_uses_namespace(self, browser_manager):
        expected = Path.home() / ".cache" / "nova" / "test-namespace-sso-state.json"
        assert browser_manager.cookie_storage_path == expected

    def test_different_namespaces_different_paths(self):
        from utils.browser_automation import BrowserManager

        mgr_a = BrowserManager("alpha")
        mgr_b = BrowserManager("beta")
        assert mgr_a.profile_dir != mgr_b.profile_dir
        assert mgr_a.cookie_storage_path != mgr_b.cookie_storage_path


class TestBrowserManagerCache:
    """Process-level cache via sys.modules."""

    def test_cache_created_in_sys_modules(self, browser_manager):
        cache = browser_manager._get_cache()
        assert cache is not None
        assert cache.playwright_obj is None
        assert cache.context is None

    def test_cache_survives_repeated_access(self, browser_manager):
        cache1 = browser_manager._get_cache()
        cache1.playwright_obj = "sentinel"
        cache2 = browser_manager._get_cache()
        assert cache2.playwright_obj == "sentinel"

    def test_different_namespaces_different_caches(self):
        from utils.browser_automation import BrowserManager

        mgr_a = BrowserManager("ns-a")
        mgr_b = BrowserManager("ns-b")
        cache_a = mgr_a._get_cache()
        cache_b = mgr_b._get_cache()
        cache_a.playwright_obj = "alpha"
        assert cache_b.playwright_obj is None


class TestGetOrCreateContext:
    """get_or_create_context creates and caches browser contexts."""

    async def test_creates_new_context(self, browser_manager):
        """First call creates a new persistent browser context."""
        mock_context = MagicMock()
        mock_context.browser.is_connected.return_value = True

        mock_pw = AsyncMock()
        mock_pw.chromium.launch_persistent_context = AsyncMock(
            return_value=mock_context
        )

        mock_start = AsyncMock(return_value=mock_pw)

        with patch(
            "playwright.async_api.async_playwright"
        ) as mock_playwright_cls:
            mock_playwright_cls.return_value = MagicMock()
            mock_playwright_cls.return_value.start = mock_start

            context = await browser_manager.get_or_create_context()

            assert context is mock_context
            mock_pw.chromium.launch_persistent_context.assert_called_once()

    async def test_reuses_cached_context(self, browser_manager):
        """Second call reuses the cached context if still alive."""
        mock_context = MagicMock()
        mock_context.browser.is_connected.return_value = True

        # Pre-populate cache
        cache = browser_manager._get_cache()
        cache.context = mock_context
        cache.playwright_obj = MagicMock()

        # Should return cached context without creating a new one
        context = await browser_manager.get_or_create_context()
        assert context is mock_context

    async def test_recreates_dead_context(self, browser_manager):
        """If cached context is dead, create a new one."""
        dead_context = MagicMock()
        dead_context.browser.is_connected.return_value = False

        new_context = MagicMock()
        new_context.browser.is_connected.return_value = True

        # Pre-populate cache with dead context
        cache = browser_manager._get_cache()
        cache.context = dead_context
        old_pw = AsyncMock()
        cache.playwright_obj = old_pw

        mock_pw = AsyncMock()
        mock_pw.chromium.launch_persistent_context = AsyncMock(
            return_value=new_context
        )
        mock_start = AsyncMock(return_value=mock_pw)

        with patch(
            "playwright.async_api.async_playwright"
        ) as mock_playwright_cls:
            mock_playwright_cls.return_value = MagicMock()
            mock_playwright_cls.return_value.start = mock_start

            context = await browser_manager.get_or_create_context()

            assert context is new_context
            old_pw.stop.assert_called_once()


class TestCookieSaveRestore:
    """Cookie save and restore operations."""

    async def test_save_cookies(self, browser_manager, tmp_path):
        """save_cookies writes storage state to disk."""
        mock_context = AsyncMock()
        cache = browser_manager._get_cache()
        cache.context = mock_context

        state_path = tmp_path / "cookies.json"
        await browser_manager.save_cookies(state_path=state_path)

        mock_context.storage_state.assert_called_once_with(path=str(state_path))

    async def test_save_cookies_no_context_is_noop(self, browser_manager, tmp_path):
        """save_cookies does nothing when no context is cached."""
        state_path = tmp_path / "cookies.json"
        await browser_manager.save_cookies(state_path=state_path)
        # Should not raise

    async def test_restore_cookies_loads_from_disk(self, browser_manager, tmp_path):
        """restore_cookies loads cookies from saved state."""
        state_path = tmp_path / "cookies.json"
        state_path.write_text(
            json.dumps(
                {
                    "cookies": [
                        {"name": "session", "domain": ".example.com", "value": "abc"},
                        {"name": "other", "domain": ".other.com", "value": "def"},
                    ]
                }
            )
        )

        mock_context = AsyncMock()
        cache = browser_manager._get_cache()
        cache.context = mock_context

        result = await browser_manager.restore_cookies(state_path=state_path)

        assert result is True
        mock_context.add_cookies.assert_called_once()
        cookies_added = mock_context.add_cookies.call_args[0][0]
        assert len(cookies_added) == 2

    async def test_restore_cookies_filters_domains(self, browser_manager, tmp_path):
        """restore_cookies excludes cookies matching exclude_domains."""
        state_path = tmp_path / "cookies.json"
        state_path.write_text(
            json.dumps(
                {
                    "cookies": [
                        {"name": "sso", "domain": ".sso.example.com", "value": "abc"},
                        {"name": "lam", "domain": ".lam.internal", "value": "def"},
                    ]
                }
            )
        )

        mock_context = AsyncMock()
        cache = browser_manager._get_cache()
        cache.context = mock_context

        result = await browser_manager.restore_cookies(
            exclude_domains=["lam.internal"], state_path=state_path
        )

        assert result is True
        cookies_added = mock_context.add_cookies.call_args[0][0]
        assert len(cookies_added) == 1
        assert cookies_added[0]["name"] == "sso"

    async def test_restore_cookies_missing_file(self, browser_manager, tmp_path):
        """restore_cookies returns False when file doesn't exist."""
        state_path = tmp_path / "nonexistent.json"
        result = await browser_manager.restore_cookies(state_path=state_path)
        assert result is False


class TestClose:
    """Close method cleans up resources."""

    async def test_close_clears_context_and_playwright(self, browser_manager):
        """close() shuts down context and playwright instance."""
        mock_context = AsyncMock()
        mock_pw = AsyncMock()

        cache = browser_manager._get_cache()
        cache.context = mock_context
        cache.playwright_obj = mock_pw

        await browser_manager.close()

        mock_context.close.assert_called_once()
        mock_pw.stop.assert_called_once()
        assert cache.context is None
        assert cache.playwright_obj is None

    async def test_close_without_context_is_noop(self, browser_manager):
        """close() doesn't raise when nothing is cached."""
        await browser_manager.close()
