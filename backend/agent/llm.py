"""
Nova LLM Module

Centralized LLM initialization for Nova agents using LiteLLM gateway.
"""

from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from config import settings


def _get_user_settings() -> dict:
    """Get user settings from database synchronously."""
    # Import here to avoid circular imports
    from database.database import UserSettingsService
    
    return UserSettingsService.get_llm_settings_sync()


def create_llm(config: Optional[RunnableConfig] = None) -> ChatOpenAI:
    """Create and configure LLM via LiteLLM gateway.
    
    Args:
        config: Optional configuration with model settings
        
    Returns:
        Configured ChatOpenAI instance pointing to LiteLLM gateway
        
    Raises:
        ValueError: If LiteLLM configuration is missing
    """
    # LiteLLM configuration
    litellm_base_url = settings.LITELLM_BASE_URL
    litellm_api_key = settings.LITELLM_MASTER_KEY
    
    if not litellm_base_url or not litellm_api_key:
        raise ValueError("LITELLM_BASE_URL and LITELLM_MASTER_KEY are required")
    
    # Get user settings from database
    user_settings = _get_user_settings()
    
    # Get configuration values with user settings as defaults
    configuration = config.get("configurable", {}) if config else {}
    model_name = configuration.get("model_name", user_settings.get("llm_model", "Qwen3-14B-Q5_K_M"))
    temperature = configuration.get("temperature", user_settings.get("llm_temperature", 0.6))
    max_tokens = configuration.get("max_tokens", user_settings.get("llm_max_tokens", 2048))
    
    return ChatOpenAI(
        model=model_name,
        api_key=litellm_api_key,
        base_url=f"{litellm_base_url}/v1",
        temperature=temperature,
        max_tokens=max_tokens,
        default_headers={
            "user": "nova-user",
            "team_id": "nova-team", 
            "user_id": "nova-user-1"
        }
    ) 