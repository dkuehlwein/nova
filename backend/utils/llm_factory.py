"""
LLM Factory Utilities

Centralized LLM creation logic to eliminate duplication between chat and memory systems.
"""

from typing import Optional, Dict, Any
from config import settings


def get_validated_model(model_name: str, fallback: str = "qwen3-32b") -> str:
    """
    Validate that a model exists in LiteLLM and return it, or fallback.
    
    Args:
        model_name: The model name to validate
        fallback: Fallback model if validation fails
        
    Returns:
        Validated model name or fallback
    """
    try:
        from services.llm_service import llm_service
        available_models = llm_service.get_available_models_sync()
        if available_models and model_name not in [m["id"] for m in available_models.get("models", [])]:
            print(f"Warning: Model '{model_name}' not available in LiteLLM, using fallback '{fallback}'")
            return fallback
        return model_name
    except Exception as e:
        print(f"Warning: Could not validate model availability: {e}")
        return model_name  # Continue with user selection - LiteLLM will handle the error


def get_litellm_config() -> Dict[str, str]:
    """
    Get consolidated LiteLLM configuration from user settings and environment.
    Base URL from user settings (Tier 3), master key from environment (Tier 2).
    
    Returns:
        Dictionary with base_url and api_key
    """
    try:
        from database.database import UserSettingsService
        user_settings = UserSettingsService.get_user_settings_sync()
        base_url = (user_settings.litellm_base_url if user_settings and user_settings.litellm_base_url 
                   else settings.LITELLM_BASE_URL)
    except Exception:
        base_url = settings.LITELLM_BASE_URL
    
    return {
        "base_url": base_url,
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
    try:
        from database.database import UserSettingsService
        user_settings = UserSettingsService.get_llm_settings_sync()
    except Exception:
        user_settings = {}
    
    model_name = user_settings.get("chat_llm_model", "qwen3-32b")
    temperature = user_settings.get("chat_llm_temperature", 0.7)
    max_tokens = user_settings.get("chat_llm_max_tokens", 2048)
    
    return {
        "model": get_validated_model(model_name),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "base_url": get_litellm_base_url(),
        "api_key": get_litellm_master_key()
    }


def get_memory_llm_config() -> Dict[str, Any]:
    """
    Get validated memory LLM configuration from user settings.
    
    Returns:
        Dictionary with memory LLM configuration
    """
    try:
        from database.database import UserSettingsService
        user_settings = UserSettingsService.get_llm_settings_sync()
    except Exception:
        user_settings = {}
    
    model_name = user_settings.get("memory_llm_model", "qwen3-32b")
    temperature = user_settings.get("memory_llm_temperature", 0.1)
    max_tokens = user_settings.get("memory_llm_max_tokens", 2048)
    
    return {
        "model": get_validated_model(model_name),
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
    
    model_name = user_settings.get("embedding_model", "qwen3-embedding-4b")
    
    return {
        "embedding_model": get_validated_model(model_name, "qwen3-embedding-4b"),
        "base_url": get_litellm_base_url(),
        "api_key": get_litellm_master_key(),
        "embedding_dim": 1024  # Qwen3-Embedding-4B output dimensions
    }