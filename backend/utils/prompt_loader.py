"""
Prompt loader with hot-reload capabilities.
UPDATED: Now uses database-based user settings instead of config files.
"""

from datetime import datetime

import pytz

from database.database import db_manager
from models.user_settings import UserSettings
from utils.config_registry import config_registry
from utils.logging import get_logger
from utils.skill_manager import get_skill_manager

logger = get_logger("prompt_loader")


async def load_nova_system_prompt() -> str:
    """
    Load Nova system prompt from markdown file with user context injection.
    Now uses database-based user settings instead of config files.
    
    FAIL-FAST: This function will raise exceptions if configuration is missing
    or invalid. This is intentional - the system should not start without
    proper configuration.
    """
    # Get prompt manager - will raise if not initialized
    prompt_manager = config_registry.get_manager("system_prompt")
    
    if prompt_manager is None:
        raise RuntimeError("System prompt manager not initialized in config registry")
    
    # Get user profile from database
    from database.database import UserSettingsService
    user_settings = await UserSettingsService.get_user_settings()
    
    # Use defaults if no user settings found
    if user_settings is None:
        logger.error("No user settings found in database, using defaults")
        user_full_name = "User"
        user_email = "user@example.com"
        user_timezone = "UTC"
        user_notes = None
    else:
        user_full_name = user_settings.full_name 
        user_email = user_settings.email 
        user_timezone = user_settings.timezone
        user_notes = user_settings.notes
    
    # Get current time in user's timezone
    try:
        user_tz = pytz.timezone(user_timezone)
        current_time = datetime.now(user_tz)
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    except pytz.UnknownTimeZoneError:
        # Fallback to UTC if timezone is invalid
        logger.warning("Invalid timezone, using UTC", extra={"data": {"user_timezone": user_timezone}})
        current_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Build available skills section
    available_skills_section = _build_available_skills_section()

    # Use the unified system's template processing - will raise if template is invalid
    prompt = prompt_manager.get_processed_config(
        user_full_name=user_full_name,
        user_email=user_email,
        user_timezone=user_timezone,
        current_time_user_tz=current_time_str,
        user_notes_section=user_notes,
        available_skills_section=available_skills_section,
    )

    return prompt


def _build_available_skills_section() -> str:
    """
    Build the available skills section for the system prompt.

    Returns an empty string if no skills are available, otherwise
    returns a formatted section listing available skills.
    """
    try:
        skill_manager = get_skill_manager()
        skill_summaries = skill_manager.get_skill_summaries()

        if not skill_summaries:
            return ""

        # Format skills as a bullet list
        skills_list = "\n".join(
            f"- **{name}**: {description}"
            for name, description in sorted(skill_summaries.items())
        )

        return f"""

**Available Skills:**
The following specialized skills are available. If a user request matches
one of these domains, use the `enable_skill` tool to load it.

{skills_list}
"""
    except Exception as e:
        logger.warning(
            "Failed to build available skills section",
            extra={"data": {"error": str(e)}},
        )
        return "" 