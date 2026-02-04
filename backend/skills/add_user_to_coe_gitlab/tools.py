"""
Add User to CoE GitLab skill tools.

These tools help add users to CoE (Center of Excellence) GitLab projects by:
1. Resolving missing emails via MS Graph directory lookup
2. Creating IAM accounts in LAM (LDAP Account Manager)
3. Creating GitLab user accounts (linked to LDAP)
4. Adding users to GitLab projects

Each operation is a separate tool for maximum flexibility and robustness.
"""

import asyncio
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Optional

import yaml
from langchain_core.tools import tool

from utils.logging import get_logger

# Helper to import sibling modules since skills are loaded via importlib (not as packages)
_SKILL_DIR = Path(__file__).parent


def _import_skill_module(module_name: str):
    """Import a module from the skill directory without relative imports."""
    module_path = _SKILL_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


logger = get_logger(__name__)


def _load_skill_config() -> dict:
    """Load skill configuration from config.yaml."""
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)

    # Fall back to example config if config.yaml doesn't exist
    example_path = Path(__file__).parent / "config.yaml.example"
    if example_path.exists():
        logger.warning("Using config.yaml.example - copy to config.yaml and customize")
        with open(example_path) as f:
            return yaml.safe_load(f)

    return {"defaults": {}, "credentials": {}, "batch": {}}


def _get_credentials() -> dict:
    """
    Get credentials from config or environment variables.

    Supports two modes:
    1. Direct credentials in config.yaml (convenient for local dev):
       credentials:
         lam_username: "myuser"
         lam_password: "mypass"

    2. Environment variable names in config (more secure):
       credentials:
         lam_username_env: "LAM_USERNAME"  # reads os.environ["LAM_USERNAME"]
         lam_password_env: "LAM_PASSWORD"
    """
    config = _load_skill_config()
    creds = config.get("credentials", {})

    def get_cred(direct_key: str, env_key: str, default_env: str) -> str | None:
        # First check for direct credential in config
        if direct_key in creds:
            return creds[direct_key]
        # Then try environment variable (name from config or default)
        env_var_name = creds.get(env_key, default_env)
        return os.environ.get(env_var_name)

    return {
        "lam_username": get_cred("lam_username", "lam_username_env", "LAM_USERNAME"),
        "lam_password": get_cred("lam_password", "lam_password_env", "LAM_PASSWORD"),
        "gitlab_token": get_cred("gitlab_token", "gitlab_token_env", "GITLAB_PERSONAL_TOKEN"),
    }


def _get_ssl_config() -> dict[str, any]:
    """Get SSL configuration from config.yaml."""
    config = _load_skill_config()
    ssl_config = config.get("ssl", {})
    return {
        "verify_ssl": ssl_config.get("verify_ssl", True),
        "ca_bundle": ssl_config.get("ca_bundle"),
    }


def _get_gitlab_auth() -> tuple[dict[str, any], tuple[str, str] | None]:
    """
    Get GitLab authentication configuration.

    Returns a tuple of (ssl_config, basic_auth) ready for use with GitLab API calls.
    Basic auth is needed when GitLab is behind an authenticated proxy.

    Returns:
        (ssl_config, basic_auth): SSL config dict and optional (username, password) tuple
    """
    creds = _get_credentials()
    ssl_config = _get_ssl_config()

    basic_auth = None
    if creds.get("lam_username") and creds.get("lam_password"):
        basic_auth = (creds["lam_username"], creds["lam_password"])

    return ssl_config, basic_auth


def _validate_email(email: str) -> bool:
    """Validate email address format."""
    try:
        from email_validator import validate_email
        validate_email(email, check_deliverability=False)
        return True
    except Exception:
        # Fall back to basic regex if email_validator not available
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))


