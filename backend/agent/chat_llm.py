"""
Nova LLM Module

Centralized LLM initialization for Nova agents using LiteLLM gateway.
"""

from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from utils.llm_factory import get_chat_llm_config


def create_chat_llm(config: Optional[RunnableConfig] = None) -> ChatOpenAI:
    """Create and configure LLM via LiteLLM gateway.
    
    Args:
        config: Optional configuration with model settings
        
    Returns:
        Configured ChatOpenAI instance pointing to LiteLLM gateway
    """
    # Get base configuration from factory
    llm_config = get_chat_llm_config()
    
    # Override with any provided config
    if config and "configurable" in config:
        configuration = config["configurable"]
        llm_config["model"] = configuration.get("chat_llm_model", llm_config["model"])
        llm_config["temperature"] = configuration.get("chat_llm_temperature", llm_config["temperature"])
        llm_config["max_tokens"] = configuration.get("chat_llm_max_tokens", llm_config["max_tokens"])
    
    return ChatOpenAI(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=f"{llm_config['base_url']}/v1",
        temperature=llm_config["temperature"],
        max_tokens=llm_config["max_tokens"],
        default_headers={
            "user": "nova-user",
            "team_id": "nova-team", 
            "user_id": "nova-user-1"
        }
    ) 