"""
Tests for MS Graph auth error detection (NOV-122).

Verifies that:
1. 401/403 responses produce clear auth error messages with auth URL
2. Non-auth errors (404, 500) pass through unchanged
"""

import httpx
import pytest

from src.service import MSGraphService
from src.people_tools import PeopleTools
from src.mail_tools import MailTools
from src.calendar_tools import CalendarTools


# -- Fixtures --


def _make_service(redirect_uri: str = "http://localhost:8400/callback") -> MSGraphService:
    """Create a MSGraphService with a mock auth and a real httpx client pointing nowhere."""

    class FakeAuth:
        def __init__(self):
            self.redirect_uri = redirect_uri

        def is_authenticated(self):
            return True

        async def get_access_token(self):
            return "fake-token"

    auth = FakeAuth()
    service = MSGraphService(auth)
    # Set a real client so ensure_client() doesn't raise RuntimeError
    service._client = httpx.AsyncClient(
        base_url="https://graph.microsoft.com/v1.0",
        headers={"Authorization": "Bearer fake-token"},
    )
    return service


def _mock_response(status_code: int, json_body: dict = None) -> httpx.Response:
    """Create a mock httpx.Response with the given status code."""
    request = httpx.Request("GET", "https://graph.microsoft.com/v1.0/test")
    response = httpx.Response(
        status_code=status_code,
        request=request,
        json=json_body or {},
    )
    return response


# -- PeopleTools auth error tests --


class TestPeopleToolsAuthError:
    """PeopleTools should detect 401/403 and return auth error with URL."""

    @pytest.fixture
    def service(self):
        return _make_service()

    @pytest.fixture
    def people(self, service):
        return PeopleTools(service)

    async def test_lookup_contact_401_returns_auth_error(self, people, monkeypatch):
        """401 from MS Graph should produce a clear auth error with auth URL."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(401)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await people.lookup_contact("John Doe")

        assert result["found"] is False
        assert "auth" in result["error"].lower() or "authentication" in result["error"].lower()
        assert "auth_url" in result
        assert "/auth/start" in result["auth_url"]
        assert result.get("auth_required") is True

    async def test_lookup_contact_403_returns_auth_error(self, people, monkeypatch):
        """403 from MS Graph should produce a clear auth error with auth URL."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(403)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await people.lookup_contact("John Doe")

        assert result["found"] is False
        assert "auth" in result["error"].lower() or "authentication" in result["error"].lower()
        assert "auth_url" in result
        assert result.get("auth_required") is True

    async def test_lookup_contact_404_passes_through(self, people, monkeypatch):
        """404 from MS Graph should NOT be treated as an auth error."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(404)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await people.lookup_contact("John Doe")

        assert result["found"] is False
        assert "auth_url" not in result
        assert result.get("auth_required") is not True

    async def test_lookup_contact_500_passes_through(self, people, monkeypatch):
        """500 from MS Graph should NOT be treated as an auth error."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(500)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await people.lookup_contact("John Doe")

        assert result["found"] is False
        assert "auth_url" not in result
        assert result.get("auth_required") is not True

    async def test_search_people_401_returns_auth_error(self, people, monkeypatch):
        """search_people should also detect auth errors."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(401)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await people.search_people("John")

        assert isinstance(result, dict)
        assert "auth" in result["error"].lower() or "authentication" in result["error"].lower()
        assert "auth_url" in result
        assert result.get("auth_required") is True

    async def test_get_user_profile_401_returns_auth_error(self, people, monkeypatch):
        """get_user_profile should also detect auth errors."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(401)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await people.get_user_profile("me")

        assert isinstance(result, dict)
        assert "auth" in result["error"].lower() or "authentication" in result["error"].lower()
        assert "auth_url" in result
        assert result.get("auth_required") is True


# -- MailTools auth error tests --