def _sanitize_username(username: str, allow_hyphen: bool = True) -> str:
    """
    Sanitize a username to ensure it's valid for Unix/LDAP/GitLab.

    Valid Unix usernames typically:
    - Start with a letter or underscore
    - Contain only lowercase letters, digits, underscores, hyphens
    - Are limited to 32 characters

    Args:
        username: Raw username string (e.g., from mail_nickname or name)
        allow_hyphen: If True, hyphens are preserved. If False, they're removed.
                      Use False when generating from names (first_initial + lastname).

    Returns:
        Sanitized username safe for Unix systems, or empty string if input
        contains no valid characters.
    """
    import unicodedata

    if not username:
        return ""

    # Normalize unicode (é -> e, ü -> u, etc.)
    normalized = unicodedata.normalize("NFKD", username)
    # Remove non-ASCII characters (accents become separate chars after NFKD)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    # Keep only valid username characters: letters, digits, underscore, and optionally hyphen
    pattern = r"[^a-zA-Z0-9_-]" if allow_hyphen else r"[^a-zA-Z0-9_]"
    sanitized = re.sub(pattern, "", ascii_only).lower()

    # Ensure username starts with a letter or underscore (Unix requirement)
    if sanitized and not sanitized[0].isalpha() and sanitized[0] != "_":
        sanitized = "_" + sanitized

    # Limit to 32 characters (common LDAP/GitLab limit)
    return sanitized[:32]


@tool
async def resolve_participant_email(name: str) -> str:
    """
    Look up an email address and login name for a person using MS Graph directory search.

    This calls the ms_graph MCP server's search_people tool which uses the User.Read.All
    permission to search the organization directory.

    Returns the mail_nickname field which should be used as the Unix username
    during IAM account creation.

    Args:
        name: The person's name to look up

    Returns:
        JSON with lookup results:
        - found: bool
        - email: email address
        - display_name: full display name
        - mail_nickname: short login name (use this as Unix username)
        - first_name, last_name: parsed from display_name
        - error: error message if not found
    """
    from mcp_client import mcp_manager

    try:
        result = await mcp_manager.call_mcp_tool(
            server_name="ms_graph",
            tool_name="search_people",  # Uses User.Read.All endpoint
            arguments={"query": name, "limit": 1},
        )

        # Parse the result - MCP may return JSON string or dict
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass

        # Handle list response (search_people returns a list)
        if isinstance(result, list):
            if len(result) > 0:
                user = result[0]
                display_name = user.get("display_name", "")
                # Use givenName/surname from MS Graph (preferred)
                # Fall back to parsing display_name only if those aren't available
                first_name = user.get("given_name", "")
                last_name = user.get("surname", "")
                if not first_name and not last_name and display_name:
                    # Fallback: parse from display_name (handles "First Last" format)
                    name_parts = display_name.split(" ", 1)
                    first_name = name_parts[0] if len(name_parts) > 0 else ""
                    last_name = name_parts[1] if len(name_parts) > 1 else ""

                return json.dumps({
                    "found": True,
                    "email": user.get("email", ""),
                    "display_name": display_name,
                    "mail_nickname": user.get("mail_nickname", ""),
                    "first_name": first_name,
                    "last_name": last_name,
                    "job_title": user.get("job_title", ""),
                    "name_searched": name,
                })
            else:
                return json.dumps({
                    "found": False,
                    "error": f"No user found for '{name}' in directory",
                    "name_searched": name,
                    "next_action": f"Ask the user to provide the email address for {name}",
                })

        # Handle dict response (error or single result)
        if isinstance(result, dict):
            if "error" in result:
                return json.dumps({
                    "found": False,
                    "error": result["error"],
                    "name_searched": name,
                    "next_action": f"Ask the user to provide the email address for {name}",
                })
            # Single user result
            if result.get("found") or result.get("email"):
                return json.dumps(result)

        return json.dumps({
            "found": False,
            "error": "Unexpected response format from MS Graph lookup",
            "name_searched": name,
            "next_action": f"Ask the user to provide the email address for {name}",
        })

    except Exception as e:
        logger.error(f"Error calling ms_graph-search_people: {e}", extra={"name": name, "error": str(e)})
        return json.dumps({
            "found": False,
            "error": str(e),
            "name_searched": name,
            "next_action": f"The ms_graph MCP server may not be available. Ask the user to provide the email address for {name}.",
        })


