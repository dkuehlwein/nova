"""
LAM (LDAP Account Manager) automation using Playwright.

This module provides browser automation to create user accounts in LAM 8.7.
The selectors may need adjustment based on your specific LAM configuration.

Uses a persistent Chromium profile (via shared BrowserManager) to retain
PingOne SSO session cookies across invocations, so users only need to
complete MFA once per session.

Reference: https://www.ldap-account-manager.org/
"""

import asyncio
import secrets
import string
from urllib.parse import urlparse

from utils.browser_automation import BrowserManager
from utils.logging import get_logger

logger = get_logger(__name__)

_browser_manager = BrowserManager("lam")


def generate_password(length: int = 16) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _build_lam_url(lam_url: str, template: str) -> str:
    """Build a LAM URL for a specific template (e.g., "login.php")."""
    if "/templates/account/edit.php" in lam_url:
        return lam_url.replace("/templates/account/edit.php", f"/templates/{template}")

    # Fallback: Try to find /templates/ and build from there
    if "/templates/" in lam_url:
        base_idx = lam_url.find("/templates/")
        return lam_url[:base_idx] + f"/templates/{template}"

    # Last resort: Assume lam_url is the base URL (e.g., https://server.com/lam)
    base_url = lam_url.rstrip("/")
    return f"{base_url}/templates/{template}"


async def close_lam_browser():
    """Close the cached browser (called on process shutdown or explicitly)."""
    await _browser_manager.close()


