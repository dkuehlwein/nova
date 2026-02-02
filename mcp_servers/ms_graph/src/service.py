"""
MS Graph Service - Main service class orchestrating Graph API access.

Provides authenticated httpx client and initializes tool classes.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from .auth import MSGraphAuth

logger = logging.getLogger(__name__)


class MSGraphService:
    """
    Microsoft Graph service that provides Mail, Calendar, and People functionality.

    Similar to GoogleWorkspaceService pattern - orchestrates auth and tool classes.
    """

    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, auth: MSGraphAuth):
        """
        Initialize the MS Graph service.

        Args:
            auth: MSGraphAuth instance for token management
        """
        self.auth = auth
        self._client: Optional[httpx.AsyncClient] = None
        self.user_info: Dict[str, Any] = {}

        # Tool classes - initialized after authentication
        self.mail_tools = None
        self.calendar_tools = None
        self.people_tools = None

    async def initialize(self) -> bool:
        """
        Initialize the service and verify authentication.

        Returns:
            True if initialization successful, False otherwise
        """
        # Check if authenticated
        if not self.auth.is_authenticated():
            logger.warning("Not authenticated - service will operate in limited mode")
            return False

        # Get access token
        token = await self.auth.get_access_token()
        if not token:
            logger.error("Could not get access token")
            return False

        # Create httpx client with auth header
        self._client = httpx.AsyncClient(
            base_url=self.GRAPH_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        # Get user profile to verify auth
        try:
            self.user_info = await self._get_user_profile()
            logger.info(f"Authenticated as: {self.user_info.get('mail', self.user_info.get('userPrincipalName', 'unknown'))}")
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return False

        # Initialize tool classes (lazy import to avoid circular imports)
        from .mail_tools import MailTools
        from .calendar_tools import CalendarTools
        from .people_tools import PeopleTools

        self.mail_tools = MailTools(self)
        self.calendar_tools = CalendarTools(self)
        self.people_tools = PeopleTools(self)

        return True

    async def ensure_client(self) -> httpx.AsyncClient:
        """
        Get the httpx client, refreshing token if needed.

        Returns:
            Authenticated httpx client

        Raises:
            RuntimeError: If not authenticated
        """
        if not self._client:
            raise RuntimeError("Service not initialized - call initialize() first")

        # Refresh token if needed
        token = await self.auth.get_access_token()
        if not token:
            raise RuntimeError("Could not get access token - re-authentication required")

        # Update authorization header
        self._client.headers["Authorization"] = f"Bearer {token}"
        return self._client

    async def _get_user_profile(self) -> Dict[str, Any]:
        """Get authenticated user's profile."""
        client = await self.ensure_client()
        response = await client.get("/me")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_ready(self) -> bool:
        """Check if service is ready to handle requests."""
        return self._client is not None and self.mail_tools is not None