@tool
async def create_iam_account(
    email: str,
    first_name: str,
    last_name: str,
    mail_nickname: Optional[str] = None,
    username: Optional[str] = None,
    lam_url: Optional[str] = None,
) -> str:
    """
    Create a single IAM account in LAM (LDAP Account Manager).

    This uses browser automation to interact with the LAM web interface.
    SSO/MFA may be required - the browser will wait for manual completion.

    Args:
        email: User's email address (required)
        first_name: User's first name
        last_name: User's last name
        mail_nickname: The mailNickname from MS Graph lookup (preferred for username).
                       This is the short corporate login (e.g., "dkuehlwe") and will be
                       converted to lowercase for the Unix username.
        username: Explicit username override (optional, takes precedence over mail_nickname)
        lam_url: Override the default LAM URL from config

    Username priority:
    1. Explicit username parameter (if provided)
    2. mail_nickname.lower() from MS Graph (if provided)
    3. Generated: first_initial + lastname (fallback)

    Returns:
        JSON with:
        - success: bool
        - username: the created username
        - error: error message if failed
        - next_action: suggested next step for the agent
    """
    # Import sibling module
    lam_automation = _import_skill_module("lam_automation")
    create_lam_account_impl = lam_automation.create_lam_account

    config = _load_skill_config()
    defaults = config.get("defaults", {})
    batch_config = config.get("batch", {})

    # Get URL and credentials
    lam_url = lam_url or defaults.get("lam_url")
    creds = _get_credentials()

    # Validate inputs
    if not email or not _validate_email(email):
        return json.dumps({
            "success": False,
            "error": f"Invalid email address format: '{email}'",
            "email_provided": email,
            "next_action": "Ask the user to provide a valid email address for this participant.",
        })

    if not creds.get("lam_username") or not creds.get("lam_password"):
        return json.dumps({
            "success": False,
            "error": "LAM credentials not configured",
            "next_action": "This is a configuration issue. Tell the user: 'LAM credentials are not configured. Please set LAM_USERNAME and LAM_PASSWORD environment variables or add them to the skill config.yaml.'",
        })

    # Determine username with priority: explicit > mail_nickname
    if not username:
        if mail_nickname:
            # Use mail_nickname from MS Graph (sanitized for Unix compatibility)
            username = _sanitize_username(mail_nickname)
            if not username:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid mail_nickname '{mail_nickname}' - contains no valid username characters",
                    "mail_nickname_provided": mail_nickname,
                    "next_action": "The mail_nickname from MS Graph is invalid. Ask the user to provide a username manually.",
                })
            logger.info(f"Using mail_nickname as username: {username} (sanitized from: {mail_nickname})")
        else:
            # No username and no mail_nickname - ask the user
            return json.dumps({
                "success": False,
                "error": "Username required: no mail_nickname provided",
                "next_action": "Use resolve_participant_email first to get the mail_nickname from MS Graph, or ask the user to provide the username directly.",
            })

    # Prepare user data
    user_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "username": username,
    }

    # No retry logic - the pre-check in lam_automation.py prevents duplicates
    # Retrying is dangerous as it can create duplicate accounts
    try:
        result = await create_lam_account_impl(
            lam_url=lam_url,
            admin_username=creds["lam_username"],
            admin_password=creds["lam_password"],
            user_data=user_data,
            headless=False,  # SSO requires visible browser for MFA
        )

        if result.get("success"):
            created_username = result.get("username", username)
            already_exists = result.get("already_exists", False)
            summary = f"IAM account for {created_username} already exists (this is fine)." if already_exists else f"IAM account created successfully for {first_name} {last_name}."
            return json.dumps({
                "success": True,
                "already_exists": already_exists,
                "username": created_username,
                "email": email,
                "summary": summary,
                "next_action": f"IAM account ready. Now call create_gitlab_user_account with email='{email}', username='{created_username}', display_name='{first_name} {last_name}'.",
            })
        else:
            error = result.get("error", "Unknown error")
            return json.dumps({
                "success": False,
                "username": username,
                "email": email,
                "error": error,
                "next_action": f"IAM account creation failed. Error: {error}. Ask the user if they want to retry or skip to GitLab user creation.",
            })

    except Exception as e:
        logger.error(f"IAM account creation failed: {e}")
        return json.dumps({
            "success": False,
            "username": username,
            "email": email,
            "error": str(e),
            "next_action": f"IAM account creation failed with exception. Ask the user if they want to retry.",
        })


