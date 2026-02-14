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

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


# Import the skill module's helper functions
@pytest.fixture
def skill_tools_module():
    """Import the skill tools module."""
    import importlib.util
    from pathlib import Path

    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "backend"
        / "skills"
        / "add_user_to_coe_gitlab"
        / "tools.py"
    )
    spec = importlib.util.spec_from_file_location(
        "add_user_to_coe_gitlab_tools", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def gitlab_client_module():
    """Import the GitLab client module."""
    import importlib.util
    from pathlib import Path

    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "backend"
        / "skills"
        / "add_user_to_coe_gitlab"
        / "gitlab_client.py"
    )
    spec = importlib.util.spec_from_file_location("gitlab_client", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lam_automation_module():
    """Import the LAM automation module."""
    import importlib.util
    from pathlib import Path

    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "backend"
        / "skills"
        / "add_user_to_coe_gitlab"
        / "lam_automation.py"
    )
    spec = importlib.util.spec_from_file_location("lam_automation", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSanitizeUsername:
    """Tests for the _sanitize_username helper function."""

    def test_basic_username(self, skill_tools_module):
        """Simple username should pass through with lowercase."""
        result = skill_tools_module._sanitize_username("dkuehlwe")
        assert result == "dkuehlwe"

    def test_uppercase_converted(self, skill_tools_module):
        """Uppercase letters should be converted to lowercase."""
        result = skill_tools_module._sanitize_username("DKuehlwe")
        assert result == "dkuehlwe"

    def test_accented_characters_removed(self, skill_tools_module):
        """Accented characters should be normalized."""
        result = skill_tools_module._sanitize_username("müller")
        assert result == "muller"

    def test_special_characters_removed(self, skill_tools_module):
        """Special characters like apostrophes should be removed."""
        result = skill_tools_module._sanitize_username("o'brien")
        assert result == "obrien"

    def test_hyphen_preserved(self, skill_tools_module):
        """Hyphens are valid in Unix usernames."""
        result = skill_tools_module._sanitize_username("jean-luc")
        assert result == "jean-luc"

    def test_underscore_preserved(self, skill_tools_module):
        """Underscores are valid in Unix usernames."""
        result = skill_tools_module._sanitize_username("john_doe")
        assert result == "john_doe"

    def test_numeric_start_prefixed(self, skill_tools_module):
        """Usernames starting with numbers should be prefixed with underscore."""
        result = skill_tools_module._sanitize_username("123abc")
        assert result == "_123abc"

    def test_empty_string(self, skill_tools_module):
        """Empty string should return empty string."""
        result = skill_tools_module._sanitize_username("")
        assert result == ""

    def test_none_equivalent(self, skill_tools_module):
        """None-ish input should return empty string."""
        result = skill_tools_module._sanitize_username("")
        assert result == ""

    def test_max_length(self, skill_tools_module):
        """Username should be truncated to 32 characters."""
        long_name = "a" * 50
        result = skill_tools_module._sanitize_username(long_name)
        assert len(result) == 32

    def test_all_invalid_chars(self, skill_tools_module):
        """String with only invalid characters should return empty."""
        result = skill_tools_module._sanitize_username("@#$%^&*()")
        assert result == ""

    def test_unicode_normalization(self, skill_tools_module):
        """Unicode characters should be properly normalized."""
        # German umlaut
        assert skill_tools_module._sanitize_username("schröder") == "schroder"
        # French accent
        assert skill_tools_module._sanitize_username("café") == "cafe"
        # Spanish tilde
        assert skill_tools_module._sanitize_username("señor") == "senor"


class TestValidateEmail:
    """Tests for the _validate_email helper function."""

    def test_valid_email(self, skill_tools_module):
        """Valid email should return True."""
        assert skill_tools_module._validate_email("test@example.com") is True

    def test_valid_email_with_subdomain(self, skill_tools_module):
        """Email with subdomain should be valid."""
        assert skill_tools_module._validate_email("test@mail.example.com") is True

    def test_valid_email_with_plus(self, skill_tools_module):
        """Email with plus addressing should be valid."""
        assert skill_tools_module._validate_email("test+filter@example.com") is True

    def test_invalid_email_no_at(self, skill_tools_module):
        """Email without @ should be invalid."""
        assert skill_tools_module._validate_email("testexample.com") is False

    def test_invalid_email_no_domain(self, skill_tools_module):
        """Email without domain should be invalid."""
        assert skill_tools_module._validate_email("test@") is False

    def test_invalid_email_no_tld(self, skill_tools_module):
        """Email without TLD should be invalid."""
        assert skill_tools_module._validate_email("test@example") is False

    def test_empty_email(self, skill_tools_module):
        """Empty email should be invalid."""
        assert skill_tools_module._validate_email("") is False


class TestSearchGitlabProjectsErrorHandling:
    """Tests for search_gitlab_projects error handling."""

    @pytest.mark.asyncio
    async def test_returns_dict_on_success(self, gitlab_client_module):
        """Should return dict with success=True and projects list."""
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
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
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
        """Should return dict with success=False on HTTP error."""
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
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
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
        """Should return dict with success=False on general exception."""
        with patch.object(gitlab_client_module.httpx, "AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await gitlab_client_module.search_gitlab_projects(
                gitlab_url="https://gitlab.example.com",
                token="test-token",
                search_query="project",
            )

            assert result["success"] is False
            assert "error" in result
            assert "Connection failed" in result["error"]
            assert result["projects"] == []


class TestCreateIamAccountValidation:
    """Tests for create_iam_account input validation."""

    @pytest.mark.asyncio
    async def test_invalid_mail_nickname_rejected(self, skill_tools_module):
        """Should reject mail_nickname with only invalid characters."""
        with patch.object(skill_tools_module, "_load_skill_config") as mock_config:
            mock_config.return_value = {
                "defaults": {"lam_url": "https://lam.example.com"},
                "credentials": {
                    "lam_username": "admin",
                    "lam_password": "secret",
                },
            }

            result = await skill_tools_module.create_iam_account.ainvoke(
                {
                    "email": "test@example.com",
                    "first_name": "Test",
                    "last_name": "User",
                    "mail_nickname": "@#$%^",  # Invalid characters only
                }
            )

            result_dict = json.loads(result)
            assert result_dict["success"] is False
            assert "Invalid mail_nickname" in result_dict["error"]

    @pytest.mark.asyncio
    async def test_invalid_email_rejected(self, skill_tools_module):
        """Should reject invalid email format."""
        with patch.object(skill_tools_module, "_load_skill_config") as mock_config:
            mock_config.return_value = {
                "defaults": {"lam_url": "https://lam.example.com"},
                "credentials": {
                    "lam_username": "admin",
                    "lam_password": "secret",
                },
            }

            result = await skill_tools_module.create_iam_account.ainvoke(
                {
                    "email": "not-an-email",
                    "first_name": "Test",
                    "last_name": "User",
                }
            )

            result_dict = json.loads(result)
            assert result_dict["success"] is False
            assert "Invalid email" in result_dict["error"]

    @pytest.mark.asyncio
    async def test_missing_credentials_rejected(self, skill_tools_module):
        """Should reject when LAM credentials are not configured."""
        with patch.object(skill_tools_module, "_load_skill_config") as mock_config:
            mock_config.return_value = {
                "defaults": {"lam_url": "https://lam.example.com"},
                "credentials": {},  # No credentials
            }

            result = await skill_tools_module.create_iam_account.ainvoke(
                {
                    "email": "test@example.com",
                    "first_name": "Test",
                    "last_name": "User",
                }
            )

            result_dict = json.loads(result)
            assert result_dict["success"] is False
            assert "LAM credentials not configured" in result_dict["error"]


class TestGetTools:
    """Tests for the get_tools function."""

    def test_returns_all_tools(self, skill_tools_module):
        """get_tools should return all 5 skill tools."""
        tools = skill_tools_module.get_tools()

        assert len(tools) == 5
        tool_names = [t.name for t in tools]
        assert "resolve_participant_email" in tool_names
        assert "create_iam_account" in tool_names
        assert "create_gitlab_user_account" in tool_names
        assert "search_gitlab_project" in tool_names
        assert "add_user_to_gitlab_project" in tool_names


class TestPersistentBrowserProfile:
    """Tests for SSO session persistence via Chromium persistent context."""

    def test_get_profile_dir_returns_default(self, lam_automation_module):
        """Default profile dir should be ~/.cache/nova/lam-chromium-profile/."""
        with patch.object(lam_automation_module, "_load_config", return_value={}):
            result = lam_automation_module._get_profile_dir()
            assert result == Path.home() / ".cache" / "nova" / "lam-chromium-profile"

    def test_get_profile_dir_respects_config(self, lam_automation_module):
        """Custom profile_dir from config should be used when set."""
        config = {"browser": {"profile_dir": "/tmp/custom-profile"}}
        with patch.object(lam_automation_module, "_load_config", return_value=config):
            result = lam_automation_module._get_profile_dir()
            assert result == Path("/tmp/custom-profile")

    def test_get_profile_dir_expands_tilde(self, lam_automation_module):
        """Tilde in profile_dir should be expanded to home directory."""
        config = {"browser": {"profile_dir": "~/my-profile"}}
        with patch.object(lam_automation_module, "_load_config", return_value=config):
            result = lam_automation_module._get_profile_dir()
            assert result == Path.home() / "my-profile"

    @pytest.mark.asyncio
    async def test_launches_persistent_context_with_profile_dir(
        self, lam_automation_module, tmp_path
    ):
        """create_lam_account should use launch_persistent_context with the profile dir."""
        profile_dir = tmp_path / "test-profile"

        # Mock Playwright's async_playwright context manager
        mock_page = AsyncMock()
        mock_page.url = "https://server.com/lam/templates/login.php"
        mock_page.query_selector = AsyncMock(
            return_value=None
        )  # No passwd field = already authed
        mock_page.content = AsyncMock(return_value="<html>Account was saved</html>")
        mock_page.goto = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.fill = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.set_default_timeout = MagicMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_chromium = AsyncMock()
        mock_chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        mock_playwright = AsyncMock()
        mock_playwright.chromium = mock_chromium

        mock_async_pw = AsyncMock()
        mock_async_pw.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_async_pw.__aexit__ = AsyncMock(return_value=None)

        with (
            patch.object(
                lam_automation_module, "_get_profile_dir", return_value=profile_dir
            ),
            patch.object(
                lam_automation_module,
                "_restore_sso_cookies",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                lam_automation_module, "_build_chrome_args_from_config", return_value=[]
            ),
            patch("playwright.async_api.async_playwright", return_value=mock_async_pw),
        ):
            result = await lam_automation_module.create_lam_account(
                lam_url="https://server.com/lam/templates/account/edit.php",
                admin_username="admin",
                admin_password="secret",
                user_data={
                    "first_name": "Test",
                    "last_name": "User",
                    "email": "t@example.com",
                    "username": "tuser",
                },
            )

        # Verify launch_persistent_context was called with the profile dir
        mock_chromium.launch_persistent_context.assert_called_once()
        call_kwargs = mock_chromium.launch_persistent_context.call_args
        assert call_kwargs.kwargs["user_data_dir"] == str(profile_dir)
        assert call_kwargs.kwargs["ignore_https_errors"] is True

        # Verify context was closed
        mock_context.close.assert_called_once()

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_corrupt_profile_triggers_retry(
        self, lam_automation_module, tmp_path
    ):
        """If persistent context launch fails, the profile should be wiped and retried."""
        profile_dir = tmp_path / "corrupt-profile"
        profile_dir.mkdir()
        # Place a sentinel file so we can verify the directory was wiped
        (profile_dir / "sentinel.txt").write_text("corrupt")

        mock_page = AsyncMock()
        mock_page.url = "https://server.com/lam/templates/login.php"
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.content = AsyncMock(return_value="<html>Account was saved</html>")
        mock_page.goto = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.fill = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.set_default_timeout = MagicMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_chromium = AsyncMock()
        # First call fails (corrupt profile), second call succeeds
        mock_chromium.launch_persistent_context = AsyncMock(
            side_effect=[Exception("Failed to open profile"), mock_context]
        )

        mock_playwright = AsyncMock()
        mock_playwright.chromium = mock_chromium

        mock_async_pw = AsyncMock()
        mock_async_pw.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_async_pw.__aexit__ = AsyncMock(return_value=None)

        with (
            patch.object(
                lam_automation_module, "_get_profile_dir", return_value=profile_dir
            ),
            patch.object(
                lam_automation_module,
                "_restore_sso_cookies",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                lam_automation_module, "_build_chrome_args_from_config", return_value=[]
            ),
            patch("playwright.async_api.async_playwright", return_value=mock_async_pw),
        ):
            result = await lam_automation_module.create_lam_account(
                lam_url="https://server.com/lam/templates/account/edit.php",
                admin_username="admin",
                admin_password="secret",
                user_data={
                    "first_name": "Test",
                    "last_name": "User",
                    "email": "t@example.com",
                    "username": "tuser",
                },
            )

        # launch_persistent_context should have been called twice (first fails, second succeeds)
        assert mock_chromium.launch_persistent_context.call_count == 2
        # The sentinel file should have been removed by the profile wipe
        assert not (profile_dir / "sentinel.txt").exists()
        # The function should still succeed
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_context_closed_on_error(self, lam_automation_module, tmp_path):
        """Context should be closed even when an error occurs during automation."""
        profile_dir = tmp_path / "test-profile"

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(side_effect=Exception("Page creation failed"))
        mock_context.close = AsyncMock()

        mock_chromium = AsyncMock()
        mock_chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        mock_playwright = AsyncMock()
        mock_playwright.chromium = mock_chromium

        mock_async_pw = AsyncMock()
        mock_async_pw.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_async_pw.__aexit__ = AsyncMock(return_value=None)

        with (
            patch.object(
                lam_automation_module, "_get_profile_dir", return_value=profile_dir
            ),
            patch.object(
                lam_automation_module,
                "_restore_sso_cookies",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                lam_automation_module, "_build_chrome_args_from_config", return_value=[]
            ),
            patch("playwright.async_api.async_playwright", return_value=mock_async_pw),
        ):
            result = await lam_automation_module.create_lam_account(
                lam_url="https://server.com/lam/templates/account/edit.php",
                admin_username="admin",
                admin_password="secret",
                user_data={
                    "first_name": "Test",
                    "last_name": "User",
                    "email": "t@example.com",
                    "username": "tuser",
                },
            )

        # Context should still be closed despite the error
        mock_context.close.assert_called_once()
        assert result["success"] is False
        assert "Page creation failed" in result["error"]


class TestSSOCookiePersistence:
    """Tests for explicit SSO cookie save/restore (session cookies don't persist via user_data_dir)."""

    @pytest.mark.asyncio
    async def test_save_sso_cookies(self, lam_automation_module, tmp_path):
        """storage_state should be saved to the state file after SSO."""
        state_path = tmp_path / "sso-state.json"
        mock_context = AsyncMock()
        mock_context.storage_state = AsyncMock()

        with patch.object(
            lam_automation_module, "_get_storage_state_path", return_value=state_path
        ):
            await lam_automation_module._save_sso_cookies(mock_context)

        mock_context.storage_state.assert_called_once_with(path=str(state_path))

    @pytest.mark.asyncio
    async def test_restore_sso_cookies_loads_from_file(
        self, lam_automation_module, tmp_path
    ):
        """Saved SSO cookies should be loaded, LAM cookies should be filtered out."""
        state_path = tmp_path / "sso-state.json"
        sso_cookie = {
            "name": "PF",
            "value": "sso-token",
            "domain": "sso.example.com",
            "path": "/",
        }
        lam_cookie = {
            "name": "PHPSESSID",
            "value": "abc123",
            "domain": "lam.example.com",
            "path": "/",
        }
        state_path.write_text(json.dumps({"cookies": [sso_cookie, lam_cookie]}))

        mock_context = AsyncMock()
        mock_context.add_cookies = AsyncMock()

        with patch.object(
            lam_automation_module, "_get_storage_state_path", return_value=state_path
        ):
            result = await lam_automation_module._restore_sso_cookies(
                mock_context,
                lam_url="https://lam.example.com/lam/templates/account/edit.php",
            )

        assert result is True
        # Only SSO cookie should be restored, not the LAM PHPSESSID
        mock_context.add_cookies.assert_called_once_with([sso_cookie])

    @pytest.mark.asyncio
    async def test_restore_sso_cookies_no_file(self, lam_automation_module, tmp_path):
        """If no state file exists, restore should return False and not call add_cookies."""
        state_path = tmp_path / "nonexistent.json"
        mock_context = AsyncMock()

        with patch.object(
            lam_automation_module, "_get_storage_state_path", return_value=state_path
        ):
            result = await lam_automation_module._restore_sso_cookies(mock_context)

        assert result is False
        mock_context.add_cookies.assert_not_called()

    @pytest.mark.asyncio
    async def test_restore_sso_cookies_corrupt_file_is_deleted(
        self, lam_automation_module, tmp_path
    ):
        """Corrupt state file should be deleted and restore should return False."""
        state_path = tmp_path / "sso-state.json"
        state_path.write_text("not valid json{{{")

        mock_context = AsyncMock()

        with patch.object(
            lam_automation_module, "_get_storage_state_path", return_value=state_path
        ):
            result = await lam_automation_module._restore_sso_cookies(mock_context)

        assert result is False
        assert not state_path.exists()
