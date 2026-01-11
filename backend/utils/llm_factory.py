"""
LLM Factory Utilities

Centralized LLM creation logic to eliminate duplication between chat and memory systems.
"""

import time
from typing import Dict, Any
from config import settings, Defaults
from utils.logging import get_logger

logger = get_logger(__name__)



def get_litellm_config() -> Dict[str, str]:
    """
    Get consolidated LiteLLM configuration from user settings and environment.
    Base URL from user settings (Tier 3), master key from environment (Tier 2).
    
    Automatically resolves localhost URLs for Docker environments using 
    host.docker.internal routing.
    
    Returns:
        Dictionary with base_url and api_key
    """
    try:
        from database.database import UserSettingsService
        from utils.docker_detection import resolve_docker_localhost_url
        
        user_settings = UserSettingsService.get_user_settings_sync()
        base_url = (user_settings.litellm_base_url if user_settings and user_settings.litellm_base_url 
                   else settings.LITELLM_BASE_URL)
        
        # Resolve Docker networking for localhost URLs
        resolved_url = resolve_docker_localhost_url(base_url)
        
    except Exception:
        from utils.docker_detection import resolve_docker_localhost_url
        resolved_url = resolve_docker_localhost_url(settings.LITELLM_BASE_URL)
    
    return {
        "base_url": resolved_url,
        "api_key": settings.LITELLM_MASTER_KEY
    }


def get_litellm_base_url() -> str:
    """
    Get LiteLLM base URL from user settings or config fallback.
    
    Returns:
        LiteLLM base URL
    """
    return get_litellm_config()["base_url"]


def get_litellm_master_key() -> str:
    """
    Get LiteLLM master key from environment configuration (ADR-008 Tier 2).
    
    Returns:
        LiteLLM master key from environment
    """
    return get_litellm_config()["api_key"]


def get_litellm_master_key() -> str:
    """
    Get LiteLLM master key from environment configuration (ADR-008 Tier 2).
    
    Returns:
        LiteLLM master key from environment
    """
    return settings.LITELLM_MASTER_KEY


def get_chat_llm_config() -> Dict[str, Any]:
    """
    Get validated chat LLM configuration from user settings.

    Returns:
        Dictionary with chat LLM configuration
    """
    t0 = time.time()
    try:
        from database.database import UserSettingsService
        user_settings = UserSettingsService.get_llm_settings_sync()
        elapsed_ms = (time.time() - t0) * 1000
        logger.info(f"⏱️ TIMING: get_llm_settings_sync took {elapsed_ms:.2f}ms")
    except Exception:
        user_settings = {}

    model_name = user_settings.get("chat_llm_model", Defaults.CHAT_LLM_MODEL)
    temperature = user_settings.get("chat_llm_temperature", Defaults.CHAT_LLM_TEMPERATURE)
    max_tokens = user_settings.get("chat_llm_max_tokens", Defaults.CHAT_LLM_MAX_TOKENS)

    return {
        "model": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "base_url": get_litellm_base_url(),
        "api_key": get_litellm_master_key()
    }


def get_memory_llm_config() -> Dict[str, Any]:
    """
    Get validated memory LLM configuration from user settings.
    
    Returns:
        Dictionary with memory LLM configuration including small model
    """
    try:
        from database.database import UserSettingsService
        user_settings = UserSettingsService.get_llm_settings_sync()
    except Exception:
        user_settings = {}
    
    model_name = user_settings.get("memory_llm_model", Defaults.MEMORY_LLM_MODEL)
    small_model_name = user_settings.get("memory_small_llm_model", model_name)  # Default to main model
    temperature = user_settings.get("memory_llm_temperature", Defaults.MEMORY_LLM_TEMPERATURE)
    max_tokens = user_settings.get("memory_llm_max_tokens", Defaults.MEMORY_LLM_MAX_TOKENS)
    
    return {
        "model": model_name,
        "small_model": small_model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "base_url": get_litellm_base_url(),
        "api_key": get_litellm_master_key()
    }


def get_embedding_config() -> Dict[str, Any]:
    """
    Get validated embedding model configuration from user settings.
    
    Returns:
        Dictionary with embedding configuration
    """
    try:
        from database.database import UserSettingsService
        user_settings = UserSettingsService.get_llm_settings_sync()
    except Exception:
        user_settings = {}
    
    model_name = user_settings.get("embedding_model", Defaults.EMBEDDING_MODEL)
    
    return {
        "embedding_model": model_name,
        "base_url": get_litellm_base_url(),
        "api_key": get_litellm_master_key(),
        "embedding_dim": 768  # Google text-embedding-004 output dimensions
    }