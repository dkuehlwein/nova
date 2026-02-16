"""
Unit tests for the shared browser automation utility module.

Tests the generic browser lifecycle functions extracted from lam_automation.py
so they can be reused across skills (GitLab LAM, Replicon time tracking, etc.).
"""

import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _purge_test_caches():
    """Remove all test browser cache keys from sys.modules."""
    for key in [k for k in sys.modules if k.startswith("_nova_test_browser")]:
        del sys.modules[key]


@pytest.fixture(autouse=True)
def clean_browser_cache():
    """Remove any test browser cache keys from sys.modules before and after each test."""
    _purge_test_caches()
    yield
    _purge_test_caches()


@pytest.fixture
def browser_mod():
    """Import the browser_automation module."""
    from utils import browser_automation
    return browser_automation


# ---------------------------------------------------------------------------
# get_browser_cache
# ---------------------------------------------------------------------------


class TestGetBrowserCache:
    """Tests for the process-level browser cache via sys.modules."""

    def test_creates_namespace_on_first_call(self, browser_mod):
        cache = browser_mod.get_browser_cache("_nova_test_browser_1")
        assert isinstance(cache, types.SimpleNamespace)
        assert cache.playwright_obj is None
        assert cache.context is None
        assert cache.profile_dir is None

    def test_returns_same_instance_on_subsequent_calls(self, browser_mod):
        cache1 = browser_mod.get_browser_cache("_nova_test_browser_2")
        cache2 = browser_mod.get_browser_cache("_nova_test_browser_2")
        assert cache1 is cache2

    def test_different_keys_return_different_caches(self, browser_mod):
        cache_a = browser_mod.get_browser_cache("_nova_test_browser_a")
        cache_b = browser_mod.get_browser_cache("_nova_test_browser_b")
        assert cache_a is not cache_b


# ---------------------------------------------------------------------------
# get_profile_dir
# ---------------------------------------------------------------------------


class TestGetProfileDir:
    """Tests for browser profile directory resolution."""

    def test_returns_default_when_no_custom(self, browser_mod):
        default = Path("/tmp/test-default-profile")
        result = browser_mod.get_profile_dir(default_dir=default)
        assert result == default

    def test_returns_custom_when_provided(self, browser_mod):
        default = Path("/tmp/test-default-profile")
        custom = "/tmp/custom-profile"
        result = browser_mod.get_profile_dir(default_dir=default, custom_dir=custom)
        assert result == Path(custom)

    def test_expands_tilde(self, browser_mod):
        default = Path("/tmp/test-default-profile")
        result = browser_mod.get_profile_dir(default_dir=default, custom_dir="~/my-profile")
        assert result == Path.home() / "my-profile"

    def test_none_custom_dir_uses_default(self, browser_mod):
        default = Path("/tmp/test-default-profile")
        result = browser_mod.get_profile_dir(default_dir=default, custom_dir=None)
        assert result == default


# ---------------------------------------------------------------------------
# get_storage_state_path
# ---------------------------------------------------------------------------


class TestGetStorageStatePath:
    """Tests for cookie storage state path computation."""

    def test_returns_path_in_parent_of_profile_dir(self, browser_mod):
        profile_dir = Path("/tmp/nova/my-profile")
        result = browser_mod.get_storage_state_path(profile_dir, "sso-state.json")
        assert result == Path("/tmp/nova/sso-state.json")

    def test_uses_provided_filename(self, browser_mod):
        profile_dir = Path("/tmp/nova/my-profile")
        result = browser_mod.get_storage_state_path(profile_dir, "custom-cookies.json")
        assert result == Path("/tmp/nova/custom-cookies.json")


# ---------------------------------------------------------------------------
# restore_sso_cookies
# ---------------------------------------------------------------------------


