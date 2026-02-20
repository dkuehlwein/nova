"""
GitLab REST API client for adding project members.

Uses the GitLab API v4 to add users as members to a project.
Reference: https://docs.gitlab.com/api/project_members/
"""

import ssl
from pathlib import Path
from typing import Optional, Union

import httpx
from urllib.parse import quote_plus

from utils.logging import get_logger

logger = get_logger(__name__)

# GitLab access level mapping
ACCESS_LEVELS = {
    "guest": 10,
    "reporter": 20,
    "developer": 30,
    "maintainer": 40,
    "owner": 50,  # Only valid for groups
}


def _get_ssl_context(
    verify_ssl: bool = True,
    ca_bundle: Optional[str] = None
) -> Union[bool, ssl.SSLContext]:
    """
    Get SSL context for httpx client.

    Args:
        verify_ssl: Whether to verify SSL certificates
        ca_bundle: Optional path to CA bundle file

    Returns:
        SSL context or boolean for httpx verify parameter
    """
    if ca_bundle and Path(ca_bundle).exists():
        # Use custom CA bundle
        ctx = ssl.create_default_context(cafile=ca_bundle)
        return ctx
    if not verify_ssl:
        logger.warning("SSL verification disabled - this is a security risk!")
    return verify_ssl


async def get_user_id_by_username(
    gitlab_url: str,
    token: str,
    username: str,
    verify_ssl: bool = True,
    ca_bundle: Optional[str] = None,
    timeout: float = 30.0,
    basic_auth: Optional[tuple[str, str]] = None,
) -> Optional[int]:
    """
    Look up a GitLab user ID by username.

    Args:
        gitlab_url: Base GitLab URL (e.g., https://gitlab.example.com)
        token: GitLab personal access token
        username: Username to look up
        verify_ssl: Whether to verify SSL certificates
        ca_bundle: Optional path to CA bundle file
        timeout: Request timeout in seconds
        basic_auth: Optional (username, password) tuple for HTTP Basic Auth
                    (needed when GitLab is behind an authenticated proxy)

    Returns:
        User ID if found, None otherwise
    """
    ssl_context = _get_ssl_context(verify_ssl, ca_bundle)
    auth = httpx.BasicAuth(*basic_auth) if basic_auth else None
    async with httpx.AsyncClient(verify=ssl_context, auth=auth) as client:
        try:
            response = await client.get(
                f"{gitlab_url}/api/v4/users",
                params={"username": username},
                headers={"PRIVATE-TOKEN": token},
                timeout=timeout,
            )
            response.raise_for_status()
            users = response.json()

            if users and len(users) > 0:
                return users[0]["id"]
            return None

        except httpx.HTTPStatusError as e:
            logger.error("GitLab API error looking up user", extra={"data": {"status_code": e.response.status_code}})
            return None
        except Exception as e:
            logger.error("Error looking up GitLab user", extra={"data": {"error": str(e)}})
            return None


async def search_user_by_email(
    gitlab_url: str,
    token: str,
    email: str,
    verify_ssl: bool = True,
    ca_bundle: Optional[str] = None,
    timeout: float = 30.0,
    basic_auth: Optional[tuple[str, str]] = None,
) -> Optional[dict]:
    """
    Search for a GitLab user by email address.

    Args:
        gitlab_url: Base GitLab URL
        token: GitLab personal access token
        email: Email to search for
        verify_ssl: Whether to verify SSL certificates
        ca_bundle: Optional path to CA bundle file
        timeout: Request timeout in seconds
        basic_auth: Optional (username, password) tuple for HTTP Basic Auth

    Returns:
        User dict with id, username, name if found, None otherwise
    """
    ssl_context = _get_ssl_context(verify_ssl, ca_bundle)
    auth = httpx.BasicAuth(*basic_auth) if basic_auth else None
    async with httpx.AsyncClient(verify=ssl_context, auth=auth) as client:
        try:
            response = await client.get(
                f"{gitlab_url}/api/v4/users",
                params={"search": email},
                headers={"PRIVATE-TOKEN": token},
                timeout=timeout,
            )
            response.raise_for_status()
            users = response.json()

            # Find exact email match
            for user in users:
                if user.get("email", "").lower() == email.lower():
                    return {
                        "id": user["id"],
                        "username": user["username"],
                        "name": user.get("name", ""),
                    }

            # If no exact match, return first result (partial match)
            if users:
                return {
                    "id": users[0]["id"],
                    "username": users[0]["username"],
                    "name": users[0].get("name", ""),
                }

            return None

        except httpx.HTTPStatusError as e:
            logger.error("GitLab API error searching user", extra={"data": {"status_code": e.response.status_code}})
            return None
        except Exception as e:
            logger.error("Error searching GitLab user", extra={"data": {"error": str(e)}})
            return None


