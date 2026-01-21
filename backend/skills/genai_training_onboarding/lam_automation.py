"""
LAM (LDAP Account Manager) automation using Playwright.

This module provides browser automation to create user accounts in LAM 8.7.
The selectors may need adjustment based on your specific LAM configuration.

Session Caching:
    This module uses Playwright's persistent browser context to cache SSO sessions.
    After the first successful SSO login, subsequent calls will reuse the session
    until it expires (typically 8-24 hours depending on SSO configuration).

    The session is stored in: ~/.nova/lam_session/

Reference: https://www.ldap-account-manager.org/
"""

import asyncio
import secrets
import string
import time
from pathlib import Path
from utils.logging import get_logger

logger = get_logger(__name__)

# Session storage directory for persistent browser context
SESSION_DIR = Path.home() / ".nova" / "lam_session"

# Auth state file for explicit session persistence (storageState API)
AUTH_STATE_FILE = SESSION_DIR / "auth_state.json"

# Max session age before automatic clearing (8 hours in seconds)
# SSO sessions typically expire after 8-24 hours
MAX_SESSION_AGE_SECONDS = 8 * 60 * 60


def clear_sso_session() -> bool:
    """
    Clear the cached SSO session.

    Call this if authentication is failing or to force a fresh login.

    Returns:
        True if session was cleared, False if no session existed.
    """
    import shutil

    if SESSION_DIR.exists():
        try:
            shutil.rmtree(SESSION_DIR)
            logger.info("Cleared cached SSO session")
            return True
        except Exception as e:
            logger.error(f"Failed to clear SSO session: {e}")
            # Try force cleanup as fallback
            shutil.rmtree(SESSION_DIR, ignore_errors=True)
            return False
    return False


