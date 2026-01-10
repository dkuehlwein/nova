"""
GenAI Training Onboarding skill tools.

These tools help onboard training participants by:
1. Resolving missing emails via Outlook contact lookup
2. Creating IAM accounts in LAM
3. Adding members to GitLab repositories

Note: Input parsing is done by the LLM directly (not a tool) since
LLMs naturally handle mixed formats (names/emails/CSV/etc).
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


def _get_ssl_config() -> dict:
    """Get SSL configuration from config.yaml."""
    config = _load_skill_config()
    ssl_config = config.get("ssl", {})
    return {
        "verify_ssl": ssl_config.get("verify_ssl", True),
        "ca_bundle": ssl_config.get("ca_bundle"),
    }


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


# Note: build_participant_list and related parsing helpers were removed.
# LLMs naturally parse mixed input formats (names/emails/mixed) into structured data.
# Having parsing as a tool added unnecessary complexity and latency.


@tool
async def resolve_participant_email(name: str) -> str:
    """
    Look up an email address for a name using Outlook contact search.

    This calls the outlook_mac MCP server's lookup_contact tool.
    If the tool is not available, it will return an error.

    Args:
        name: The person's name to look up

    Returns:
        JSON with lookup results: found, email, display_name, or error
    """
    from mcp_client import mcp_manager

    try:
        result = await mcp_manager.call_mcp_tool(
            server_name="outlook_mac",
            tool_name="outlook_lookup_contact",  # Prefixed per ADR-019
            arguments={"name": name},
        )

        if isinstance(result, str):
            try:
                return result  # Already JSON string
            except json.JSONDecodeError:
                return json.dumps({"found": True, "result": result})

        if isinstance(result, dict):
            if "error" in result:
                return json.dumps(
                    {
                        "found": False,
                        "error": result["error"],
                        "suggestion": f"Ask the user for {name}'s email address",
                    }
                )
            return json.dumps(result)

        return json.dumps({"found": False, "error": "Unexpected response format"})

    except Exception as e:
        logger.error(f"Error calling outlook_lookup_contact: {e}")
        return json.dumps(
            {
                "found": False,
                "error": str(e),
                "suggestion": f"The outlook_lookup_contact tool may not be available. Ask the user for {name}'s email address.",
            }
        )


@tool
async def execute_batch_onboarding(
    participants: list,
    lam_url: Optional[str] = None,
    gitlab_url: Optional[str] = None,
    gitlab_project: Optional[str] = None,
    skip_iam: bool = False,
    skip_gitlab: bool = False,
) -> str:
    """
    Execute the batch onboarding for training participants.

    For each participant:
    1. Create IAM account in LAM (unless skip_iam=True)
    2. Add as member to GitLab project (unless skip_gitlab=True)

    Args:
        participants: List of participant dicts, each with 'email' (required) and optionally
                     'name', 'first_name', 'last_name'. Example:
                     [{"email": "john@example.com", "name": "John Doe"}]
        lam_url: Override the default LAM URL
        gitlab_url: Override the default GitLab URL
        gitlab_project: Override the default GitLab project
        skip_iam: Skip IAM account creation
        skip_gitlab: Skip GitLab membership
    """
    # Import sibling modules (can't use relative imports - skill loaded via importlib)
    gitlab_client = _import_skill_module("gitlab_client")
    lam_automation = _import_skill_module("lam_automation")

    add_gitlab_member = gitlab_client.add_gitlab_member
    check_gitlab_connection = gitlab_client.check_gitlab_connection
    create_gitlab_user = gitlab_client.create_gitlab_user
    create_lam_account = lam_automation.create_lam_account

    config = _load_skill_config()
    defaults = config.get("defaults", {})
    batch_config = config.get("batch", {})

    # Get URLs
    lam_url = lam_url or defaults.get("lam_url")
    gitlab_url = gitlab_url or defaults.get("gitlab_url")
    gitlab_project = gitlab_project or defaults.get("gitlab_project")
    gitlab_access = defaults.get("gitlab_access_level", "developer")

    # Get credentials
    creds = _get_credentials()

    # Filter out participants without emails and validate email format
    valid_participants = []
    invalid_emails = []
    for p in participants:
        email = p.get("email")
        if email:
            if _validate_email(email):
                valid_participants.append(p)
            else:
                invalid_emails.append({"name": p.get("name", "Unknown"), "email": email})

    if invalid_emails:
        logger.warning(f"Skipping participants with invalid emails: {invalid_emails}")

    if not valid_participants:
        return json.dumps({"error": "No participants with valid email addresses to onboard"})

    # Validate credentials
    if not skip_iam:
        if not creds.get("lam_username") or not creds.get("lam_password"):
            return json.dumps(
                {
                    "error": "LAM credentials not configured. Set LAM_USERNAME and LAM_PASSWORD environment variables."
                }
            )

    # Get SSL configuration
    ssl_config = _get_ssl_config()

    if not skip_gitlab:
        if not creds.get("gitlab_token"):
            return json.dumps(
                {
                    "error": "GitLab token not configured. Set GITLAB_PERSONAL_TOKEN environment variable."
                }
            )

        # Check GitLab connection
        # Note: This GitLab instance requires HTTP Basic Auth (LAM credentials) in addition to the PAT
        basic_auth = (creds["lam_username"], creds["lam_password"]) if creds.get("lam_username") and creds.get("lam_password") else None
        gitlab_check = await check_gitlab_connection(
            gitlab_url, creds["gitlab_token"],
            verify_ssl=ssl_config["verify_ssl"],
            ca_bundle=ssl_config["ca_bundle"],
            basic_auth=basic_auth
        )
        if not gitlab_check.get("connected"):
            return json.dumps(
                {
                    "error": f"Cannot connect to GitLab: {gitlab_check.get('error', 'Unknown error')}"
                }
            )

    # Process each participant
    results = []
    successful = 0
    delay_ms = batch_config.get("delay_between_participants_ms", 1000)

    for i, participant in enumerate(valid_participants):
        result = {
            "participant": participant,
            "iam_created": False,
            "iam_error": None,
            "iam_password": None,
            "gitlab_added": False,
            "gitlab_error": None,
        }

        # Prepare user data
        user_data = {
            "first_name": participant.get("first_name", ""),
            "last_name": participant.get("last_name", ""),
            "email": participant["email"],
            "username": participant.get("username"),
        }

        # Create IAM account
        if not skip_iam:
            try:
                iam_result = await create_lam_account(
                    lam_url=lam_url,
                    admin_username=creds["lam_username"],
                    admin_password=creds["lam_password"],
                    user_data=user_data,
                    headless=False,  # SSO requires visible browser for MFA
                )
                result["iam_created"] = iam_result.get("success", False)
                if result["iam_created"]:
                    result["iam_password"] = iam_result.get("password")
                    result["iam_username"] = iam_result.get("username")
                else:
                    result["iam_error"] = iam_result.get("error", "Unknown error")
            except Exception as e:
                result["iam_error"] = str(e)

        # Add to GitLab
        if not skip_gitlab:
            try:
                # Use HTTP Basic Auth (LAM credentials) in addition to PAT
                basic_auth = (creds["lam_username"], creds["lam_password"]) if creds.get("lam_username") and creds.get("lam_password") else None

                # If IAM was created, also create GitLab user (they don't have one yet)
                # If IAM was skipped, assume user already exists in both systems
                if result.get("iam_created"):
                    gitlab_username = result.get("iam_username")
                    display_name = participant.get("name") or f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()

                    # Build LDAP DN for linking
                    ldap_dn = f"uid={gitlab_username},ou=People,dc=pl,dc=s2-eu,dc=capgemini,dc=local"

                    logger.info(f"Creating GitLab user: {gitlab_username} for {participant['email']}")
                    create_result = await create_gitlab_user(
                        gitlab_url=gitlab_url,
                        token=creds["gitlab_token"],
                        email=participant["email"],
                        username=gitlab_username,
                        name=display_name,
                        ldap_dn=ldap_dn,
                        verify_ssl=ssl_config["verify_ssl"],
                        ca_bundle=ssl_config["ca_bundle"],
                        basic_auth=basic_auth,
                    )

                    if not create_result.get("success"):
                        result["gitlab_error"] = f"Failed to create GitLab user: {create_result.get('error', 'Unknown error')}"
                        results.append(result)
                        continue

                    result["gitlab_user_created"] = True

                # Now add to project
                gitlab_result = await add_gitlab_member(
                    gitlab_url=gitlab_url,
                    token=creds["gitlab_token"],
                    project_path=gitlab_project,
                    user_identifier=participant["email"],
                    access_level=gitlab_access,
                    verify_ssl=ssl_config["verify_ssl"],
                    ca_bundle=ssl_config["ca_bundle"],
                    basic_auth=basic_auth,
                )
                result["gitlab_added"] = gitlab_result.get("success", False)
                if not result["gitlab_added"]:
                    result["gitlab_error"] = gitlab_result.get("error", "Unknown error")
            except Exception as e:
                result["gitlab_error"] = str(e)

        # Count success
        iam_ok = skip_iam or result["iam_created"]
        gitlab_ok = skip_gitlab or result["gitlab_added"]
        if iam_ok and gitlab_ok:
            successful += 1

        results.append(result)

        # Delay between participants (except for last one)
        if i < len(valid_participants) - 1 and delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)

    # Generate summary
    summary = {
        "status": "completed",
        "total": len(valid_participants),
        "successful": successful,
        "failed": len(valid_participants) - successful,
        "results": results,
    }

    # Add credentials section for successful IAM accounts (for user reference)
    if not skip_iam:
        new_accounts = [
            {
                "name": f"{r['participant'].get('first_name', '')} {r['participant'].get('last_name', '')}".strip(),
                "email": r["participant"]["email"],
                "username": r.get("iam_username", "N/A"),
                "password": r.get("iam_password", "N/A"),
            }
            for r in results
            if r["iam_created"]
        ]
        if new_accounts:
            summary["new_iam_accounts"] = new_accounts

    return json.dumps(summary, indent=2)


def get_tools():
    """Return all tools provided by this skill."""
    return [
        resolve_participant_email,
        execute_batch_onboarding,
    ]
