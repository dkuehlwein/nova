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
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


# Import the skill module's helper functions
@pytest.fixture
def skill_tools_module():
    """Import the skill tools module."""
    import importlib.util
    from pathlib import Path

    module_path = Path(__file__).parent.parent.parent.parent / "backend" / "skills" / "add_user_to_coe_gitlab" / "tools.py"
    spec = importlib.util.spec_from_file_location("add_user_to_coe_gitlab_tools", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def gitlab_client_module():
    """Import the GitLab client module."""
    import importlib.util
    from pathlib import Path

    module_path = Path(__file__).parent.parent.parent.parent / "backend" / "skills" / "add_user_to_coe_gitlab" / "gitlab_client.py"
    spec = importlib.util.spec_from_file_location("gitlab_client", module_path)
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
        """Should return dict with success=False on HTTP error."""
        with patch.object(gitlab_client_module.httpx, "AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.raise_for_status.side_effect = gitlab_client_module.httpx.HTTPStatusError(
                "Forbidden", request=MagicMock(), response=mock_response
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
        """Should return dict with success=False on general exception."""
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

            result = await skill_tools_module.create_iam_account.ainvoke({
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "mail_nickname": "@#$%^",  # Invalid characters only
            })

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

            result = await skill_tools_module.create_iam_account.ainvoke({
                "email": "not-an-email",
                "first_name": "Test",
                "last_name": "User",
            })

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

            result = await skill_tools_module.create_iam_account.ainvoke({
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
            })

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