class TestRestoreSsoCookies:
    """Tests for restoring SSO cookies into a browser context."""

    @pytest.mark.asyncio
    async def test_returns_false_when_no_file(self, browser_mod, tmp_path):
        state_path = tmp_path / "nonexistent.json"
        mock_context = AsyncMock()
        result = await browser_mod.restore_sso_cookies(mock_context, state_path)
        assert result is False
        mock_context.add_cookies.assert_not_called()

    @pytest.mark.asyncio
    async def test_restores_cookies_filtering_domain(self, browser_mod, tmp_path):
        state_path = tmp_path / "sso-state.json"
        sso_cookie = {"name": "PF", "value": "tok", "domain": "sso.example.com", "path": "/"}
        app_cookie = {"name": "PHPSESSID", "value": "abc", "domain": "app.example.com", "path": "/"}
        state_path.write_text(json.dumps({"cookies": [sso_cookie, app_cookie]}))

        mock_context = AsyncMock()
        mock_context.add_cookies = AsyncMock()

        result = await browser_mod.restore_sso_cookies(
            mock_context, state_path, filter_domain="app.example.com"
        )
        assert result is True
        mock_context.add_cookies.assert_called_once_with([sso_cookie])

    @pytest.mark.asyncio
    async def test_restores_all_cookies_when_no_filter(self, browser_mod, tmp_path):
        state_path = tmp_path / "sso-state.json"
        c1 = {"name": "A", "value": "1", "domain": "a.com", "path": "/"}
        c2 = {"name": "B", "value": "2", "domain": "b.com", "path": "/"}
        state_path.write_text(json.dumps({"cookies": [c1, c2]}))

        mock_context = AsyncMock()
        mock_context.add_cookies = AsyncMock()

        result = await browser_mod.restore_sso_cookies(mock_context, state_path)
        assert result is True
        mock_context.add_cookies.assert_called_once_with([c1, c2])

    @pytest.mark.asyncio
    async def test_deletes_corrupt_file_and_returns_false(self, browser_mod, tmp_path):
        state_path = tmp_path / "sso-state.json"
        state_path.write_text("not valid json{{{")

        mock_context = AsyncMock()
        result = await browser_mod.restore_sso_cookies(mock_context, state_path)
        assert result is False
        assert not state_path.exists()


# ---------------------------------------------------------------------------
# save_sso_cookies
# ---------------------------------------------------------------------------


class TestSaveSsoCookies:
    """Tests for saving SSO cookies to disk."""

    @pytest.mark.asyncio
    async def test_calls_storage_state(self, browser_mod, tmp_path):
        state_path = tmp_path / "sso-state.json"
        mock_context = AsyncMock()
        mock_context.storage_state = AsyncMock()

        await browser_mod.save_sso_cookies(mock_context, state_path)

        mock_context.storage_state.assert_called_once_with(path=str(state_path))

    @pytest.mark.asyncio
    async def test_creates_parent_directory(self, browser_mod, tmp_path):
        state_path = tmp_path / "subdir" / "deep" / "sso-state.json"
        mock_context = AsyncMock()
        mock_context.storage_state = AsyncMock()

        await browser_mod.save_sso_cookies(mock_context, state_path)

        assert state_path.parent.exists()


# ---------------------------------------------------------------------------
# get_or_create_browser_context
# ---------------------------------------------------------------------------


