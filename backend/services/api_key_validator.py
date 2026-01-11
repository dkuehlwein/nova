"""
API Key Validator Service

Provides reusable validator classes for external service API keys.
Extracted from settings_endpoints.py to enable reuse and reduce duplication.
"""

from datetime import datetime, timezone
from typing import Optional
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from utils.logging import get_logger

logger = get_logger("api_key_validator")


async def http_request(url: str, headers: dict, timeout: int = 10) -> tuple[int, dict]:
    """Make HTTP GET request and return status code and response data."""
    async with aiohttp.ClientSession() as http_session:
        async with http_session.get(url, headers=headers, timeout=timeout) as response:
            try:
                data = await response.json()
            except (ValueError, aiohttp.ContentTypeError):
                data = {"error": await response.text()}
            return response.status, data


async def cache_validation_result(db_session: AsyncSession, settings, key_type: str, result_data: dict):
    """Helper to cache validation results consistently."""
    from database.database import UserSettingsService
    settings.api_key_validation_status[key_type] = result_data
    flag_modified(settings, "api_key_validation_status")
    await UserSettingsService.update_user_settings(db_session, settings)


async def validate_google_api_key(db_session: AsyncSession, api_key: str, settings) -> dict:
    """Validate Google API key using Gemini API."""
    from config import settings as app_config
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(app_config.DEFAULT_CHAT_MODEL)
        response = model.generate_content("Hello")

        now = datetime.now(timezone.utc).isoformat()
        await cache_validation_result(db_session, settings, "google_api_key", {
            "validated": True,
            "validated_at": now,
            "validation_error": None,
            "last_check": now,
            "gemini_models_available": 0
        })

        return {"valid": True, "message": "Google API key is valid", "service": "google"}
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await cache_validation_result(db_session, settings, "google_api_key", {
            "validated": False,
            "validated_at": None,
            "validation_error": str(e),
            "last_check": now,
            "gemini_models_available": 0
        })
        return {"valid": False, "message": f"Google API key validation failed: {str(e)}", "service": "google"}


async def validate_litellm_master_key(db_session: AsyncSession, api_key: str, settings) -> dict:
    """Validate LiteLLM master key by testing the models endpoint."""
    from config import settings as app_settings
    try:
        status, data = await http_request(
            f"{app_settings.LITELLM_BASE_URL}/v1/models",
            {"Authorization": f"Bearer {api_key}"}
        )

        now = datetime.now(timezone.utc).isoformat()
        if status == 200 and isinstance(data, dict) and "data" in data:
            models_count = len(data.get("data", []))
            await cache_validation_result(db_session, settings, "litellm_master_key", {
                "validated": True,
                "validated_at": now,
                "validation_error": None,
                "last_check": now,
                "base_url": app_settings.LITELLM_BASE_URL,
                "models_available": models_count
            })
            return {"valid": True, "message": f"LiteLLM master key is valid ({models_count} models available)", "service": "litellm"}
        elif status == 401 or status == 403:
            await cache_validation_result(db_session, settings, "litellm_master_key", {
                "validated": False,
                "validated_at": None,
                "validation_error": f"Authentication failed (HTTP {status})",
                "last_check": now,
                "base_url": app_settings.LITELLM_BASE_URL
            })
            return {"valid": False, "message": "LiteLLM master key is invalid (authentication failed)", "service": "litellm"}
        else:
            error_msg = data.get('error', 'Unknown error') if isinstance(data, dict) else str(data)
            await cache_validation_result(db_session, settings, "litellm_master_key", {
                "validated": False,
                "validated_at": None,
                "validation_error": f"HTTP {status}: {error_msg}",
                "last_check": now,
                "base_url": app_settings.LITELLM_BASE_URL
            })
            return {"valid": False, "message": f"LiteLLM validation failed: HTTP {status}", "service": "litellm"}
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await cache_validation_result(db_session, settings, "litellm_master_key", {
            "validated": False,
            "validated_at": None,
            "validation_error": str(e),
            "last_check": now,
            "base_url": "unknown"
        })
        return {"valid": False, "message": f"LiteLLM master key validation failed: {str(e)}", "service": "litellm"}


async def validate_openrouter_api_key(db_session: AsyncSession, api_key: str, settings) -> dict:
    """Validate OpenRouter API key by testing a minimal completion request."""
    try:
        test_payload = {
            "model": "z-ai/glm-4.5-air:free",
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 1
        }

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=test_payload,
                timeout=10
            ) as response:
                now = datetime.now(timezone.utc).isoformat()

                if response.status == 200:
                    models_status, models_data = await http_request(
                        "https://openrouter.ai/api/v1/models",
                        {"Authorization": f"Bearer {api_key}"}
                    )
                    models_count = len(models_data.get("data", [])) if models_status == 200 else 0

                    await cache_validation_result(db_session, settings, "openrouter_api_key", {
                        "validated": True,
                        "validated_at": now,
                        "validation_error": None,
                        "last_check": now,
                        "models_available": models_count
                    })
                    return {"valid": True, "message": f"OpenRouter API key is valid ({models_count} models available)", "service": "openrouter"}
                else:
                    error_data = await response.json() if response.content_type == "application/json" else {"error": await response.text()}
                    error_msg = error_data.get("error", {}).get("message", "Unknown error") if isinstance(error_data.get("error"), dict) else str(error_data.get("error", "Unknown error"))

                    await cache_validation_result(db_session, settings, "openrouter_api_key", {
                        "validated": False,
                        "validated_at": None,
                        "validation_error": f"HTTP {response.status}: {error_msg}",
                        "last_check": now
                    })
                    return {"valid": False, "message": f"OpenRouter API key validation failed: {error_msg}", "service": "openrouter"}
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await cache_validation_result(db_session, settings, "openrouter_api_key", {
            "validated": False,
            "validated_at": None,
            "validation_error": str(e),
            "last_check": now
        })
        return {"valid": False, "message": f"OpenRouter API key validation failed: {str(e)}", "service": "openrouter"}


# Validation method dispatch map for use by endpoints
VALIDATION_METHODS = {
    "google_api_key": validate_google_api_key,
    "litellm_master_key": validate_litellm_master_key,
    "openrouter_api_key": validate_openrouter_api_key,
}
