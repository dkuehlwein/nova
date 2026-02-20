"""
MS Graph OAuth browser automation.

When the MS Graph MCP server reports an auth failure (via NOV-122's auth_required
response), this module opens a browser and completes the OAuth flow automatically.

The user may need to complete MFA interactively - the browser stays visible.
After successful auth, cookies and tokens are persisted so re-auth isn't needed.
"""

from utils.browser_automation import BrowserManager
from utils.logging import get_logger

logger = get_logger(__name__)

_browser_manager = BrowserManager("ms-graph")

_MFA_WAIT_TIMEOUT_MS = 120_000


async def authenticate_ms_graph(
    auth_url: str,
    mfa_timeout_ms: int = _MFA_WAIT_TIMEOUT_MS,
    headless: bool = False,
) -> dict:
    """Complete MS Graph OAuth flow via Playwright browser automation.

    Opens a browser to the MS Graph MCP server's /auth/start endpoint,
    which redirects to Microsoft login. The user completes sign-in (including
    MFA if required), and the MCP server's /callback endpoint exchanges the
    code for tokens.

    Args:
        auth_url: The auth start URL (e.g., "http://localhost:8400/auth/start")
        mfa_timeout_ms: Timeout in ms waiting for MFA completion (default 2 min)
        headless: Run browser in headless mode (default False - MFA needs visible browser)

    Returns:
        Dict with "success" (bool) and optionally "error" (str)
    """
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
        }

    page = None
    try:
        context = await _browser_manager.get_or_create_context(headless=headless)
        page = await context.new_page()
        page.set_default_timeout(30000)

        logger.info("Navigating to MS Graph auth", extra={"data": {"auth_url": auth_url}})
        await page.goto(auth_url, wait_until="networkidle")

        page_content = await page.content()
        if "already authenticated" in page_content.lower():
            logger.info("Already authenticated with MS Graph")
            return {"success": True}

        # Click "Sign in with Microsoft" button if present
        sign_in_link = await page.query_selector('a.btn, a[href*="login.microsoftonline"]')
        if sign_in_link:
            logger.info("Clicking 'Sign in with Microsoft' button")
            await sign_in_link.click()
            await page.wait_for_load_state("networkidle")

        # Wait for OAuth callback to show success page
        logger.info("Waiting for OAuth flow completion (user may need to complete MFA)...")
        try:
            await page.wait_for_function(
                """() => {
                    const text = document.body.innerText.toLowerCase();
                    return text.includes('authentication successful')
                        || text.includes('already authenticated');
                }""",
                timeout=mfa_timeout_ms,
            )
        except PlaywrightTimeout:
            timeout_secs = mfa_timeout_ms / 1000
            current_content = await page.content()
            if "error" in current_content.lower():
                msg = f"OAuth flow failed or timed out after {timeout_secs}s. Check the browser window for details."
            else:
                msg = f"OAuth flow timed out after {timeout_secs}s. User may not have completed MFA in time."
            return {"success": False, "error": msg}

        logger.info("MS Graph OAuth flow completed successfully")
        await _browser_manager.save_cookies()
        return {"success": True}

    except Exception as e:
        logger.error("MS Graph browser auth error", extra={"data": {"error": str(e)}})
        return {"success": False, "error": str(e)}

    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def close_ms_graph_browser():
    """Close the cached MS Graph browser context."""
    await _browser_manager.close()