class TestGetOrCreateBrowserContext:
    """Tests for the cached browser context lifecycle."""

    @pytest.mark.asyncio
    async def test_creates_new_context(self, browser_mod, tmp_path):
        profile_dir = tmp_path / "profile"
        mock_context = AsyncMock()
        mock_context.browser = MagicMock()
        mock_context.browser.is_connected.return_value = True

        mock_pw = AsyncMock()
        mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        mock_async_pw = AsyncMock()
        mock_async_pw.start = AsyncMock(return_value=mock_pw)

        with patch(
            "utils.browser_automation.async_playwright",
            return_value=mock_async_pw,
        ):
            ctx = await browser_mod.get_or_create_browser_context(
                cache_key="_nova_test_browser_create",
                profile_dir=profile_dir,
            )

        assert ctx is mock_context
        mock_pw.chromium.launch_persistent_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_reuses_cached_context(self, browser_mod, tmp_path):
        profile_dir = tmp_path / "profile"
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True

        mock_context = AsyncMock()
        mock_context.browser = mock_browser

        mock_pw = AsyncMock()
        mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        mock_async_pw = AsyncMock()
        mock_async_pw.start = AsyncMock(return_value=mock_pw)

        with patch(
            "utils.browser_automation.async_playwright",
            return_value=mock_async_pw,
        ):
            ctx1 = await browser_mod.get_or_create_browser_context(
                cache_key="_nova_test_browser_reuse",
                profile_dir=profile_dir,
            )
            ctx2 = await browser_mod.get_or_create_browser_context(
                cache_key="_nova_test_browser_reuse",
                profile_dir=profile_dir,
            )

        assert ctx1 is ctx2
        mock_pw.chromium.launch_persistent_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_recovers_from_dead_context(self, browser_mod, tmp_path):
        profile_dir = tmp_path / "profile"
        cache_key = "_nova_test_browser_dead"

        # Set up dead cached context
        dead_browser = MagicMock()
        dead_browser.is_connected.return_value = False
        dead_context = AsyncMock()
        dead_context.browser = dead_browser

        cache = browser_mod.get_browser_cache(cache_key)
        cache.context = dead_context
        cache.playwright_obj = AsyncMock()

        # Set up new context
        new_browser = MagicMock()
        new_browser.is_connected.return_value = True
        new_context = AsyncMock()
        new_context.browser = new_browser

        mock_pw = AsyncMock()
        mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=new_context)

        mock_async_pw = AsyncMock()
        mock_async_pw.start = AsyncMock(return_value=mock_pw)

        with patch(
            "utils.browser_automation.async_playwright",
            return_value=mock_async_pw,
        ):
            ctx = await browser_mod.get_or_create_browser_context(
                cache_key=cache_key,
                profile_dir=profile_dir,
            )

        assert ctx is new_context

    @pytest.mark.asyncio
    async def test_retries_on_corrupt_profile(self, browser_mod, tmp_path):
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir(parents=True)

        mock_context = AsyncMock()
        mock_context.browser = MagicMock()
        mock_context.browser.is_connected.return_value = True

        mock_pw = AsyncMock()
        # First call fails, second succeeds
        mock_pw.chromium.launch_persistent_context = AsyncMock(
            side_effect=[Exception("Corrupt profile"), mock_context]
        )

        mock_async_pw = AsyncMock()
        mock_async_pw.start = AsyncMock(return_value=mock_pw)

        with patch(
            "utils.browser_automation.async_playwright",
            return_value=mock_async_pw,
        ):
            ctx = await browser_mod.get_or_create_browser_context(
                cache_key="_nova_test_browser_corrupt",
                profile_dir=profile_dir,
            )

        assert ctx is mock_context
        assert mock_pw.chromium.launch_persistent_context.call_count == 2


# ---------------------------------------------------------------------------
# close_browser
# ---------------------------------------------------------------------------


class TestCloseBrowser:
    """Tests for clean browser shutdown."""

    @pytest.mark.asyncio
    async def test_closes_context_and_stops_playwright(self, browser_mod):
        cache_key = "_nova_test_browser_close"
        mock_context = AsyncMock()
        mock_pw = AsyncMock()

        cache = browser_mod.get_browser_cache(cache_key)
        cache.context = mock_context
        cache.playwright_obj = mock_pw

        await browser_mod.close_browser(cache_key)

        mock_context.close.assert_called_once()
        mock_pw.stop.assert_called_once()
        assert cache.context is None
        assert cache.playwright_obj is None

    @pytest.mark.asyncio
    async def test_handles_no_context(self, browser_mod):
        cache_key = "_nova_test_browser_close_empty"
        # Should not raise even with empty cache
        await browser_mod.close_browser(cache_key)
