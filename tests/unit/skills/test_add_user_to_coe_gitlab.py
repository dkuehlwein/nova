"""
Unit tests for the Add User to CoE GitLab skill.

Tests helper functions, input validation, and tool behavior.

These tests are isolated unit tests that don't require external services
(GitLab, MS Graph, LAM).
"""

import os
import sys

# Add backend to path for imports before any other imports
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Disable database-related imports for these tests
os.environ.setdefault("NOVA_SKIP_DB", "1")

import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


# --- Shared helpers ---


def _load_skill_module(filename: str, module_name: str):
    """Load a module from the add_user_to_coe_gitlab skill directory."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "backend"
        / "skills"
        / "add_user_to_coe_gitlab"
        / filename
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_mock_lam_page(
    url: str = "https://server.com/lam/templates/login.php",
    content: str = "<html>Account was saved</html>",
) -> AsyncMock:
    """Create a mock Playwright page pre-configured for LAM automation tests."""
    page = AsyncMock()
    page.url = url
    page.query_selector = AsyncMock(return_value=None)
    page.content = AsyncMock(return_value=content)
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_url = AsyncMock()
    page.set_default_timeout = MagicMock()
    page.close = AsyncMock()
    return page


_DEFAULT_USER_DATA = {
    "first_name": "Test",
    "last_name": "User",
    "email": "t@example.com",
    "username": "tuser",
}

_DEFAULT_LAM_URL = "https://server.com/lam/templates/account/edit.php"


@contextmanager
def _patch_browser_manager(lam_module, mock_context, extra_patches=None):
    """Patch _browser_manager.get_or_create_context and restore_cookies."""
    patches = [
        patch.object(
            lam_module._browser_manager,
            "get_or_create_context",
            new_callable=AsyncMock,
            return_value=mock_context,
        ),
        patch.object(
            lam_module._browser_manager,
            "restore_cookies",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ]
    if extra_patches:
        patches.extend(extra_patches)

    # Enter all patches
    mocks = []
    for p in patches:
        mocks.append(p.__enter__())
    try:
        yield mocks
    finally:
        for p in reversed(patches):
            p.__exit__(None, None, None)


# --- Fixtures ---


@pytest.fixture
def skill_tools_module():
    return _load_skill_module("tools.py", "add_user_to_coe_gitlab_tools")


@pytest.fixture
def gitlab_client_module():
    return _load_skill_module("gitlab_client.py", "gitlab_client")


@pytest.fixture
def lam_automation_module():
    return _load_skill_module("lam_automation.py", "lam_automation")


@pytest.fixture(autouse=True)
def clean_browser_cache():
    """Remove any browser cache entries from sys.modules after each test."""
    yield
    keys_to_remove = [k for k in sys.modules if k.startswith("_nova_browser_")]
    for key in keys_to_remove:
        del sys.modules[key]


# --- Test classes ---


class TestSanitizeUsername:
    """Tests for the _sanitize_username helper function."""

    def test_basic_username(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("dkuehlwe") == "dkuehlwe"

    def test_uppercase_converted(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("DKuehlwe") == "dkuehlwe"

    def test_accented_characters_removed(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("muller") == "muller"

    def test_special_characters_removed(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("o'brien") == "obrien"

    def test_hyphen_preserved(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("jean-luc") == "jean-luc"

    def test_underscore_preserved(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("john_doe") == "john_doe"

    def test_numeric_start_prefixed(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("123abc") == "_123abc"

    def test_empty_string(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("") == ""

    def test_none_equivalent(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("") == ""

    def test_max_length(self, skill_tools_module):
        result = skill_tools_module._sanitize_username("a" * 50)
        assert len(result) == 32

    def test_all_invalid_chars(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("@#$%^&*()") == ""

    def test_unicode_normalization(self, skill_tools_module):
        assert skill_tools_module._sanitize_username("schroder") == "schroder"
        assert skill_tools_module._sanitize_username("cafe") == "cafe"
        assert skill_tools_module._sanitize_username("senor") == "senor"


class TestValidateEmail:
    """Tests for the _validate_email helper function."""

    def test_valid_email(self, skill_tools_module):
        assert skill_tools_module._validate_email("test@example.com") is True

    def test_valid_email_with_subdomain(self, skill_tools_module):
        assert skill_tools_module._validate_email("test@mail.example.com") is True

    def test_valid_email_with_plus(self, skill_tools_module):
        assert skill_tools_module._validate_email("test+filter@example.com") is True

    def test_invalid_email_no_at(self, skill_tools_module):
        assert skill_tools_module._validate_email("testexample.com") is False

    def test_invalid_email_no_domain(self, skill_tools_module):
        assert skill_tools_module._validate_email("test@") is False

    def test_invalid_email_no_tld(self, skill_tools_module):
        assert skill_tools_module._validate_email("test@example") is False

    def test_empty_email(self, skill_tools_module):
        assert skill_tools_module._validate_email("") is False


class TestSearchGitlabProjectsErrorHandling:
    """Tests for search_gitlab_projects error handling."""

    @pytest.mark.asyncio
    async def test_returns_dict_on_success(self, gitlab_client_module):
        with patch.object(gitlab_client_module.httpx, "AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {
                    "id": 1,
                    "path_with_namespace": "group/project",
                    "name": "project",
                    "description": "A project",
                    "web_url": "https://gitlab.example.com/group/project",
                }
            ]
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await gitlab_client_module.search_gitlab_projects(
                gitlab_url="https://gitlab.example.com",
                token="test-token",
                search_query="project",
            )

            assert result["success"] is True
            assert len(result["projects"]) == 1
            assert result["projects"][0]["path_with_namespace"] == "group/project"

    @pytest.mark.asyncio
    async def test_returns_dict_on_http_error(self, gitlab_client_module):
        with patch.object(gitlab_client_module.httpx, "AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.raise_for_status.side_effect = (
                gitlab_client_module.httpx.HTTPStatusError(
                    "Forbidden", request=MagicMock(), response=mock_response
                )
            )

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await gitlab_client_module.search_gitlab_projects(
                gitlab_url="https://gitlab.example.com",
                token="test-token",
                search_query="project",
            )

            assert result["success"] is False
            assert "error" in result
            assert result["projects"] == []

    @pytest.mark.asyncio
    async def test_returns_dict_on_exception(self, gitlab_client_module):
        with patch.object(gitlab_client_module.httpx, "AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await gitlab_client_module.search_gitlab_projects(
                gitlab_url="https://gitlab.example.com",
                token="test-token",
                search_query="project",
            )

            assert result["success"] is False
            assert "Connection failed" in result["error"]
            assert result["projects"] == []


class TestCreateIamAccountValidation:
    """Tests for create_iam_account input validation."""

    @pytest.mark.asyncio
    async def test_invalid_mail_nickname_rejected(self, skill_tools_module):
        with patch.object(skill_tools_module, "_load_skill_config") as mock_config:
            mock_config.return_value = {
                "defaults": {"lam_url": "https://lam.example.com"},
                "credentials": {"lam_username": "admin", "lam_password": "secret"},
            }

            result = await skill_tools_module.create_iam_account.ainvoke(
                {
                    "email": "test@example.com",
                    "first_name": "Test",
                    "last_name": "User",
                    "mail_nickname": "@#$%^",
                }
            )

            result_dict = json.loads(result)
            assert result_dict["success"] is False
            assert "Invalid mail_nickname" in result_dict["error"]

    @pytest.mark.asyncio
    async def test_invalid_email_rejected(self, skill_tools_module):
        with patch.object(skill_tools_module, "_load_skill_config") as mock_config:
            mock_config.return_value = {
                "defaults": {"lam_url": "https://lam.example.com"},
                "credentials": {"lam_username": "admin", "lam_password": "secret"},
            }

            result = await skill_tools_module.create_iam_account.ainvoke(
                {"email": "not-an-email", "first_name": "Test", "last_name": "User"}
            )

            result_dict = json.loads(result)
            assert result_dict["success"] is False
            assert "Invalid email" in result_dict["error"]

    @pytest.mark.asyncio
    async def test_missing_credentials_rejected(self, skill_tools_module):
        with patch.object(skill_tools_module, "_load_skill_config") as mock_config:
            mock_config.return_value = {
                "defaults": {"lam_url": "https://lam.example.com"},
                "credentials": {},
            }

            result = await skill_tools_module.create_iam_account.ainvoke(
                {"email": "test@example.com", "first_name": "Test", "last_name": "User"}
            )

            result_dict = json.loads(result)
            assert result_dict["success"] is False
            assert "LAM credentials not configured" in result_dict["error"]


class TestGetTools:
    """Tests for the get_tools function."""

    def test_returns_all_tools(self, skill_tools_module):
        tools = skill_tools_module.get_tools()
        assert len(tools) == 5
        tool_names = [t.name for t in tools]
        assert "resolve_participant_email" in tool_names
        assert "create_iam_account" in tool_names
        assert "create_gitlab_user_account" in tool_names
        assert "search_gitlab_project" in tool_names
        assert "add_user_to_gitlab_project" in tool_names


class TestPersistentBrowserProfile:
    """Tests for SSO session persistence via cached browser context."""

    @pytest.mark.asyncio
    async def test_create_lam_account_uses_cached_context(self, lam_automation_module):
        mock_page = _make_mock_lam_page()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with _patch_browser_manager(lam_automation_module, mock_context) as [mock_get_ctx, _]:
            result = await lam_automation_module.create_lam_account(
                lam_url=_DEFAULT_LAM_URL,
                admin_username="admin",
                admin_password="secret",
                user_data=_DEFAULT_USER_DATA,
            )

        mock_get_ctx.assert_called_once()
        mock_page.close.assert_called_once()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_page_closed_on_error(self, lam_automation_module):
        mock_page = AsyncMock()
        mock_page.set_default_timeout = MagicMock()
        mock_page.goto = AsyncMock(side_effect=Exception("Navigation failed"))
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with _patch_browser_manager(lam_automation_module, mock_context):
            result = await lam_automation_module.create_lam_account(
                lam_url=_DEFAULT_LAM_URL,
                admin_username="admin",
                admin_password="secret",
                user_data=_DEFAULT_USER_DATA,
            )

        mock_page.close.assert_called_once()
        assert result["success"] is False
        assert "Navigation failed" in result["error"]


class TestBrowserCache:
    """Tests for the LAM browser manager integration."""

    def test_lam_browser_manager_uses_lam_namespace(self, lam_automation_module):
        assert lam_automation_module._browser_manager.namespace == "lam"

    @pytest.mark.asyncio
    async def test_browser_reuse_across_calls(self, lam_automation_module):
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True

        mock_context = AsyncMock()
        mock_context.browser = mock_browser

        mock_pw = AsyncMock()
        mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        mock_async_pw_instance = AsyncMock()
        mock_async_pw_instance.start = AsyncMock(return_value=mock_pw)

        with patch(
            "playwright.async_api.async_playwright",
            return_value=mock_async_pw_instance,
        ):
            ctx1 = await lam_automation_module._browser_manager.get_or_create_context()
            ctx2 = await lam_automation_module._browser_manager.get_or_create_context()

        assert ctx1 is ctx2
        mock_pw.chromium.launch_persistent_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_dead_browser_recovery(self, lam_automation_module):
        dead_browser = MagicMock()
        dead_browser.is_connected.return_value = False
        dead_context = AsyncMock()
        dead_context.browser = dead_browser

        cache = lam_automation_module._browser_manager._get_cache()
        cache.context = dead_context
        old_pw = AsyncMock()
        cache.playwright_obj = old_pw

        new_browser = MagicMock()
        new_browser.is_connected.return_value = True
        new_context = AsyncMock()
        new_context.browser = new_browser

        mock_pw = AsyncMock()
        mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=new_context)

        mock_async_pw_instance = AsyncMock()
        mock_async_pw_instance.start = AsyncMock(return_value=mock_pw)

        with patch(
            "playwright.async_api.async_playwright",
            return_value=mock_async_pw_instance,
        ):
            ctx = await lam_automation_module._browser_manager.get_or_create_context()

        assert ctx is new_context
        old_pw.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_lam_browser(self, lam_automation_module):
        mock_context = AsyncMock()
        mock_pw = AsyncMock()

        cache = lam_automation_module._browser_manager._get_cache()
        cache.context = mock_context
        cache.playwright_obj = mock_pw

        await lam_automation_module.close_lam_browser()

        mock_context.close.assert_called_once()
        mock_pw.stop.assert_called_once()
        assert cache.context is None
        assert cache.playwright_obj is None


class TestTabbedFormFill:
    """Tests for LAM's two-step form: save personal fields first (duplicate check), then uid."""

    @pytest.mark.asyncio
    async def test_saves_personal_fields_first_then_fills_uid(self, lam_automation_module):
        """Flow: fill personal fields -> save (duplicate check) -> fill uid -> save again."""
        call_log = []

        mock_page = _make_mock_lam_page()

        async def track_fill(selector, value):
            call_log.append(("fill", selector, value))

        async def track_click(selector):
            call_log.append(("click", selector))

        mock_page.fill = AsyncMock(side_effect=track_fill)
        mock_page.click = AsyncMock(side_effect=track_click)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with _patch_browser_manager(lam_automation_module, mock_context):
            result = await lam_automation_module.create_lam_account(
                lam_url=_DEFAULT_LAM_URL,
                admin_username="admin",
                admin_password="secret",
                user_data={
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@example.com",
                    "username": "jdoe",
                },
            )

        assert result["success"] is True

        form_fills = [(op, sel) for op, sel, *_ in call_log if op == "fill"]

        # Personal tab fields should be filled
        assert ("fill", "input[name='givenName']") in form_fills
        assert ("fill", "input[name='sn']") in form_fills
        assert ("fill", "input[name='mail_0']") in form_fills

        # First save should happen BEFORE unix tab
        first_save_idx = call_log.index(
            ("click", "button[name='accountContainerSaveAccount']")
        )
        givenname_idx = call_log.index(("fill", "input[name='givenName']", "Jane"))
        assert givenname_idx < first_save_idx

        # Unix tab and uid fill should happen AFTER first save
        unix_tab_idx = call_log.index(
            ("click", 'button[name="form_main_posixAccount"]')
        )
        uid_idx = call_log.index(("fill", "input[name='uid']", "jdoe"))
        assert first_save_idx < unix_tab_idx < uid_idx

        # Second save should happen after uid fill
        save_clicks = [
            i for i, entry in enumerate(call_log)
            if entry == ("click", "button[name='accountContainerSaveAccount']")
        ]
        assert len(save_clicks) == 2
        assert save_clicks[1] > uid_idx

    @pytest.mark.asyncio
    async def test_skips_uid_when_user_already_exists(self, lam_automation_module):
        """If first save detects duplicate, should return immediately without filling uid."""
        call_log = []

        mock_page = _make_mock_lam_page(
            content="<html>This attribute is already in use.</html>"
        )

        async def track_fill(selector, value):
            call_log.append(("fill", selector, value))

        async def track_click(selector):
            call_log.append(("click", selector))

        mock_page.fill = AsyncMock(side_effect=track_fill)
        mock_page.click = AsyncMock(side_effect=track_click)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with _patch_browser_manager(lam_automation_module, mock_context):
            result = await lam_automation_module.create_lam_account(
                lam_url=_DEFAULT_LAM_URL,
                admin_username="admin",
                admin_password="secret",
                user_data={
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@example.com",
                    "username": "jdoe",
                },
            )

        assert result["success"] is True
        assert result["already_exists"] is True

        form_fills = [sel for op, sel, *_ in call_log if op == "fill"]
        assert "input[name='uid']" not in form_fills

        form_clicks = [sel for op, sel, *_ in call_log if op == "click"]
        assert 'button[name="form_main_posixAccount"]' not in form_clicks


