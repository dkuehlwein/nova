"""
Nova LLM Module

Centralized LLM initialization for Nova agents using LiteLLM gateway.
"""

import os
from typing import Optional, Union

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from config import settings


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
    
    # Get configuration values with defaults
    configuration = config.get("configurable", {}) if config else {}
    model_name = configuration.get("model_name", "gemma3-12b-local")  # Default to local model
    temperature = configuration.get("temperature", 0.1)
    
    return ChatOpenAI(
        model=model_name,
        openai_api_key=litellm_api_key,
        openai_api_base=f"{litellm_base_url}/v1",
        temperature=temperature,
        max_tokens=2048,
    ) 