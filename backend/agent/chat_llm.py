"""
Nova LLM Module

Centralized LLM initialization for Nova agents using LiteLLM gateway.
"""

from typing import Any, Dict, List, Optional, Sequence, Union

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai import ChatOpenAI

from utils.llm_factory import get_chat_llm_config


def _clean_null_defaults(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively remove 'default': null from JSON schema.

    Some LLM providers (e.g., LM Studio with certain models) fail when
    tool schemas contain 'default': null due to Jinja template rendering
    issues. This function removes those null defaults.
    """
    if not isinstance(schema, dict):
        return schema

    cleaned = {}
    for key, value in schema.items():
        if key == "default" and value is None:
            # Skip null defaults
            continue
        elif isinstance(value, dict):
            cleaned[key] = _clean_null_defaults(value)
        elif isinstance(value, list):
            cleaned[key] = [
                _clean_null_defaults(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value

    return cleaned


def _clean_tool_schema(tool_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Clean a single tool's schema to remove null defaults."""
    if "function" in tool_dict and "parameters" in tool_dict["function"]:
        tool_dict["function"]["parameters"] = _clean_null_defaults(
            tool_dict["function"]["parameters"]
        )
    return tool_dict


class NovaChatOpenAI(ChatOpenAI):
    """ChatOpenAI wrapper that cleans tool schemas before binding.

    Some local LLM providers (e.g., LM Studio with Nemotron models) fail
    when tool schemas contain 'default': null values due to Jinja template
    rendering issues. This wrapper removes those null defaults.
    """

    def bind_tools(
        self,
        tools: Sequence[Union[Dict[str, Any], type, BaseTool]],
        **kwargs: Any,
    ) -> "NovaChatOpenAI":
        """Bind tools with cleaned schemas (no null defaults)."""
        # Convert tools to OpenAI format
        formatted_tools = []
        for tool in tools:
            if isinstance(tool, dict):
                formatted_tools.append(_clean_tool_schema(tool.copy()))
            else:
                # Convert LangChain tool to OpenAI format, then clean
                openai_tool = convert_to_openai_tool(tool)
                formatted_tools.append(_clean_tool_schema(openai_tool))

        # Call parent bind_tools with pre-formatted tools
        return super().bind_tools(formatted_tools, **kwargs)


def create_chat_llm(config: Optional[RunnableConfig] = None) -> NovaChatOpenAI:
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
    
    return NovaChatOpenAI(
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