@tool
async def create_gitlab_user_account(
    email: str,
    username: str,
    display_name: str,
    gitlab_url: Optional[str] = None,
    max_retries: int = 2,
) -> str:
    """
    Create a GitLab user account linked to LDAP.

    This creates the user in GitLab and links it to their LDAP account for SSO.
    The user won't need a GitLab password - they'll authenticate via LDAP.

    IMPORTANT: Call this AFTER create_iam_account succeeds, using the same username.

    Args:
        email: User's email address (must match IAM account)
        username: GitLab username (should match IAM username for consistency)
        display_name: User's display name (e.g., "John Smith")
        gitlab_url: Override the default GitLab URL from config
        max_retries: Number of retry attempts on failure (default: 2)

    Returns:
        JSON with:
        - success: bool
        - user_id: GitLab user ID if created
        - username: the username
        - error: error message if failed
        - blocked: true if user exists but is blocked (needs admin intervention)
    """
    # Import sibling module
    gitlab_client = _import_skill_module("gitlab_client")
    create_gitlab_user_impl = gitlab_client.create_gitlab_user
    search_user_by_email = gitlab_client.search_user_by_email
    check_gitlab_connection = gitlab_client.check_gitlab_connection

    config = _load_skill_config()
    defaults = config.get("defaults", {})
    batch_config = config.get("batch", {})

    # Get URL and credentials
    gitlab_url = gitlab_url or defaults.get("gitlab_url")
    creds = _get_credentials()
    ssl_config, basic_auth = _get_gitlab_auth()

    # Validate inputs
    if not email or not _validate_email(email):
        return json.dumps({
            "success": False,
            "error": f"Invalid email address format: '{email}'",
            "email_provided": email,
            "next_action": "Ask the user to provide a valid email address.",
        })

    if not username:
        return json.dumps({
            "success": False,
            "error": "Username is required but was not provided",
            "next_action": "The username should come from the create_iam_account result. If IAM was skipped, ask the user for the username.",
        })

    if not creds.get("gitlab_token"):
        return json.dumps({
            "success": False,
            "error": "GitLab token not configured",
            "next_action": "This is a configuration issue. Tell the user: 'GitLab API token is not configured. Please set GITLAB_PERSONAL_TOKEN environment variable or add gitlab_token to the skill config.yaml.'",
        })

    # Check GitLab connection first
    connection_check = await check_gitlab_connection(
        gitlab_url, creds["gitlab_token"],
        verify_ssl=ssl_config["verify_ssl"],
        ca_bundle=ssl_config["ca_bundle"],
        basic_auth=basic_auth
    )
    if not connection_check.get("connected"):
        return json.dumps({
            "success": False,
            "error": f"Cannot connect to GitLab: {connection_check.get('error', 'Unknown error')}",
            "gitlab_url": gitlab_url,
            "next_action": "GitLab connection failed. This could be a network issue or invalid token. Tell the user about the connection error and suggest checking the GitLab URL and token configuration.",
        })

    # Check if user already exists
    existing_user = await search_user_by_email(
        gitlab_url, creds["gitlab_token"], email,
        verify_ssl=ssl_config["verify_ssl"],
        ca_bundle=ssl_config["ca_bundle"],
        basic_auth=basic_auth
    )

    if existing_user:
        # User exists - this is actually success, proceed to next step
        return json.dumps({
            "success": True,
            "already_exists": True,
            "user_id": existing_user["id"],
            "username": existing_user["username"],
            "email": email,
            "note": "User already exists in GitLab",
            "next_action": f"GitLab user already exists. Proceed to add_user_to_gitlab_project with user_identifier='{email}'.",
        })

    # LDAP linking disabled - let user's first SSO login establish the connection
    # This avoids issues where GitLab LDAP sync blocks users that were created
    # via API but haven't logged in yet.
    # If you need LDAP linking, set ldap_dn_template in config.yaml
    ldap_dn = None
    ldap_dn_template = defaults.get("ldap_dn_template")
    if ldap_dn_template:
        ldap_dn = ldap_dn_template.format(username=username)

    # Retry logic
    max_retries = min(max_retries, batch_config.get("max_retries", 2))
    last_error = None
    retries_used = 0

    for attempt in range(max_retries + 1):
        try:
            result = await create_gitlab_user_impl(
                gitlab_url=gitlab_url,
                token=creds["gitlab_token"],
                email=email,
                username=username,
                name=display_name,
                ldap_dn=ldap_dn,
                verify_ssl=ssl_config["verify_ssl"],
                ca_bundle=ssl_config["ca_bundle"],
                basic_auth=basic_auth,
            )

            if result.get("success"):
                created_username = result.get("username", username)
                return json.dumps({
                    "success": True,
                    "user_id": result.get("id"),
                    "username": created_username,
                    "email": email,
                    "note": result.get("note"),
                    "retries_used": retries_used,
                    "summary": f"GitLab user account created successfully for {display_name} ({created_username}).",
                    "next_action": f"GitLab user created. Now call add_user_to_gitlab_project with user_identifier='{email}'.",
                })
            else:
                last_error = result.get("error", "Unknown error")
                # Check for blocked user indication
                if "blocked" in last_error.lower():
                    return json.dumps({
                        "success": False,
                        "username": username,
                        "email": email,
                        "error": last_error,
                        "blocked": True,
                        "retries_used": retries_used,
                        "next_action": f"STOP: User '{username}' is BLOCKED in GitLab. Tell the user: 'The user {display_name} ({username}) is blocked in GitLab. An admin must unblock them at: GitLab Admin > Users > search for '{username}' > Edit > Unblock.' Do NOT retry - this requires manual admin intervention.",
                    })

        except Exception as e:
            last_error = str(e)
            logger.error(f"GitLab user creation attempt {attempt + 1} failed: {e}", extra={"username": username, "email": email, "attempt": attempt + 1})

        retries_used = attempt + 1
        if attempt < max_retries:
            await asyncio.sleep(min(2 ** attempt, 30))  # Cap at 30 seconds

    return json.dumps({
        "success": False,
        "username": username,
        "email": email,
        "error": last_error,
        "retries_used": retries_used,
        "next_action": f"GitLab user creation failed after {retries_used} attempts. Report the error to the user: '{last_error}'. Ask if they want to retry or if an admin should check the GitLab system.",
    })


