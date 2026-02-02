"""
MS Graph OAuth Authentication module.

Handles OAuth 2.0 authorization code flow with MSAL (Microsoft Authentication Library).
Supports both interactive authentication and token refresh.
"""

import json
import logging
import os
import secrets
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import msal

logger = logging.getLogger(__name__)


class MSGraphAuth:
    """
    Handles OAuth 2.0 authorization code flow with MSAL.

    Token storage: File-based in credentials/ directory
    Flow: Browser-based login, user consent, token caching
    """

    # Scopes required for MS Graph MCP server
    # Note: People.Read is fallback only - prefer User.Read.All for mailNickname
    SCOPES = [
        "User.Read",           # /me profile
        "Mail.Read",           # List/read emails
        "Calendars.Read",      # List events
        "Calendars.ReadWrite", # Create/update/delete events
        "User.Read.All",       # Search directory users - gets mailNickname (login name)
    ]

    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        client_secret: str,
        token_cache_path: str,
        redirect_uri: str = "http://localhost:8400/callback"
    ):
        """
        Initialize the MS Graph auth handler.

        Args:
            client_id: Azure AD application (client) ID
            tenant_id: Azure AD directory (tenant) ID
            client_secret: Azure AD client secret
            token_cache_path: Path to store the MSAL token cache
            redirect_uri: OAuth redirect URI (must match Azure AD app registration)
        """
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.client_secret = client_secret
        self.token_cache_path = Path(token_cache_path)
        self.redirect_uri = redirect_uri
        self._token_cache: Optional[msal.SerializableTokenCache] = None
        self._app: Optional[msal.ConfidentialClientApplication] = None
        self._pending_auth_state: Optional[str] = None

        # Initialize on construction
        self._initialize()

    def _initialize(self):
        """Initialize MSAL application and load token cache."""
        self._token_cache = msal.SerializableTokenCache()

        # Load existing cache if available
        if self.token_cache_path.exists():
            try:
                cache_data = self.token_cache_path.read_text()
                self._token_cache.deserialize(cache_data)
                logger.info(f"Loaded token cache from {self.token_cache_path}")
            except Exception as e:
                logger.warning(f"Could not load token cache: {e}")

        # Create MSAL confidential client application
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self._app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=authority,
            token_cache=self._token_cache,
        )

    def _save_token_cache(self):
        """Save token cache to file if it has changed."""
        if self._token_cache and self._token_cache.has_state_changed:
            try:
                # Ensure parent directory exists
                self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.token_cache_path.write_text(self._token_cache.serialize())
                logger.info(f"Saved token cache to {self.token_cache_path}")
            except Exception as e:
                logger.error(f"Failed to save token cache: {e}")

    def get_accounts(self) -> list:
        """Get all cached accounts."""
        if not self._app:
            return []
        return self._app.get_accounts()

    def is_authenticated(self) -> bool:
        """Check if we have a valid cached token."""
        accounts = self.get_accounts()
        if not accounts:
            return False

        # Try to get a token silently to verify the cache is valid
        result = self._app.acquire_token_silent(
            scopes=self.SCOPES,
            account=accounts[0]
        )
        return result is not None and "access_token" in result

    def get_auth_status(self) -> dict:
        """
        Get current authentication status.

        Returns:
            Dict with 'authenticated', 'user_email', 'user_name' fields
        """
        accounts = self.get_accounts()
        if not accounts:
            return {
                "authenticated": False,
                "user_email": None,
                "user_name": None,
            }

        account = accounts[0]
        # Try to verify the token is still valid
        result = self._app.acquire_token_silent(
            scopes=self.SCOPES,
            account=account
        )

        if result and "access_token" in result:
            return {
                "authenticated": True,
                "user_email": account.get("username"),
                "user_name": account.get("name"),
            }
        else:
            return {
                "authenticated": False,
                "user_email": None,
                "user_name": None,
                "error": result.get("error_description") if result else "Token expired",
            }

    def get_authorization_url(self) -> dict:
        """
        Generate OAuth authorization URL for user to visit.

        Returns:
            Dict with 'auth_url' and 'state' for CSRF protection
        """
        self._pending_auth_state = secrets.token_urlsafe(32)

        auth_url = self._app.get_authorization_request_url(
            scopes=self.SCOPES,
            state=self._pending_auth_state,
            redirect_uri=self.redirect_uri,
        )

        return {
            "auth_url": auth_url,
            "state": self._pending_auth_state,
        }

    def complete_auth_flow(self, auth_code: str, state: str) -> dict:
        """
        Complete OAuth flow by exchanging authorization code for tokens.

        Args:
            auth_code: Authorization code from callback
            state: State parameter for CSRF verification

        Returns:
            Dict with 'success', 'user_email', 'user_name', or 'error'
        """
        # Verify state matches
        if state != self._pending_auth_state:
            return {
                "success": False,
                "error": "State mismatch - possible CSRF attack",
            }

        # Clear pending state
        self._pending_auth_state = None

        # Exchange code for token
        result = self._app.acquire_token_by_authorization_code(
            code=auth_code,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri,
        )

        if "access_token" in result:
            # Save the token cache
            self._save_token_cache()

            # Get account info
            accounts = self.get_accounts()
            account = accounts[0] if accounts else {}

            return {
                "success": True,
                "user_email": account.get("username"),
                "user_name": account.get("name"),
            }
        else:
            return {
                "success": False,
                "error": result.get("error_description", result.get("error", "Unknown error")),
            }

    async def get_access_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Access token string, or None if not authenticated
        """
        accounts = self.get_accounts()
        if not accounts:
            logger.warning("No cached accounts - authentication required")
            return None

        # Try to get token silently (with auto-refresh)
        result = self._app.acquire_token_silent(
            scopes=self.SCOPES,
            account=accounts[0]
        )

        if result and "access_token" in result:
            # Save cache in case refresh token was updated
            self._save_token_cache()
            return result["access_token"]
        else:
            error = result.get("error_description") if result else "Unknown error"
            logger.warning(f"Could not acquire token silently: {error}")
            return None

    def logout(self):
        """Clear all cached tokens and accounts."""
        accounts = self.get_accounts()
        for account in accounts:
            self._app.remove_account(account)

        # Clear the cache file
        if self.token_cache_path.exists():
            try:
                self.token_cache_path.unlink()
                logger.info("Cleared token cache")
            except Exception as e:
                logger.error(f"Failed to clear token cache: {e}")

        # Reinitialize with empty cache
        self._initialize()