async def add_gitlab_member(
    gitlab_url: str,
    token: str,
    project_path: str,
    user_identifier: str,
    access_level: str = "developer",
    verify_ssl: bool = True,
    ca_bundle: Optional[str] = None,
    timeout: float = 30.0,
    basic_auth: Optional[tuple[str, str]] = None,
) -> dict:
    """
    Add a member to a GitLab project.

    Args:
        gitlab_url: Base GitLab URL (e.g., https://gitlab.example.com)
        token: GitLab personal access token with api scope
        project_path: Project path (e.g., "group/project-name")
        user_identifier: Username or email of the user to add
        access_level: Access level (guest, reporter, developer, maintainer)
        verify_ssl: Whether to verify SSL certificates
        ca_bundle: Optional path to CA bundle file
        timeout: Request timeout in seconds
        basic_auth: Optional (username, password) tuple for HTTP Basic Auth
                    (needed when GitLab is behind an authenticated proxy)

    Returns:
        Dict with success status and error message if failed
        {"success": True} or {"success": False, "error": "error message"}
    """
    # Validate access level
    access_level_lower = access_level.lower()
    if access_level_lower not in ACCESS_LEVELS:
        return {
            "success": False,
            "error": f"Invalid access level: {access_level}. Valid: {list(ACCESS_LEVELS.keys())}",
        }

    access_level_num = ACCESS_LEVELS[access_level_lower]

    # URL-encode the project path for the API
    encoded_project = quote_plus(project_path)

    # First, find the user ID
    user_id = None

    # Try as email first (contains @)
    if "@" in user_identifier:
        user_info = await search_user_by_email(
            gitlab_url, token, user_identifier,
            verify_ssl=verify_ssl, ca_bundle=ca_bundle, timeout=timeout,
            basic_auth=basic_auth
        )
        if user_info:
            user_id = user_info["id"]
            logger.info(
                f"Found GitLab user by email: {user_identifier} -> {user_info['username']} (ID: {user_id})"
            )
    else:
        # Try as username
        user_id = await get_user_id_by_username(
            gitlab_url, token, user_identifier,
            verify_ssl=verify_ssl, ca_bundle=ca_bundle, timeout=timeout,
            basic_auth=basic_auth
        )
        if user_id:
            logger.info("Found GitLab user by username: (ID", extra={"data": {"user_identifier": user_identifier, "user_id": str(user_id)}})

    if not user_id:
        return {
            "success": False,
            "error": f"User not found in GitLab: {user_identifier}",
        }

    # Add the user as a project member
    ssl_context = _get_ssl_context(verify_ssl, ca_bundle)
    auth = httpx.BasicAuth(*basic_auth) if basic_auth else None
    async with httpx.AsyncClient(verify=ssl_context, auth=auth) as client:
        try:
            response = await client.post(
                f"{gitlab_url}/api/v4/projects/{encoded_project}/members",
                headers={"PRIVATE-TOKEN": token},
                data={
                    "user_id": user_id,
                    "access_level": access_level_num,
                },
                timeout=timeout,
            )

            if response.status_code == 201:
                logger.info(
                    f"Successfully added {user_identifier} to {project_path} as {access_level}"
                )
                return {"success": True}

            elif response.status_code == 409:
                # Member already exists
                logger.info("User is already a member", extra={"data": {"user_identifier": user_identifier, "project_path": project_path}})
                return {"success": True, "note": "User was already a member"}

            else:
                error_msg = response.json().get("message", response.text)
                logger.error(
                    f"Failed to add {user_identifier} to {project_path}: {response.status_code} - {error_msg}"
                )
                return {"success": False, "error": f"API error {response.status_code}: {error_msg}"}

        except httpx.HTTPStatusError as e:
            logger.error("GitLab API HTTP error", extra={"data": {"error": str(e)}})
            return {"success": False, "error": f"HTTP error: {e.response.status_code}"}

        except Exception as e:
            logger.error("Error adding GitLab member", extra={"data": {"error": str(e)}})
            return {"success": False, "error": str(e)}