def generate_password(length: int = 16) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


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
        - SSO sessions are cached in ~/.nova/lam_session/ to avoid repeated passcode entry.
    """
    # Import here to allow the skill to load even if playwright isn't installed
    try:
        from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: playwright install chromium (browser binaries must be installed separately after pip install)",
        }

    # Extract user data
    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    email = user_data.get("email", "")
    username = user_data.get("username")

    # Auto-generate username if not provided
    if not username:
        username = f"{first_name[0].lower()}{last_name.lower()}".replace(" ", "")

    logger.info(f"Starting LAM account creation for: {username}")

    # Check if cached session is too old and should be cleared
    if AUTH_STATE_FILE.exists():
        try:
            session_age = time.time() - AUTH_STATE_FILE.stat().st_mtime
            if session_age > MAX_SESSION_AGE_SECONDS:
                logger.info(f"Auth state is {session_age / 3600:.1f} hours old, clearing...")
                clear_sso_session()
        except OSError:
            pass  # Ignore stat errors

    # Ensure session directory exists with restricted permissions (owner-only)
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    try:
        SESSION_DIR.chmod(0o700)  # Only owner can read/write/execute
    except OSError:
        pass  # May fail on some filesystems, proceed anyway

    async with async_playwright() as p:
        context = None
        browser = None
        try:
            # Use persistent context with explicit storageState for reliable session persistence
            # Note: Chromium does not persist session cookies (those without Expires) by default
            # See: https://github.com/microsoft/playwright/issues/36139
            # The storageState API explicitly saves/restores all cookies including session cookies
            storage_state = str(AUTH_STATE_FILE) if AUTH_STATE_FILE.exists() else None
            if storage_state:
                logger.info("Loading saved auth state from previous session")

            async def launch_context(with_storage_state: bool = True):
                return await p.chromium.launch_persistent_context(
                    user_data_dir=str(SESSION_DIR),
                    headless=headless,
                    ignore_https_errors=True,  # Common for internal servers
                    storage_state=storage_state if with_storage_state else None,
                )

            try:
                context = await launch_context()
            except Exception as e:
                # Handle corrupted storage state by clearing and retrying
                if storage_state:
                    logger.warning(f"Failed to load auth state, clearing and retrying: {e}")
                    clear_sso_session()
                    context = await launch_context(with_storage_state=False)
                else:
                    raise  # Re-raise if not a storage state issue

            browser = context.browser
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(timeout_ms)

            # Step 1: Navigate to LAM login page
            # The login page is typically at /lam/templates/login.php
            login_url = lam_url.replace("/templates/account/edit.php", "/templates/login.php")
            logger.debug(f"Navigating to LAM login: {login_url}")

            await page.goto(login_url, wait_until="networkidle")

            # Step 2: Handle SSO/MFA if redirected
            # Check if we're on an SSO page (not LAM)
            current_url = page.url
            if "lam" not in current_url.lower():
                logger.info(f"SSO detected at: {current_url}")
                logger.info("Waiting for user to complete SSO/MFA login...")

                # Wait for SSO completion - user will be redirected back to LAM
                try:
                    await page.wait_for_url(
                        "**/lam/**",
                        timeout=sso_wait_timeout_ms,
                        wait_until="networkidle"
                    )
                    logger.info("SSO completed, now on LAM page")

                    # Save auth state after successful SSO to avoid re-authentication
                    # This persists all cookies including session cookies
                    await context.storage_state(path=str(AUTH_STATE_FILE))
                    logger.info("Saved SSO auth state for future sessions")
                except PlaywrightTimeout:
                    return {
                        "success": False,
                        "username": username,
                        "error": f"SSO login timeout ({sso_wait_timeout_ms/1000}s). Please complete SSO faster or increase timeout.",
                    }

            # Step 3: LAM Profile Login (after SSO)
            # LAM uses a profile selection + password form
            try:
                # Check if we're on the LAM login page (not the main interface)
                passwd_field = await page.query_selector("input[name='passwd']")
                if passwd_field:
                    logger.debug("Found LAM profile password field")

                    # Enter LAM profile password
                    await page.fill("input[name='passwd']", admin_password)

                    # Submit login form
                    await page.click("button[type='submit'], input[type='submit']")

                    # Wait for navigation after login
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
            # LAM requires clicking the "New user" button from the list page
            list_url = lam_url.replace(
                "/templates/account/edit.php",
                "/templates/lists/list.php?type=user"
            )
            logger.debug(f"Navigating to user list: {list_url}")
            await page.goto(list_url, wait_until="networkidle")

            # Click "New user" button
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

            # Step 5: Fill in the account form
            # Field names based on LAM 8.7 configuration
            try:
                # givenName - First name
                await page.fill("input[name='givenName']", first_name)

                # sn - Surname/Last name
                await page.fill("input[name='sn']", last_name)

                # mail_0 - Email (LAM uses indexed names for multi-value fields)
                await page.fill("input[name='mail_0']", email)

                # Note: Password fields are in a modal and not needed for this LAM config
                # The password is set by the user during first login

            except PlaywrightTimeout as e:
                return {
                    "success": False,
                    "username": username,
                    "error": f"Form field not found: {str(e)}. Check LAM form selectors.",
                }

            # Step 6: Submit the form
            try:
                # LAM's save button is named 'accountContainerSaveAccount'
                await page.click("button[name='accountContainerSaveAccount']")

                # Wait for response
                await page.wait_for_load_state("networkidle")

                # Check for success indicator
                # LAM typically shows a success message or redirects to account list
                page_content = await page.content()

                # Check for common error messages
                if "error" in page_content.lower() and "already exists" in page_content.lower():
                    return {
                        "success": False,
                        "username": username,
                        "error": f"User {username} already exists in LDAP",
                    }

                if "error" in page_content.lower():
                    # Try to extract error message
                    error_elem = await page.query_selector(".error, .alert-danger, .msg-error")
                    error_msg = await error_elem.text_content() if error_elem else "Unknown error"
                    return {
                        "success": False,
                        "username": username,
                        "error": f"LAM error: {error_msg}",
                    }

                # Success indicators
                if "saved" in page_content.lower() or "created" in page_content.lower():
                    logger.info(f"Successfully created LAM account: {username}")
                    return {
                        "success": True,
                        "username": username,
                        # Note: Password is not set in LAM - user sets it on first login
                    }

                # If we can't determine success/failure, assume success but warn
                logger.warning(f"Could not confirm account creation for {username}")
                return {
                    "success": True,
                    "username": username,
                    "note": "Account creation submitted but could not confirm success",
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
            # Close both context and browser to prevent lock file issues
            # See: https://github.com/microsoft/playwright/issues/35466
            # Browsers persist in background for performance; explicit close releases locks
            if context:
                await context.close()
            if browser:
                await browser.close()


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
            login_url = lam_url.replace("/templates/account/edit.php", "/templates/login.php")
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
            lam_url=os.environ.get("LAM_URL", "https://example.com/lam/templates/account/edit.php"),
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
