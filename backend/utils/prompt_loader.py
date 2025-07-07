"""
Prompt loader with hot-reload capabilities.
UPDATED: Now uses database-based user settings instead of config files.
"""

from utils.config_registry import config_registry
from utils.logging import get_logger
from database.database import db_manager
from models.user_settings import UserSettings
from datetime import datetime
import pytz

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
    async with db_manager.get_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(UserSettings).limit(1))
        user_settings = result.scalar_one_or_none()
    
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
        logger.warning(f"Invalid timezone '{user_timezone}', using UTC")
        current_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Create user notes section
    user_notes_section = ""
    if user_notes:
        user_notes_section = f"\n\n**Additional User Context:**\n{user_notes}"
    
    # Use the unified system's template processing - will raise if template is invalid
    prompt = prompt_manager.get_processed_config(
        user_full_name=user_full_name,
        user_email=user_email,
        user_timezone=user_timezone,
        current_time_user_tz=current_time_str,
        user_notes_section=user_notes_section
    )
    
    return prompt 