"""
LAM (LDAP Account Manager) automation using Playwright.

This module provides browser automation to create user accounts in LAM 8.7.
The selectors may need adjustment based on your specific LAM configuration.

Reference: https://www.ldap-account-manager.org/
"""

import asyncio
import secrets
import string
from pathlib import Path
from utils.logging import get_logger

logger = get_logger(__name__)


def generate_password(length: int = 16) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _build_lam_url(lam_url: str, template: str) -> str:
    """
    Build a LAM URL for a specific template.

    Args:
        lam_url: Base LAM URL (typically ending in /templates/account/edit.php)
        template: Target template (e.g., "login.php", "lists/list.php?type=user")

    Returns:
        Full URL for the target template
    """
    # Standard case: URL contains the expected path
    if "/templates/account/edit.php" in lam_url:
        return lam_url.replace("/templates/account/edit.php", f"/templates/{template}")

    # Fallback: Try to find /templates/ and build from there
    if "/templates/" in lam_url:
        base_idx = lam_url.find("/templates/")
        return lam_url[:base_idx] + f"/templates/{template}"

    # Last resort: Assume lam_url is the base URL (e.g., https://server.com/lam)
    base_url = lam_url.rstrip("/")
    return f"{base_url}/templates/{template}"


def _load_config() -> dict:
    """Load skill configuration from config.yaml."""
    import yaml
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _build_chrome_args_from_config() -> list[str]:
    """
    Build Chrome args for auto-selecting client certificates.
    
    Reads domains from config.yaml (browser.auto_cert_domains) and builds
    Chrome's --auto-select-certificate-for-urls flags.
    
    Returns:
        List of Chrome argument strings
    """
    config = _load_config()
    browser_config = config.get("browser", {})
    domains = browser_config.get("auto_cert_domains", [])
    
    if not domains:
        return []
    
    args = []
    for domain in domains:
        # Chrome expects pattern like: {"pattern":"https://[*.]domain.com","filter":{}}
        pattern = f'{{"pattern":"https://[*.]{{domain}}","filter":{{}}}}'.replace("{domain}", domain)
        args.append(f'--auto-select-certificate-for-urls={pattern}')
    
    return args


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

    async with async_playwright() as p:
        context = None
        browser = None
        try:
            # Chrome args for enterprise SSO environments:
            # Auto-select client certificates for known SSO domains (avoids cert picker dialog)
            # Domains are loaded from config.yaml (browser.auto_cert_domains)
            chrome_args = _build_chrome_args_from_config()

            browser = await p.chromium.launch(
                headless=headless,
                args=chrome_args,
            )
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            page.set_default_timeout(timeout_ms)

            # Step 1: Navigate to LAM login page
            # The login page is typically at /lam/templates/login.php
            login_url = _build_lam_url(lam_url, "login.php")
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
            # Note: We don't pre-check for existing users because LAM's search doesn't
            # support filtering by email. Instead, we rely on LAM's warning when
            # attempting to create a user with an existing email.
            # LAM requires clicking the "New user" button from the list page
            list_url = _build_lam_url(lam_url, "lists/list.php?type=user")
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

            # Step 6: Submit the form (may require multiple saves if Unix attributes needed)
            try:
                # LAM's save button is named 'accountContainerSaveAccount'
                await page.click("button[name='accountContainerSaveAccount']")

                # Wait for response
                await page.wait_for_load_state("networkidle")

                # Check for success indicator
                # LAM typically shows a success message or redirects to account list
                page_content = await page.content()
                page_lower = page_content.lower()

                # FIRST: Check for "already in use" message - this appears on first save
                # LAM shows "already in use." in a box at the top of the page
                if "already exists" in page_lower or "already in use" in page_lower:
                    logger.info(f"User with email {email} already exists in LAM (detected 'already in use' message)")
                    return {
                        "success": True,  # This is actually success - the account exists
                        "already_exists": True,
                        "username": username,
                        "email": email,
                        "message": "User already exists in LDAP - no action needed",
                    }

                # Check if LAM requires additional attributes (e.g., Unix tab)
                # This happens when "Some required information is missing" appears
                if "required" in page_lower and "missing" in page_lower:
                    logger.info("LAM requires additional attributes, checking for Unix tab...")

                    # Look for the Unix tab link and click it
                    unix_tab = await page.query_selector("a[href*='unix'], a:has-text('Unix'), button:has-text('Unix')")
                    if unix_tab:
                        logger.info("Clicking Unix tab to fill required attributes")
                        await unix_tab.click()
                        await page.wait_for_load_state("networkidle")

                        # Unix attributes are typically auto-generated by LAM
                        # but we need to ensure the tab is visited before saving
                        # Some LAM configs require just visiting the tab, others need field interaction

                        # Check if there are empty required fields and try to trigger auto-generation
                        uid_number_field = await page.query_selector("input[name='uidNumber']")
                        if uid_number_field:
                            # Check if it's empty - if so, LAM should auto-generate on blur
                            uid_value = await uid_number_field.get_attribute("value")
                            if not uid_value:
                                logger.debug("uidNumber is empty, triggering field interaction")
                                await uid_number_field.click()
                                await uid_number_field.press("Tab")  # Trigger blur to auto-generate
                                await page.wait_for_timeout(500)  # Brief wait for JS

                        # Now click Save again
                        logger.info("Clicking Save again after visiting Unix tab")
                        await page.click("button[name='accountContainerSaveAccount']")
                        await page.wait_for_load_state("networkidle")

                        # Re-check page content after second save
                        page_content = await page.content()
                        page_lower = page_content.lower()

                # Check if still showing required/missing after our Unix tab attempt
                if "required" in page_lower and "missing" in page_lower:
                    # Try to extract which fields are missing
                    error_elem = await page.query_selector(".error, .alert-danger, .msg-error, .statusMessage")
                    error_msg = await error_elem.text_content() if error_elem else "Required fields still missing"
                    return {
                        "success": False,
                        "username": username,
                        "error": f"LAM requires additional attributes: {error_msg}. Manual intervention may be needed.",
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
                # LAM shows "Account was saved" or similar on success
                if "saved" in page_content.lower() or "created" in page_content.lower():
                    logger.info(f"Successfully created LAM account: {username}")
                    return {
                        "success": True,
                        "username": username,
                        "email": email,
                        "message": "Account was created successfully",
                        # Note: Password is not set in LAM - user sets it on first login
                    }

                # If we're back on the user list, that usually means success
                if "list.php" in page.url and "type=user" in page.url:
                    logger.info(f"Redirected to user list - assuming success for {username}")
                    return {
                        "success": True,
                        "username": username,
                        "email": email,
                        "message": "Account creation completed (redirected to user list)",
                    }

                # If we can't determine success/failure from page content, 
                # log the page content for debugging and assume failure
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
