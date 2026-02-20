"""
Shared Playwright browser automation utility.

Provides persistent browser contexts with cookie management, designed to be
reused across different automation flows (LAM, MS Graph auth, future OAuth).

Each consumer uses a unique namespace to isolate browser profiles and cookies.
Browser contexts survive module re-imports via a process-level cache in sys.modules.
"""

import json
import shutil
import sys
import types
from pathlib import Path
from typing import Optional

from utils.logging import get_logger

logger = get_logger(__name__)

_BASE_CACHE_DIR = Path.home() / ".cache" / "nova"
_CACHE_KEY_PREFIX = "_nova_browser_"


class BrowserManager:
    """Manages a persistent Playwright browser context for a given namespace.

    The context is cached in sys.modules so it survives module re-imports
    (Nova's skill loader re-imports tools on every invocation). This keeps
    the browser alive across tool calls, preserving cert selection and SSO
    cookies in-memory.
    """

    def __init__(self, namespace: str):
        self.namespace = namespace
        self._cache_key = f"{_CACHE_KEY_PREFIX}{namespace}"

    @property
    def profile_dir(self) -> Path:
        return _BASE_CACHE_DIR / f"{self.namespace}-chromium-profile"

    @property
    def cookie_storage_path(self) -> Path:
        return _BASE_CACHE_DIR / f"{self.namespace}-sso-state.json"

    def _get_cache(self):
        cache = sys.modules.get(self._cache_key)
        if cache is None:
            cache = types.SimpleNamespace(playwright_obj=None, context=None)
            sys.modules[self._cache_key] = cache
        return cache

    async def get_or_create_context(self, headless: bool = False):
        """Return a cached Playwright BrowserContext, creating one if needed.

        Args:
            headless: Run browser in headless mode (default False for MFA compat)
        """
        from playwright.async_api import async_playwright

        cache = self._get_cache()

        # Reuse cached context if still alive
        if cache.context is not None:
            try:
                if cache.context.browser and cache.context.browser.is_connected():
                    logger.debug("Reusing cached browser context", extra={"data": {"namespace": self.namespace}})
                    return cache.context
            except Exception:
                pass
            # Dead context - clean up
            logger.info("Cached browser context is dead, recreating", extra={"data": {"namespace": self.namespace}})
            await self._cleanup_cache(cache)

        # Create new Playwright instance and persistent context
        pw = await async_playwright().start()
        try:
            profile_dir = self.profile_dir
            profile_dir.mkdir(parents=True, exist_ok=True)

            try:
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=headless,
                    ignore_https_errors=True,
                )
            except Exception as launch_err:
                # Corrupt profile - wipe and retry once
                logger.warning(
                    "Persistent context launch failed, resetting profile",
                    extra={"data": {"namespace": self.namespace, "error": str(launch_err)}}
                )
                shutil.rmtree(profile_dir, ignore_errors=True)
                profile_dir.mkdir(parents=True, exist_ok=True)
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=headless,
                    ignore_https_errors=True,
                )
        except Exception:
            await pw.stop()
            raise

        cache.playwright_obj = pw
        cache.context = context
        logger.info("Created new persistent browser context", extra={"data": {"namespace": self.namespace}})
        return context

    async def _cleanup_cache(self, cache) -> None:
        """Silently close context and playwright, then reset cache fields."""
        if cache.context:
            try:
                await cache.context.close()
            except Exception:
                pass
            cache.context = None
        if cache.playwright_obj:
            try:
                await cache.playwright_obj.stop()
            except Exception:
                pass
            cache.playwright_obj = None

    async def save_cookies(self, state_path: Optional[Path] = None) -> None:
        """Save current cookies to disk so session cookies survive browser restarts."""
        state_path = state_path or self.cookie_storage_path
        cache = self._get_cache()
        if not cache.context:
            return
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            await cache.context.storage_state(path=str(state_path))
            logger.info("Saved cookies", extra={"data": {"namespace": self.namespace, "state_path": state_path}})
        except Exception as e:
            logger.warning("Failed to save cookies", extra={"data": {"namespace": self.namespace, "error": str(e)}})

    async def restore_cookies(
        self,
        exclude_domains: Optional[list[str]] = None,
        state_path: Optional[Path] = None,
    ) -> bool:
        """Restore saved cookies into the browser context.

        Args:
            exclude_domains: List of domain substrings to filter out
            state_path: Override the default cookie storage path

        Returns:
            True if cookies were restored
        """
        state_path = state_path or self.cookie_storage_path
        if not state_path.exists():
            return False

        cache = self._get_cache()
        if not cache.context:
            return False

        try:
            state = json.loads(state_path.read_text())
            cookies = state.get("cookies", [])
            if exclude_domains:
                cookies = [
                    c
                    for c in cookies
                    if not any(d in c.get("domain", "") for d in exclude_domains)
                ]
            if cookies:
                await cache.context.add_cookies(cookies)
                logger.info(
                    "Restored cookies",
                    extra={"data": {"namespace": self.namespace, "count": len(cookies), "state_path": str(state_path)}}
                )
                return True
        except Exception as e:
            logger.warning("Failed to restore cookies", extra={"data": {"namespace": self.namespace, "error": str(e)}})
            state_path.unlink(missing_ok=True)
        return False

    async def close(self) -> None:
        """Close the cached browser context and Playwright instance."""
        await self._cleanup_cache(self._get_cache())