@tool
async def search_gitlab_project(
    search_query: str,
    gitlab_url: Optional[str] = None,
) -> str:
    """
    Search for GitLab projects by name.

    Use this tool to find the exact project path when you only know a partial name
    (e.g., "cohort2" to find "dkuehlwe/2026-genaitraining-cohort2").

    Args:
        search_query: Project name or partial name to search for (e.g., "cohort2", "training")

    Returns:
        JSON with:
        - success: bool
        - projects: list of matching projects with path_with_namespace, name, description
        - count: number of matches found
        - error: error message if failed

    Example:
        search_gitlab_project("cohort2")
        -> {"success": true, "projects": [{"path_with_namespace": "dkuehlwe/2026-genaitraining-cohort2", ...}]}
    """
    # Import sibling module
    gitlab_client = _import_skill_module("gitlab_client")
    search_gitlab_projects = gitlab_client.search_gitlab_projects

    config = _load_skill_config()
    defaults = config.get("defaults", {})

    # Get URL and credentials
    gitlab_url = gitlab_url or defaults.get("gitlab_url")
    creds = _get_credentials()
    ssl_config, basic_auth = _get_gitlab_auth()

    if not creds.get("gitlab_token"):
        return json.dumps({
            "success": False,
            "error": "GitLab token not configured",
            "next_action": "This is a configuration issue. Tell the user: 'GitLab API token is not configured.'",
        })

    try:
        result = await search_gitlab_projects(
            gitlab_url=gitlab_url,
            token=creds["gitlab_token"],
            search_query=search_query,
            membership=True,  # Only projects user has access to
            limit=10,
            verify_ssl=ssl_config["verify_ssl"],
            ca_bundle=ssl_config["ca_bundle"],
            basic_auth=basic_auth,
        )

        if not result.get("success"):
            return json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error"),
                "search_query": search_query,
                "next_action": "GitLab project search failed. Ask the user for the exact project path.",
            })

        projects = result.get("projects", [])
        if projects:
            return json.dumps({
                "success": True,
                "count": len(projects),
                "projects": projects,
                "search_query": search_query,
                "next_action": f"Found {len(projects)} project(s). Use the 'path_with_namespace' value when calling add_user_to_gitlab_project.",
            })
        else:
            return json.dumps({
                "success": True,
                "count": 0,
                "projects": [],
                "search_query": search_query,
                "next_action": f"No projects found matching '{search_query}'. Ask the user for the correct project name or path.",
            })

    except Exception as e:
        logger.error(f"GitLab project search failed: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "search_query": search_query,
            "next_action": "GitLab project search failed. Ask the user for the exact project path.",
        })


