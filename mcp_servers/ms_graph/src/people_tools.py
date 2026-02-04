"""
People Tools - People and contact operations via MS Graph API.

Provides tools for searching people/directory and looking up contacts.
"""

import logging
from typing import Any, Dict, List, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .service import MSGraphService

logger = logging.getLogger(__name__)


class PeopleTools:
    """People and contact operations via MS Graph API."""

    def __init__(self, service: "MSGraphService"):
        """
        Initialize people tools.

        Args:
            service: MSGraphService instance for API access
        """
        self.service = service

    async def lookup_contact(self, name: str) -> Dict[str, Any]:
        """
        Look up an email address and login name for a person by name.

        Searches the organization directory using User.Read.All.
        Returns mailNickname (short login name) which is needed for GitLab integration.

        Args:
            name: The person's name to look up (e.g., "John Doe" or "John")

        Returns:
            Dict with:
            - found: True if user was found
            - email: The email address (if found)
            - display_name: The full display name
            - mail_nickname: Short login name (e.g., "jdoe") - for GitLab
            - user_principal_name: Full login (e.g., "john.doe@company.com")
            - job_title: Job title (if available)
        """
        try:
            client = await self.service.ensure_client()

            # Search directory users by displayName or mail
            # Uses User.Read.All to get mailNickname
            params = {
                "$filter": f"startswith(displayName,'{name}') or startswith(mail,'{name}')",
                "$select": "id,displayName,mail,userPrincipalName,mailNickname,jobTitle",
                "$top": 1,
            }

            response = await client.get("/users", params=params)
            response.raise_for_status()
            data = response.json()

            users = data.get("value", [])
            if users:
                user = users[0]
                return {
                    "found": True,
                    "email": user.get("mail") or user.get("userPrincipalName", ""),
                    "display_name": user.get("displayName", "Unknown"),
                    "mail_nickname": user.get("mailNickname", ""),
                    "user_principal_name": user.get("userPrincipalName", ""),
                    "job_title": user.get("jobTitle", ""),
                }

            return {
                "found": False,
                "error": f"No user found for '{name}' in directory",
            }

        except Exception as e:
            logger.error(f"Error looking up contact: {e}")
            return {"found": False, "error": f"Failed to look up contact: {str(e)}"}

    async def search_people(self, query: str, limit: int = 10) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Search organization directory for people.

        Uses the /users endpoint with User.Read.All to get mailNickname (login name).
        This is the primary search method for finding people and their login names.

        Args:
            query: Search query (name or email prefix)
            limit: Maximum number of results (default: 10)

        Returns:
            List of users with displayName, email, mailNickname (login), jobTitle, department
        """
        try:
            client = await self.service.ensure_client()

            # Use the /users endpoint with filter to get mailNickname
            # User.Read.All is required for this endpoint
            params = {
                "$filter": f"startswith(displayName,'{query}') or startswith(mail,'{query}')",
                "$select": "id,displayName,givenName,surname,mail,userPrincipalName,mailNickname,jobTitle,department,companyName",
                "$top": limit,
            }

            response = await client.get("/users", params=params)
            response.raise_for_status()
            data = response.json()

            results = []
            for user in data.get("value", []):
                results.append({
                    "display_name": user.get("displayName", "Unknown"),
                    "given_name": user.get("givenName", ""),
                    "surname": user.get("surname", ""),
                    "email": user.get("mail") or user.get("userPrincipalName", ""),
                    "mail_nickname": user.get("mailNickname", ""),
                    "user_principal_name": user.get("userPrincipalName", ""),
                    "job_title": user.get("jobTitle", ""),
                    "department": user.get("department", ""),
                    "company": user.get("companyName", ""),
                })

            return results

        except Exception as e:
            logger.error(f"Error searching people: {e}")
            return {"error": f"Failed to search people: {str(e)}"}

    async def get_user_profile(self, user_id: str = "me") -> Dict[str, Any]:
        """
        Get user profile information.

        Args:
            user_id: User ID or "me" for the authenticated user (default: "me")

        Returns:
            User profile with displayName, mail, mailNickname (login), jobTitle, department, etc.
        """
        try:
            client = await self.service.ensure_client()

            # Build endpoint
            if user_id == "me":
                endpoint = "/me"
            else:
                endpoint = f"/users/{user_id}"

            # Select relevant fields including mailNickname
            params = {
                "$select": "id,displayName,mail,userPrincipalName,mailNickname,jobTitle,department,officeLocation,mobilePhone,companyName",
            }

            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            user = response.json()

            return {
                "id": user.get("id", ""),
                "display_name": user.get("displayName", "Unknown"),
                "email": user.get("mail") or user.get("userPrincipalName", ""),
                "mail_nickname": user.get("mailNickname", ""),
                "user_principal_name": user.get("userPrincipalName", ""),
                "job_title": user.get("jobTitle", ""),
                "department": user.get("department", ""),
                "office_location": user.get("officeLocation", ""),
                "mobile_phone": user.get("mobilePhone", ""),
                "company": user.get("companyName", ""),
            }

        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return {"error": f"Failed to get user profile: {str(e)}"}