async def create_lam_account(
    lam_url: str,
    admin_username: str,
    admin_password: str,
    user_data: dict,
    headless: bool = False,
    timeout_ms: int = 30000,
    sso_wait_timeout_ms: int = 120000,
) -> dict:
    """
    Create a user account in LDAP Account Manager via browser automation.

    Args:
        lam_url: LAM URL (e.g., https://server.com/lam/templates/account/edit.php)
        admin_username: LAM admin username (used after SSO for LAM profile login)
        admin_password: LAM admin password (used after SSO for LAM profile login)
        user_data: Dict containing:
            - first_name: User's first name
            - last_name: User's last name
            - email: User's email address
            - username: Desired username (optional, auto-generated if not provided)
        headless: Run browser in headless mode (default False for SSO compatibility)
        timeout_ms: Timeout for page operations in milliseconds
        sso_wait_timeout_ms: Timeout to wait for user to complete SSO/MFA (default 2 min)

    Returns:
        Dict with:
            - success: bool
            - username: str (the created username)
            - password: str (the generated password, if successful)
            - error: str (error message if failed)

    Note:
        - The selectors in this script are based on LAM 8.7 default templates.
        - If SSO is detected, the browser will wait for manual login completion.
        - Set headless=False when SSO/MFA is required (default).
    """
    # Import here to allow the skill to load even if playwright isn't installed
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: playwright install chromium (browser binaries must be installed separately after pip install)",
        }

    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    email = user_data.get("email", "")
    username = user_data.get("username")

    if not username:
        username = f"{first_name[0].lower()}{last_name.lower()}".replace(" ", "")

    logger.info(f"Starting LAM account creation for: {username}")

    page = None
    try:
        context = await _browser_manager.get_or_create_context(headless=headless)

        # Restore saved SSO session cookies on first use (fallback for
        # when the process restarted and the browser cache was lost).
        # Filter out LAM cookies to avoid stale sessions.
        lam_host = urlparse(lam_url).hostname or ""
        exclude = [lam_host] if lam_host else None
        await _browser_manager.restore_cookies(exclude_domains=exclude)

        page = await context.new_page()
        page.set_default_timeout(timeout_ms)

        # Step 1: Navigate to LAM login page
        login_url = _build_lam_url(lam_url, "login.php")
        logger.debug(f"Navigating to LAM login: {login_url}")

        await page.goto(login_url, wait_until="networkidle")

        # Step 2: Handle SSO/MFA if redirected
        current_url = page.url
        if "lam" not in current_url.lower():
            logger.info(f"SSO detected at: {current_url}")
            logger.info("Waiting for user to complete SSO/MFA login...")

            try:
                await page.wait_for_url(
                    "**/lam/**",
                    timeout=sso_wait_timeout_ms,
                    wait_until="networkidle",
                )
                logger.info("SSO completed, now on LAM page")

                # Save SSO cookies so they survive process restarts
                await _browser_manager.save_cookies()
            except PlaywrightTimeout:
                return {
                    "success": False,
                    "username": username,
                    "error": f"SSO login timeout ({sso_wait_timeout_ms / 1000}s). Please complete SSO faster or increase timeout.",
                }

        # Step 3: LAM Profile Login (after SSO)
        try:
            passwd_field = await page.query_selector("input[name='passwd']")
            if passwd_field:
                logger.debug("Found LAM profile password field")
                await page.fill("input[name='passwd']", admin_password)
                await page.click("button[type='submit'], input[type='submit']")
                await page.wait_for_load_state("networkidle")
            else:
                logger.debug("No LAM profile login needed, already authenticated")
        except PlaywrightTimeout:
            return {
                "success": False,
                "username": username,
                "error": "LAM login form interaction failed.",
            }

        # Step 4: Navigate to user list and click "New user"
        list_url = _build_lam_url(lam_url, "lists/list.php?type=user")
        logger.debug(f"Navigating to user list: {list_url}")
        await page.goto(list_url, wait_until="networkidle")

        try:
            await page.click('button[name="new"]')
            await page.wait_for_load_state("networkidle")
            logger.debug(f"New user form URL: {page.url}")
        except PlaywrightTimeout:
            return {
                "success": False,
                "username": username,
                "error": "Could not find 'New user' button on the list page.",
            }

        # Step 5: Fill personal fields and save (duplicate check)
        # LAM flow: fill personal fields -> save -> if not duplicate -> fill uid -> save again
        logger.debug(f"Form page URL: {page.url}")
        try:
            await page.fill("input[name='givenName']", first_name)
            await page.fill("input[name='sn']", last_name)
            await page.fill("input[name='mail_0']", email)
        except PlaywrightTimeout as e:
            logger.error(f"Form field timeout on page: {page.url}")
            return {
                "success": False,
                "username": username,
                "error": f"Form field not found on {page.url}: {str(e)}. Check LAM form selectors.",
            }

        # Step 6: First save - checks for duplicate users
        try:
            await page.click("button[name='accountContainerSaveAccount']")
            await page.wait_for_load_state("networkidle")

            page_content = await page.content()
            page_lower = page_content.lower()

            if "already exists" in page_lower or "already in use" in page_lower:
                logger.info(
                    f"User with email {email} already exists in LAM (detected 'already in use' message)"
                )
                return {
                    "success": True,
                    "already_exists": True,
                    "username": username,
                    "email": email,
                    "message": "User already exists in LDAP - no action needed",
                }

            # Step 7: User doesn't exist - fill uid and save again
            logger.info("User not found, filling uid and saving again")
            try:
                await page.click('button[name="form_main_posixAccount"]')
                await page.wait_for_load_state("networkidle")
                await page.fill("input[name='uid']", username)
            except PlaywrightTimeout as e:
                logger.error(f"Unix tab/uid field timeout on page: {page.url}")
                return {
                    "success": False,
                    "username": username,
                    "error": f"Could not fill uid on {page.url}: {str(e)}. Check LAM form selectors.",
                }

            await page.click("button[name='accountContainerSaveAccount']")
            await page.wait_for_load_state("networkidle")

            page_content = await page.content()
            page_lower = page_content.lower()

            if "required" in page_lower and "missing" in page_lower:
                error_elem = await page.query_selector(
                    ".error, .alert-danger, .msg-error, .statusMessage"
                )
                error_msg = (
                    await error_elem.text_content()
                    if error_elem
                    else "Required fields still missing"
                )
                return {
                    "success": False,
                    "username": username,
                    "error": f"LAM requires additional attributes: {error_msg}. Manual intervention may be needed.",
                }

            if "error" in page_content.lower():
                error_elem = await page.query_selector(
                    ".error, .alert-danger, .msg-error"
                )
                error_msg = (
                    await error_elem.text_content()
                    if error_elem
                    else "Unknown error"
                )
                return {
                    "success": False,
                    "username": username,
                    "error": f"LAM error: {error_msg}",
                }

            if "saved" in page_content.lower() or "created" in page_content.lower():
                logger.info(f"Successfully created LAM account: {username}")
                return {
                    "success": True,
                    "username": username,
                    "email": email,
                    "message": "Account was created successfully",
                }

            if "list.php" in page.url and "type=user" in page.url:
                logger.info(
                    f"Redirected to user list - assuming success for {username}"
                )
                return {
                    "success": True,
                    "username": username,
                    "email": email,
                    "message": "Account creation completed (redirected to user list)",
                }

            logger.warning(f"Could not confirm account creation for {username}")
            logger.debug(f"Page URL: {page.url}")
            logger.debug(f"Page content sample: {page_content[:1000]}")
            return {
                "success": False,
                "username": username,
                "error": "Could not determine if account was created. Check LAM manually.",
                "page_url": page.url,
            }

        except PlaywrightTimeout:
            return {
                "success": False,
                "username": username,
                "error": "Form submission timed out",
            }

    except Exception as e:
        logger.error(f"LAM automation error: {e}")
        return {
            "success": False,
            "username": username,
            "error": str(e),
        }

    finally:
        # Close the PAGE, not the context. The context stays alive for
        # the next invocation, preserving cert selection and SSO cookies.
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def check_lam_connection(
    lam_url: str,
    admin_username: str,
    admin_password: str,
    headless: bool = True,
) -> dict:
    """
    Verify LAM connection by attempting to login.

    Args:
        lam_url: LAM URL
        admin_username: Admin username
        admin_password: Admin password
        headless: Run browser in headless mode

    Returns:
        Dict with connection status
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "connected": False,
            "error": "Playwright not installed",
        }

    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            page.set_default_timeout(10000)

            # Navigate to login
            login_url = _build_lam_url(lam_url, "login.php")
            await page.goto(login_url)

            # Check if login form appears
            await page.wait_for_selector("input[name='passwd']", timeout=5000)

            # Enter password and submit
            await page.fill("input[name='passwd']", admin_password)
            await page.click("button[type='submit'], input[type='submit']")

            # Wait for navigation
            await page.wait_for_load_state("networkidle")

            # Check if we're logged in (look for logout link or main menu)
            page_content = await page.content()

            if "logout" in page_content.lower() or "logoff" in page_content.lower():
                return {"connected": True}

            if "error" in page_content.lower() or "invalid" in page_content.lower():
                return {"connected": False, "error": "Invalid credentials"}

            return {"connected": True, "note": "Login appears successful"}

        except Exception as e:
            return {"connected": False, "error": str(e)}

        finally:
            if browser:
                await browser.close()


# For testing the automation manually
if __name__ == "__main__":
    import os

    async def test():
        result = await create_lam_account(
            lam_url=os.environ.get(
                "LAM_URL", "https://example.com/lam/templates/account/edit.php"
            ),
            admin_username=os.environ.get("LAM_USERNAME", "admin"),
            admin_password=os.environ.get("LAM_PASSWORD", "password"),
            user_data={
                "first_name": "Test",
                "last_name": "User",
                "email": "test.user@example.com",
            },
            headless=False,  # Set to False to see the browser
        )
        print(result)

    asyncio.run(test())