class TestSSOCookiePersistence:
    """Tests for SSO cookie save/restore integration with BrowserManager."""

    def test_cookie_storage_path_uses_lam_namespace(self, lam_automation_module):
        expected = Path.home() / ".cache" / "nova" / "lam-sso-state.json"
        assert lam_automation_module._browser_manager.cookie_storage_path == expected

    @pytest.mark.asyncio
    async def test_restore_cookies_called_on_account_creation(self, lam_automation_module):
        """create_lam_account should call restore_cookies with LAM host excluded."""
        mock_page = _make_mock_lam_page()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with _patch_browser_manager(lam_automation_module, mock_context) as [_, mock_restore]:
            await lam_automation_module.create_lam_account(
                lam_url=_DEFAULT_LAM_URL,
                admin_username="admin",
                admin_password="secret",
                user_data=_DEFAULT_USER_DATA,
            )

        mock_restore.assert_called_once()
        exclude = mock_restore.call_args.kwargs.get("exclude_domains")
        assert exclude is not None
        assert "server.com" in exclude

    @pytest.mark.asyncio
    async def test_save_cookies_called_after_sso(self, lam_automation_module):
        """save_cookies should be called when SSO redirect is detected and completed."""
        mock_page = _make_mock_lam_page(url="https://sso.example.com/login")
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        save_patch = patch.object(
            lam_automation_module._browser_manager,
            "save_cookies",
            new_callable=AsyncMock,
        )

        with _patch_browser_manager(
            lam_automation_module, mock_context, extra_patches=[save_patch]
        ) as [_, _, mock_save]:
            await lam_automation_module.create_lam_account(
                lam_url=_DEFAULT_LAM_URL,
                admin_username="admin",
                admin_password="secret",
                user_data=_DEFAULT_USER_DATA,
            )

        mock_save.assert_called_once()
