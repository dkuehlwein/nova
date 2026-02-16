"""
Shared browser automation utilities for Playwright-based skills.

Provides a reusable browser lifecycle: persistent Chromium context with
process-level caching (via sys.modules), SSO cookie save/restore, and
clean shutdown. Each skill supplies its own cache_key and profile directory
so multiple skills can maintain independent browser sessions.
"""

import json
import shutil
import sys
import types
from pathlib import Path

from playwright.async_api import async_playwright

from utils.logging import get_logger

logger = get_logger(__name__)


def get_browser_cache(cache_key: str) -> types.SimpleNamespace:
    """
    Get or create a process-level browser cache stored in sys.modules.

    sys.modules is process-global and survives module re-imports, which is
    important because Nova's skill loader re-imports tool modules on every
    invocation.

    Args:
        cache_key: Unique key in sys.modules (e.g. "_nova_lam_browser").
    """
    cache = sys.modules.get(cache_key)
    if cache is None:
        cache = types.SimpleNamespace(
            playwright_obj=None,
            context=None,
            profile_dir=None,
        )
        sys.modules[cache_key] = cache
    return cache


def get_profile_dir(
    default_dir: Path,
    custom_dir: str | None = None,
) -> Path:
    """
    Resolve the persistent browser profile directory.

    Args:
        default_dir: Fallback path when no custom_dir is provided.
        custom_dir: Optional override path (supports ~ expansion).
    """
    if custom_dir:
        return Path(custom_dir).expanduser()
    return default_dir


def get_storage_state_path(profile_dir: Path, filename: str) -> Path:
    """
    Compute the path for the SSO cookie storage state file.

    Places the file in the parent of the profile directory so it is
    sibling to the profile folder, not inside it.
    """
    return profile_dir.parent / filename


async def restore_sso_cookies(
    context,
    state_path: Path,
    filter_domain: str = "",
) -> bool:
    """
    Restore saved SSO session cookies into a browser context.

    PingOne (and similar IdPs) use session cookies (expires=-1) which
    Chromium does not persist to disk even with a user_data_dir. We
    explicitly save and restore them.

    Args:
        context: Playwright BrowserContext.
        state_path: Path to the JSON storage state file.
        filter_domain: If set, cookies whose domain contains this string
            are excluded (e.g. the application hostname, to avoid stale
            app-session cookies that bypass login but are expired
            server-side).

    Returns:
        True if cookies were restored.
    """
    if not state_path.exists():
        return False

    try:
        state = json.loads(state_path.read_text())
        cookies = state.get("cookies", [])
        if filter_domain:
            cookies = [c for c in cookies if filter_domain not in c.get("domain", "")]
        if cookies:
            await context.add_cookies(cookies)
            logger.info(f"Restored {len(cookies)} SSO cookies from {state_path}")
            return True
    except Exception as e:
        logger.warning(f"Failed to restore SSO cookies: {e}")
        state_path.unlink(missing_ok=True)
    return False


async def save_sso_cookies(context, state_path: Path) -> None:
    """Save current cookies to disk so session cookies survive browser restarts."""
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(state_path))
        logger.info(f"Saved SSO cookies to {state_path}")
    except Exception as e:
        logger.warning(f"Failed to save SSO cookies: {e}")


async def get_or_create_browser_context(
    cache_key: str,
    profile_dir: Path,
    headless: bool = False,
):
    """
    Return a cached Playwright BrowserContext, creating one if needed.

    The context is stored in sys.modules (via get_browser_cache) so it
    survives module re-imports. This keeps the browser alive across tool
    calls, preserving certificate selection and SSO cookies in-memory.

    If the cached context is dead (browser process exited), a new one is
    created automatically. If the persistent profile is corrupt, it is
    wiped and recreated.

    Args:
        cache_key: sys.modules key for this browser cache.
        profile_dir: Path to the persistent Chromium user data directory.
        headless: Run browser in headless mode.

    Returns:
        A Playwright BrowserContext (persistent).
    """
    cache = get_browser_cache(cache_key)

    # Check if cached context is still alive
    if cache.context is not None:
        try:
            if cache.context.browser and cache.context.browser.is_connected():
                logger.debug("Reusing cached browser context")
                return cache.context
        except Exception:
            pass
        # Dead context -- clean up
        logger.info("Cached browser context is dead, recreating")
        cache.context = None
        if cache.playwright_obj:
            try:
                await cache.playwright_obj.stop()
            except Exception:
                pass
            cache.playwright_obj = None

    # Create new Playwright instance and persistent context
    pw = await async_playwright().start()
    profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            ignore_https_errors=True,
        )
    except Exception as launch_err:
        # Corrupt profile -- wipe and retry once
        logger.warning(f"Persistent context launch failed, resetting profile: {launch_err}")
        shutil.rmtree(profile_dir, ignore_errors=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            ignore_https_errors=True,
        )

    cache.playwright_obj = pw
    cache.context = context
    cache.profile_dir = profile_dir
    logger.info("Created new persistent browser context")
    return context


async def close_browser(cache_key: str) -> None:
    """Close the cached browser for the given cache key."""
    cache = get_browser_cache(cache_key)
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