async def create_gitlab_user(
    gitlab_url: str,
    token: str,
    email: str,
    username: str,
    name: str,
    ldap_dn: Optional[str] = None,
    ldap_provider: str = "ldapmain",
    verify_ssl: bool = True,
    ca_bundle: Optional[str] = None,
    timeout: float = 30.0,
    basic_auth: Optional[tuple[str, str]] = None,
) -> dict:
    """
    Create a GitLab user via the admin API.

    This is needed because GitLab doesn't automatically sync LDAP users -
    users only get created when they first log in. This function creates
    the user proactively so they can be added to projects.

    Requires admin privileges on the GitLab instance.

    Args:
        gitlab_url: Base GitLab URL
        token: GitLab personal access token with admin scope
        email: User's email address
        username: GitLab username
        name: User's display name
        ldap_dn: Optional LDAP DN to link the user to LDAP auth
        ldap_provider: LDAP provider name (default: "ldapmain")
        verify_ssl: Whether to verify SSL certificates
        ca_bundle: Optional path to CA bundle file
        timeout: Request timeout in seconds
        basic_auth: Optional (username, password) tuple for HTTP Basic Auth

    Returns:
        Dict with success status and user info or error
    """
    import secrets
    import string

    ssl_context = _get_ssl_context(verify_ssl, ca_bundle)
    auth = httpx.BasicAuth(*basic_auth) if basic_auth else None

    # Generate a temporary password (user will use LDAP auth anyway)
    alphabet = string.ascii_letters + string.digits
    temp_password = "".join(secrets.choice(alphabet) for _ in range(16))

    user_data = {
        "email": email,
        "username": username,
        "name": name,
        "password": temp_password,
        "skip_confirmation": True,  # Don't require email confirmation
    }

    # Link to LDAP if DN provided
    if ldap_dn:
        user_data["extern_uid"] = ldap_dn
        user_data["provider"] = ldap_provider

    async with httpx.AsyncClient(verify=ssl_context, auth=auth) as client:
        try:
            response = await client.post(
                f"{gitlab_url}/api/v4/users",
                headers={"PRIVATE-TOKEN": token},
                data=user_data,
                timeout=timeout,
            )

            if response.status_code == 201:
                user = response.json()
                user_id = user["id"]
                user_state = user.get("state", "unknown")
                logger.info("Created GitLab user: (ID: , state", extra={"data": {"username": username, "user_id": str(user_id), "user_state": user_state}})

                # If user was created in blocked state, unblock them
                # This can happen if GitLab has "User approval required" enabled
                if user_state in ("blocked", "blocked_pending_approval"):
                    logger.info("User created as , attempting to unblock...", extra={"data": {"username": username, "user_state": user_state}})
                    unblock_response = await client.post(
                        f"{gitlab_url}/api/v4/users/{user_id}/unblock",
                        headers={"PRIVATE-TOKEN": token},
                        timeout=timeout,
                    )
                    if unblock_response.status_code == 201:
                        logger.info("Successfully unblocked user", extra={"data": {"username": username}})
                    else:
                        logger.warning(
                            f"Failed to unblock user {username}: {unblock_response.status_code} - "
                            f"User may need manual activation by an admin"
                        )

                return {
                    "success": True,
                    "id": user_id,
                    "username": user["username"],
                    "email": user["email"],
                }

            elif response.status_code == 409:
                # User already exists
                logger.info("GitLab user already exists", extra={"data": {"username": username}})
                return {"success": True, "note": "User already exists"}

            else:
                error_msg = response.json().get("message", response.text)
                logger.error("Failed to create GitLab user", extra={"data": {"status_code": response.status_code, "error_msg": error_msg}})
                return {"success": False, "error": f"API error {response.status_code}: {error_msg}"}

        except httpx.HTTPStatusError as e:
            logger.error("GitLab API HTTP error", extra={"data": {"error": str(e)}})
            return {"success": False, "error": f"HTTP error: {e.response.status_code}"}

        except Exception as e:
            logger.error("Error creating GitLab user", extra={"data": {"error": str(e)}})
            return {"success": False, "error": str(e)}


