"""
Prompt loader with hot-reload capabilities.
UPDATED: Now fully uses unified configuration management system.
"""

from utils.config_registry import config_registry
from utils.logging import get_logger
from datetime import datetime
import pytz

logger = get_logger("prompt_loader")


def load_nova_system_prompt() -> str:
    """Load Nova system prompt from markdown file with user context injection."""
    try:
        # Load user profile from unified config system
        user_profile_manager = config_registry.get_manager("user_profile")
        user_profile = user_profile_manager.get_config()
        
        # Get current time in user's timezone
        try:
            user_tz = pytz.timezone(user_profile.timezone)
            current_time = datetime.now(user_tz)
            current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        except pytz.UnknownTimeZoneError:
            # Fallback to UTC if timezone is invalid
            current_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Create user notes section
        user_notes_section = ""
        if user_profile.notes:
            user_notes_section = f"\n\n**Additional User Context:**\n{user_profile.notes}"
        
        # Use the unified system's template processing
        prompt_manager = config_registry.get_manager("system_prompt")
        prompt = prompt_manager.get_processed_config(
            user_full_name=user_profile.full_name,
            user_email=user_profile.email,
            user_timezone=user_profile.timezone,
            current_time_user_tz=current_time_str,
            user_notes_section=user_notes_section
        )
        
        return prompt
        
    except Exception as e:
        logger.error(
            "Failed to inject user context into system prompt",
            exc_info=True,
            extra={"data": {"error": str(e)}}
        )
        # Fallback to raw prompt without user context
        prompt_manager = config_registry.get_manager("system_prompt")
        return prompt_manager.get_config() 