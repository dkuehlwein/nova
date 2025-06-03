"""
Nova LLM Module

Centralized LLM initialization for Nova agents.
"""

import os
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings


def create_llm(config: Optional[RunnableConfig] = None) -> ChatGoogleGenerativeAI:
    """Create and configure the Google Gemini model.
    
    Args:
        config: Optional configuration with model settings
        
    Returns:
        Configured ChatGoogleGenerativeAI instance
        
    Raises:
        ValueError: If GOOGLE_API_KEY is not found
    """
    api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    # Get configuration values with defaults
    configuration = config.get("configurable", {}) if config else {}
    model_name = configuration.get("model_name", settings.GOOGLE_MODEL_NAME or "gemini-2.5-flash-preview-04-17")
    temperature = configuration.get("temperature", 0.7)
    
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=temperature,
        max_tokens=2048,
    ) 