async def search_gitlab_projects(
    gitlab_url: str,
    token: str,
    search_query: str,
    membership: bool = True,
    limit: int = 10,
    verify_ssl: bool = True,
    ca_bundle: Optional[str] = None,
    timeout: float = 30.0,
    basic_auth: Optional[tuple[str, str]] = None,
) -> dict[str, any]:
    """
    Search for GitLab projects by name.

    Uses: GET /api/v4/projects?search={query}&membership=true

    Args:
        gitlab_url: Base GitLab URL
        token: GitLab personal access token
        search_query: Project name or partial name to search for
        membership: If True, only return projects the user has access to (default: True)
        limit: Maximum number of results (default: 10)
        verify_ssl: Whether to verify SSL certificates
        ca_bundle: Optional path to CA bundle file
        timeout: Request timeout in seconds
        basic_auth: Optional (username, password) tuple for HTTP Basic Auth

    Returns:
        Dict with:
        - success: bool
        - projects: list of project dicts with id, path_with_namespace, name, description
        - error: error message if failed
    """
    ssl_context = _get_ssl_context(verify_ssl, ca_bundle)
    auth = httpx.BasicAuth(*basic_auth) if basic_auth else None

    params = {
        "search": search_query,
        "per_page": limit,
        "order_by": "name",
        "sort": "asc",
    }
    if membership:
        params["membership"] = "true"

    async with httpx.AsyncClient(verify=ssl_context, auth=auth) as client:
        try:
            response = await client.get(
                f"{gitlab_url}/api/v4/projects",
                params=params,
                headers={"PRIVATE-TOKEN": token},
                timeout=timeout,
            )
            response.raise_for_status()
            projects = response.json()

            results = []
            for project in projects:
                results.append({
                    "id": project["id"],
                    "path_with_namespace": project["path_with_namespace"],
                    "name": project["name"],
                    "description": project.get("description", ""),
                    "web_url": project.get("web_url", ""),
                })

            logger.info("Found projects matching ''", extra={"data": {"results_count": len(results), "search_query": search_query}})
            return {"success": True, "projects": results}

        except httpx.HTTPStatusError as e:
            logger.error("GitLab API error searching projects", extra={"data": {"status_code": e.response.status_code}})
            return {"success": False, "projects": [], "error": f"GitLab API error: {e.response.status_code}"}
        except Exception as e:
            logger.error("Error searching GitLab projects", extra={"data": {"error": str(e)}})
            return {"success": False, "projects": [], "error": str(e)}


async def check_gitlab_connection(
    gitlab_url: str,
    token: str,
    verify_ssl: bool = True,
    ca_bundle: Optional[str] = None,
    timeout: float = 10.0,
    basic_auth: Optional[tuple[str, str]] = None,
) -> dict:
    """
    Verify GitLab API connection and token validity.

    Args:
        gitlab_url: Base GitLab URL
        token: GitLab personal access token
        verify_ssl: Whether to verify SSL certificates
        ca_bundle: Optional path to CA bundle file
        timeout: Request timeout in seconds
        basic_auth: Optional (username, password) tuple for HTTP Basic Auth

    Returns:
        Dict with connection status and user info
    """
    ssl_context = _get_ssl_context(verify_ssl, ca_bundle)
    auth = httpx.BasicAuth(*basic_auth) if basic_auth else None
    async with httpx.AsyncClient(verify=ssl_context, auth=auth) as client:
        try:
            response = await client.get(
                f"{gitlab_url}/api/v4/user",
                headers={"PRIVATE-TOKEN": token},
                timeout=timeout,
            )
            response.raise_for_status()
            user = response.json()

            return {
                "connected": True,
                "username": user.get("username"),
                "name": user.get("name"),
            }

        except httpx.HTTPStatusError as e:
            return {
                "connected": False,
                "error": f"Authentication failed: {e.response.status_code}",
            }
        except Exception as e:
            return {
                "connected": False,
                "error": f"Connection failed: {str(e)}",
            }
