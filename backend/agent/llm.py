"""
Nova LLM Module

Centralized LLM initialization for Nova agents using LiteLLM gateway.
"""

import os
from typing import Optional, Union
import asyncio

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from config import settings


def _get_user_settings() -> dict:
    """Get user settings from database synchronously."""
    try:
        # Import here to avoid circular imports
        from database.database import UserSettingsService
        
        return UserSettingsService.get_llm_settings_sync()
    except Exception as e:
        print(f"Warning: Could not get user settings, using defaults: {e}")
        return {}


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
    model_name = configuration.get("model_name", user_settings.get("llm_model", "gemma3:12b-it-qat"))
    temperature = configuration.get("temperature", user_settings.get("llm_temperature", 0.1))
    max_tokens = configuration.get("max_tokens", user_settings.get("llm_max_tokens", 64000))
    
    return ChatOpenAI(
        model=model_name,
        openai_api_key=litellm_api_key,
        openai_api_base=f"{litellm_base_url}/v1",
        temperature=temperature,
        max_tokens=max_tokens,
    ) 