class TestMailToolsAuthError:
    """MailTools should detect 401/403 and return auth error with URL."""

    @pytest.fixture
    def service(self):
        return _make_service()

    @pytest.fixture
    def mail(self, service):
        return MailTools(service)

    async def test_list_emails_401_returns_auth_error(self, mail, monkeypatch):
        """list_emails should detect auth errors."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(401)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await mail.list_emails()

        assert isinstance(result, dict)
        assert "auth" in result["error"].lower() or "authentication" in result["error"].lower()
        assert "auth_url" in result
        assert result.get("auth_required") is True

    async def test_list_emails_404_passes_through(self, mail, monkeypatch):
        """404 should not be treated as an auth error."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(404)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await mail.list_emails()

        assert isinstance(result, dict)
        assert "auth_url" not in result
        assert result.get("auth_required") is not True

    async def test_read_email_401_returns_auth_error(self, mail, monkeypatch):
        """read_email should detect auth errors."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(401)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await mail.read_email("some-id")

        assert isinstance(result, dict)
        assert "auth_url" in result
        assert result.get("auth_required") is True

    async def test_send_email_401_returns_auth_error(self, mail, monkeypatch):
        """send_email should detect auth errors."""
        async def mock_post(self_client, url, **kwargs):
            return _mock_response(401)

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await mail.send_email(["test@example.com"], "Subject", "Body")

        assert isinstance(result, dict)
        assert "auth_url" in result
        assert result.get("auth_required") is True


# -- CalendarTools auth error tests --


class TestCalendarToolsAuthError:
    """CalendarTools should detect 401/403 and return auth error with URL."""

    @pytest.fixture
    def service(self):
        return _make_service()

    @pytest.fixture
    def calendar(self, service):
        return CalendarTools(service)

    async def test_list_events_401_returns_auth_error(self, calendar, monkeypatch):
        """list_calendar_events should detect auth errors."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(401)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await calendar.list_calendar_events()

        assert isinstance(result, dict)
        assert "auth" in result["error"].lower() or "authentication" in result["error"].lower()
        assert "auth_url" in result
        assert result.get("auth_required") is True

    async def test_list_events_500_passes_through(self, calendar, monkeypatch):
        """500 should not be treated as an auth error."""
        async def mock_get(self_client, url, **kwargs):
            return _mock_response(500)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await calendar.list_calendar_events()

        assert isinstance(result, dict)
        assert "auth_url" not in result
        assert result.get("auth_required") is not True

    async def test_create_event_401_returns_auth_error(self, calendar, monkeypatch):
        """create_event should detect auth errors."""
        async def mock_post(self_client, url, **kwargs):
            return _mock_response(401)

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await calendar.create_event(
            "Meeting", "2026-03-01T10:00:00", "2026-03-01T11:00:00"
        )

        assert isinstance(result, dict)
        assert "auth_url" in result
        assert result.get("auth_required") is True

    async def test_delete_event_401_returns_auth_error(self, calendar, monkeypatch):
        """delete_event should detect auth errors."""
        async def mock_delete(self_client, url, **kwargs):
            return _mock_response(401)

        monkeypatch.setattr(httpx.AsyncClient, "delete", mock_delete)

        result = await calendar.delete_event("some-event-id")

        assert isinstance(result, dict)
        assert "auth_url" in result
        assert result.get("auth_required") is True


# -- Auth URL construction tests --


class TestAuthUrlConstruction:
    """Auth URL should be correctly derived from the redirect URI."""

    async def test_auth_url_from_default_redirect_uri(self):
        """Default redirect_uri -> correct auth start URL."""
        service = _make_service(redirect_uri="http://localhost:8400/callback")
        assert service.get_auth_start_url() == "http://localhost:8400/auth/start"

    async def test_auth_url_from_custom_redirect_uri(self):
        """Custom redirect_uri -> correct auth start URL."""
        service = _make_service(redirect_uri="http://myhost:9000/callback")

        assert service.get_auth_start_url() == "http://myhost:9000/auth/start"
