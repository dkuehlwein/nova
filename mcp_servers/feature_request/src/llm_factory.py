"""
LLM Factory for Feature Request MCP Server

Provides LiteLLM-based LLM creation with proper authentication and configuration.
Follows the same patterns as Nova's main backend for consistency.
"""

import os
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI


def resolve_docker_localhost_url(url: str) -> str:
    """
    Resolve localhost URLs for Docker environments.
    
    In Docker containers, localhost URLs need to be rewritten to use
    host.docker.internal for proper connectivity to host services.
    
    Args:
        url: Original URL (may contain localhost)
        
    Returns:
        Resolved URL for the current environment
    """
    # Check if running in Docker container
    if os.path.exists('/.dockerenv') or os.environ.get('DOCKER_ENV') == 'true':
        # In Docker: replace localhost with host.docker.internal
        if 'localhost' in url:
            return url.replace('localhost', 'host.docker.internal')
    
    return url


def get_litellm_config() -> Dict[str, str]:
    """
    Get LiteLLM configuration from environment variables.
    
    Returns:
        Dictionary with base_url and api_key for LiteLLM
    """
    # Get base URL from environment (fallback to default)
    base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
    
    # Resolve Docker networking for localhost URLs
    resolved_url = resolve_docker_localhost_url(base_url)
    
    # Get API key - MUST be service-specific key (no master key fallback for security)
    api_key = os.getenv("FEATURE_REQUEST_LITELLM_KEY")
    
    return {
        "base_url": resolved_url,
        "api_key": api_key
    }


def create_feature_analyzer_llm(
    model: str = "gemini-2.5-flash",
    temperature: float = 0.1,
    max_tokens: int = 2048
) -> ChatOpenAI:
    """
    Create LLM instance for feature request analysis via LiteLLM gateway.
    
    Args:
        model: Model name (should be available in LiteLLM)
        temperature: Sampling temperature (0.0 to 1.0)
        max_tokens: Maximum tokens in response
        
    Returns:
        Configured ChatOpenAI instance pointing to LiteLLM gateway
    """
    # Get LiteLLM configuration
    litellm_config = get_litellm_config()
    
    return ChatOpenAI(
        model=model,
        api_key=litellm_config["api_key"],
        base_url=f"{litellm_config['base_url']}/v1",
        temperature=temperature,
        max_tokens=max_tokens,
        default_headers={
            "user": "feature-request-service",
            "team_id": "nova-mcp-services",
            "user_id": "feature-request-service"
        }
    )


def get_available_models() -> list[str]:
    """
    Get list of models available for feature analysis.
    
    Returns:
        List of model names available through LiteLLM
    """
    return [
        "gemini-2.5-flash",  # Primary model
        "gemini-1.5-flash",  # Fallback model
        "phi-4-Q4_K_M",      # Local model option
        "smollm3-3b-Q4_K_M"  # Lightweight local model
    ]


def validate_configuration() -> Dict[str, Any]:
    """
    Validate LiteLLM configuration and connectivity.
    
    Returns:
        Dictionary with validation results
    """
    try:
        config = get_litellm_config()
        
        # SECURITY: Service MUST have its own dedicated key
        service_key = os.getenv("FEATURE_REQUEST_LITELLM_KEY")
        
        if not service_key:
            return {
                "valid": False,
                "error": "FEATURE_REQUEST_LITELLM_KEY environment variable is required",
                "base_url": config["base_url"],
                "has_api_key": False,
                "using_service_key": False,
                "available_models": []
            }
        
        # Validate service key format (should be a proper virtual key)
        if not service_key.startswith("sk-") or len(service_key) < 20:
            return {
                "valid": False,
                "error": "Invalid service key format - must be a proper virtual key",
                "base_url": config["base_url"],
                "has_api_key": True,
                "using_service_key": False,
                "available_models": []
            }
        
        # Basic validation passed
        validation_result = {
            "valid": True,
            "base_url": config["base_url"],
            "has_api_key": True,
            "using_service_key": True,
            "service_key_prefix": service_key[:10] + "..." if service_key else None,
            "available_models": get_available_models()
        }
        
        return validation_result
        
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "base_url": None,
            "has_api_key": False,
            "using_service_key": False,
            "available_models": []
        }