@tool
async def add_user_to_gitlab_project(
    user_identifier: str,
    gitlab_project: Optional[str] = None,
    access_level: Optional[str] = None,
    gitlab_url: Optional[str] = None,
    max_retries: int = 2,
) -> str:
    """
    Add a user to a GitLab project with the specified access level.

    This is the final step after IAM and GitLab user accounts are created.
    The user will gain access to the training repository.

    Args:
        user_identifier: Email address or username of the user to add
        gitlab_project: Project path (e.g., "group/project-name") OR project name to search for.
                        If the value contains "/", it's treated as an exact path.
                        If no "/", it searches for matching projects and uses the first result.
                        Uses config default if not specified.
        access_level: Access level: guest, reporter, developer, maintainer. Uses config default if not specified.
        gitlab_url: Override the default GitLab URL from config
        max_retries: Number of retry attempts on failure (default: 2)

    Returns:
        JSON with:
        - success: bool
        - project: the project path
        - access_level: the granted access level
        - error: error message if failed
        - already_member: true if user was already a member
    """
    # Import sibling module
    gitlab_client = _import_skill_module("gitlab_client")
    add_gitlab_member = gitlab_client.add_gitlab_member
    check_gitlab_connection = gitlab_client.check_gitlab_connection
    search_gitlab_projects = gitlab_client.search_gitlab_projects

    config = _load_skill_config()
    defaults = config.get("defaults", {})
    batch_config = config.get("batch", {})

    # Get URL and credentials
    gitlab_url = gitlab_url or defaults.get("gitlab_url")
    gitlab_project = gitlab_project or defaults.get("gitlab_project")
    access_level = access_level or defaults.get("gitlab_access_level", "developer")
    creds = _get_credentials()
    ssl_config, basic_auth = _get_gitlab_auth()

    # Validate inputs
    if not user_identifier:
        return json.dumps({
            "success": False,
            "error": "user_identifier is required (email or username)",
            "next_action": "Provide either the user's email address or GitLab username from the previous create_gitlab_user_account result.",
        })

    if not gitlab_project:
        return json.dumps({
            "success": False,
            "error": "gitlab_project is required but not configured",
            "next_action": "This is a configuration issue. Tell the user: 'The GitLab project path is not configured. Please add gitlab_project to the skill config.yaml (e.g., \"group/project-name\").'",
        })

    if not creds.get("gitlab_token"):
        return json.dumps({
            "success": False,
            "error": "GitLab token not configured",
            "next_action": "This is a configuration issue. Tell the user: 'GitLab API token is not configured. Please set GITLAB_PERSONAL_TOKEN environment variable or add gitlab_token to the skill config.yaml.'",
        })

    # If gitlab_project doesn't contain "/", treat it as a search query
    if "/" not in gitlab_project:
        logger.info(f"Searching for GitLab project matching: {gitlab_project}")
        try:
            result = await search_gitlab_projects(
                gitlab_url=gitlab_url,
                token=creds["gitlab_token"],
                search_query=gitlab_project,
                membership=True,
                limit=5,
                verify_ssl=ssl_config["verify_ssl"],
                ca_bundle=ssl_config["ca_bundle"],
                basic_auth=basic_auth,
            )
            if not result.get("success"):
                return json.dumps({
                    "success": False,
                    "error": f"Failed to search for project '{gitlab_project}': {result.get('error', 'Unknown error')}",
                    "next_action": "Project search failed. Provide the exact project path instead (e.g., 'group/project-name').",
                })
            projects = result.get("projects", [])
            if projects:
                # Use the first matching project
                resolved_project = projects[0]["path_with_namespace"]
                logger.info(f"Resolved project '{gitlab_project}' to '{resolved_project}'")
                gitlab_project = resolved_project
            else:
                return json.dumps({
                    "success": False,
                    "error": f"No project found matching '{gitlab_project}'",
                    "search_query": gitlab_project,
                    "next_action": f"No projects found matching '{gitlab_project}'. Use search_gitlab_project to find available projects, or provide the exact project path (e.g., 'group/project-name').",
                })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to search for project '{gitlab_project}': {str(e)}",
                "next_action": "Project search failed. Provide the exact project path instead (e.g., 'group/project-name').",
            })

    # Check GitLab connection first
    connection_check = await check_gitlab_connection(
        gitlab_url, creds["gitlab_token"],
        verify_ssl=ssl_config["verify_ssl"],
        ca_bundle=ssl_config["ca_bundle"],
        basic_auth=basic_auth
    )
    if not connection_check.get("connected"):
        return json.dumps({
            "success": False,
            "error": f"Cannot connect to GitLab: {connection_check.get('error', 'Unknown error')}",
            "gitlab_url": gitlab_url,
            "next_action": "GitLab connection failed. Tell the user about the connection error and suggest checking network connectivity and GitLab token validity.",
        })

    # Retry logic
    max_retries = min(max_retries, batch_config.get("max_retries", 2))
    last_error = None
    retries_used = 0

    for attempt in range(max_retries + 1):
        try:
            result = await add_gitlab_member(
                gitlab_url=gitlab_url,
                token=creds["gitlab_token"],
                project_path=gitlab_project,
                user_identifier=user_identifier,
                access_level=access_level,
                verify_ssl=ssl_config["verify_ssl"],
                ca_bundle=ssl_config["ca_bundle"],
                basic_auth=basic_auth,
            )

            if result.get("success"):
                response = {
                    "success": True,
                    "user": user_identifier,
                    "project": gitlab_project,
                    "access_level": access_level,
                    "retries_used": retries_used,
                    "summary": f"User '{user_identifier}' now has {access_level} access to project '{gitlab_project}'.",
                }
                if result.get("note"):
                    response["already_member"] = True
                    response["note"] = result["note"]
                    response["summary"] = f"User '{user_identifier}' was already a member of project '{gitlab_project}'."
                return json.dumps(response)
            else:
                last_error = result.get("error", "Unknown error")
                # Check for user not found (might need GitLab user creation first)
                if "not found" in last_error.lower():
                    return json.dumps({
                        "success": False,
                        "user": user_identifier,
                        "project": gitlab_project,
                        "error": last_error,
                        "user_not_found": True,
                        "retries_used": retries_used,
                        "next_action": f"User '{user_identifier}' was not found in GitLab. You must call create_gitlab_user_account first before adding them to a project. Go back and create the GitLab user account.",
                    })
                # Check for blocked user
                if "blocked" in last_error.lower():
                    return json.dumps({
                        "success": False,
                        "user": user_identifier,
                        "project": gitlab_project,
                        "error": last_error,
                        "blocked": True,
                        "retries_used": retries_used,
                        "next_action": f"STOP: User '{user_identifier}' is BLOCKED in GitLab. Tell the user: 'This user is blocked and cannot be added to the project. An admin must unblock them at: GitLab Admin > Users > search for the user > Edit > Unblock.' Do NOT retry.",
                    })

        except Exception as e:
            last_error = str(e)
            logger.error(f"Add to project attempt {attempt + 1} failed: {e}", extra={"user": user_identifier, "project": gitlab_project, "attempt": attempt + 1})

        retries_used = attempt + 1
        if attempt < max_retries:
            await asyncio.sleep(min(2 ** attempt, 30))  # Cap at 30 seconds

    return json.dumps({
        "success": False,
        "user": user_identifier,
        "project": gitlab_project,
        "error": last_error,
        "retries_used": retries_used,
        "next_action": f"Failed to add user to project after {retries_used} attempts. Report the error to the user: '{last_error}'.",
    })


def get_tools():
    """Return all tools provided by this skill."""
    return [
        resolve_participant_email,
        create_iam_account,
        create_gitlab_user_account,
        search_gitlab_project,
        add_user_to_gitlab_project,
    ]
