"""
External Service Status Checker Service

Provides status checking classes for external services with caching support.
Uses a template pattern to eliminate duplication across status endpoints.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from utils.logging import get_logger

logger = get_logger("external_service_status")


class ExternalServiceStatusChecker(ABC):
    """Base class for external service status checking with caching."""

    # Override in subclasses
    cache_key: str = ""
    service_name: str = ""

    async def get_status(
        self,
        db_session: AsyncSession,
        settings,
        force_refresh: bool = False
    ) -> dict:
        """
        Get service status, using cache unless force_refresh is True.

        Args:
            db_session: Database session for caching
            settings: User settings object containing cache
            force_refresh: If True, bypass cache and perform real-time check

        Returns:
            Status dictionary with service-specific fields
        """
        from database.database import UserSettingsService

        cached_status = settings.api_key_validation_status.get(self.cache_key, {})
        has_api_key = self._has_api_key()

        if not force_refresh and cached_status and has_api_key:
            return self._format_cached_response(cached_status, has_api_key)

        # Perform real-time validation
        if has_api_key:
            logger.info(
                f"Performing real-time {self.service_name} API validation",
                extra={"data": {"force_refresh": force_refresh}}
            )
            result = await self._perform_check()

            # Cache the validation results
            now = datetime.now(timezone.utc).isoformat()
            new_status = self._build_cache_status(result, now, cached_status)
            settings.api_key_validation_status[self.cache_key] = new_status
            flag_modified(settings, "api_key_validation_status")
            await UserSettingsService.update_user_settings(db_session, settings)

            return self._format_response(result, has_api_key, new_status)
        else:
            return self._format_not_configured_response()

    @abstractmethod
    def _has_api_key(self) -> bool:
        """Check if the API key is configured."""
        pass

    @abstractmethod
    async def _perform_check(self) -> dict:
        """Perform the actual service check. Returns dict with 'valid' and extra fields."""
        pass

    @abstractmethod
    def _format_cached_response(self, cached_status: dict, has_api_key: bool) -> dict:
        """Format response when using cached data."""
        pass

    @abstractmethod
    def _format_response(self, result: dict, has_api_key: bool, new_status: dict) -> dict:
        """Format response after real-time check."""
        pass

    @abstractmethod
    def _format_not_configured_response(self) -> dict:
        """Format response when API key is not configured."""
        pass

    @abstractmethod
    def _build_cache_status(self, result: dict, now: str, cached_status: dict) -> dict:
        """Build the cache status dictionary."""
        pass


class GoogleAPIStatusChecker(ExternalServiceStatusChecker):
    """Status checker for Google API (Gemini)."""

    cache_key = "google_api_key"
    service_name = "Google"

    def _has_api_key(self) -> bool:
        from config import settings as app_settings
        return bool(app_settings.GOOGLE_API_KEY)

    async def _perform_check(self) -> dict:
        from config import settings as app_settings
        from services.llm_service import llm_service

        is_valid = False
        gemini_models_count = 0

        try:
            import google.generativeai as genai
            genai.configure(api_key=app_settings.GOOGLE_API_KEY.get_secret_value())

            model = genai.GenerativeModel(app_settings.DEFAULT_CHAT_MODEL)
            response = model.generate_content("Hello", request_options={"timeout": 10})

            if response and response.text and len(response.text.strip()) > 0:
                is_valid = True
        except Exception as e:
            logger.warning(f"Google API validation failed: {e}")
            is_valid = False

        # Get available Gemini models
        available_models = await llm_service.get_available_models()
        all_models = available_models.get("all_models", [])
        gemini_models_count = len([m for m in all_models if "gemini" in m.get("model_name", "").lower()])

        return {"valid": is_valid, "gemini_models_count": gemini_models_count}

    def _format_cached_response(self, cached_status: dict, has_api_key: bool) -> dict:
        is_valid = cached_status.get("validated", False)
        gemini_models_count = cached_status.get("gemini_models_available", 0)
        last_check = cached_status.get("last_check", "Unknown")

        logger.info("Using cached Google API validation status", extra={"data": {
            "cached": True,
            "valid": is_valid,
            "models_count": gemini_models_count,
            "last_check": last_check
        }})

        return {
            "has_google_api_key": has_api_key,
            "google_api_key_valid": is_valid,
            "gemini_models_available": gemini_models_count,
            "status": "ready" if is_valid else "configured_invalid",
            "cached": True,
            "last_check": last_check
        }

    def _format_response(self, result: dict, has_api_key: bool, new_status: dict) -> dict:
        return {
            "has_google_api_key": has_api_key,
            "google_api_key_valid": result["valid"],
            "gemini_models_available": result["gemini_models_count"],
            "status": "ready" if result["valid"] else "configured_invalid",
            "cached": False,
            "last_check": "Just now"
        }

    def _format_not_configured_response(self) -> dict:
        return {
            "has_google_api_key": False,
            "google_api_key_valid": False,
            "gemini_models_available": 0,
            "status": "not_configured",
            "cached": False,
            "last_check": "Never"
        }

    def _build_cache_status(self, result: dict, now: str, cached_status: dict) -> dict:
        return {
            "validated": result["valid"],
            "validated_at": now if result["valid"] else cached_status.get("validated_at"),
            "validation_error": None if result["valid"] else "API key validation failed",
            "last_check": now,
            "gemini_models_available": result["gemini_models_count"]
        }


class LiteLLMStatusChecker(ExternalServiceStatusChecker):
    """Status checker for LiteLLM API."""

    cache_key = "litellm_master_key"
    service_name = "LiteLLM"

    def _has_api_key(self) -> bool:
        from config import settings as app_settings
        return bool(app_settings.LITELLM_MASTER_KEY)

    async def _perform_check(self) -> dict:
        from config import settings as app_settings

        is_valid = False
        base_url = app_settings.LITELLM_BASE_URL

        try:
            async with aiohttp.ClientSession() as client_session:
                async with client_session.get(
                    f"{app_settings.LITELLM_BASE_URL}/v1/models",
                    headers={"Authorization": f"Bearer {app_settings.LITELLM_MASTER_KEY}"},
                    timeout=10
                ) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            is_valid = isinstance(data, dict) and "data" in data
                        except (ValueError, aiohttp.ContentTypeError):
                            is_valid = False
        except Exception as e:
            logger.warning(f"LiteLLM API validation failed: {e}")

        return {"valid": is_valid, "base_url": base_url}

    def _format_cached_response(self, cached_status: dict, has_api_key: bool) -> dict:
        from config import settings as app_settings

        is_valid = cached_status.get("validated", False)
        base_url = cached_status.get("base_url", app_settings.LITELLM_BASE_URL)
        last_check = cached_status.get("last_check", "Unknown")

        logger.info("Using cached LiteLLM API validation status", extra={"data": {
            "cached": True,
            "valid": is_valid,
            "base_url": base_url,
            "last_check": last_check
        }})

        return {
            "has_litellm_master_key": has_api_key,
            "litellm_master_key_valid": is_valid,
            "base_url": base_url,
            "status": "ready" if is_valid else "configured_invalid",
            "cached": True,
            "last_check": last_check
        }

    def _format_response(self, result: dict, has_api_key: bool, new_status: dict) -> dict:
        return {
            "has_litellm_master_key": has_api_key,
            "litellm_master_key_valid": result["valid"],
            "base_url": result["base_url"],
            "status": "ready" if result["valid"] else "configured_invalid",
            "cached": False,
            "last_check": "Just now"
        }

    def _format_not_configured_response(self) -> dict:
        from config import settings as app_settings
        return {
            "has_litellm_master_key": False,
            "litellm_master_key_valid": False,
            "base_url": app_settings.LITELLM_BASE_URL,
            "status": "not_configured",
            "cached": False,
            "last_check": "Never"
        }

    def _build_cache_status(self, result: dict, now: str, cached_status: dict) -> dict:
        return {
            "validated": result["valid"],
            "validated_at": now if result["valid"] else cached_status.get("validated_at"),
            "validation_error": None if result["valid"] else "API key validation failed",
            "last_check": now,
            "base_url": result["base_url"]
        }


class OpenRouterStatusChecker(ExternalServiceStatusChecker):
    """Status checker for OpenRouter API."""

    cache_key = "openrouter_api_key"
    service_name = "OpenRouter"

    def _has_api_key(self) -> bool:
        from config import settings as app_settings
        return bool(app_settings.OPENROUTER_API_KEY)

    async def _perform_check(self) -> dict:
        from config import settings as app_settings

        is_valid = False
        models_count = 0

        try:
            async with aiohttp.ClientSession() as client_session:
                async with client_session.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {app_settings.OPENROUTER_API_KEY.get_secret_value()}"},
                    timeout=10
                ) as response:
                    if response.status == 200:
                        models_data = await response.json()
                        models_count = len(models_data.get("data", []))
                        is_valid = True
        except Exception as e:
            logger.warning(f"OpenRouter API validation failed: {e}")

        return {"valid": is_valid, "models_count": models_count}

    def _format_cached_response(self, cached_status: dict, has_api_key: bool) -> dict:
        is_valid = cached_status.get("validated", False)
        models_count = cached_status.get("models_available", 0)
        last_check = cached_status.get("last_check", "Unknown")

        logger.info("Using cached OpenRouter API validation status", extra={"data": {
            "cached": True,
            "valid": is_valid,
            "models_count": models_count,
            "last_check": last_check
        }})

        return {
            "has_openrouter_api_key": has_api_key,
            "openrouter_api_key_valid": is_valid,
            "models_available": models_count,
            "status": "ready" if is_valid else "configured_invalid",
            "cached": True,
            "last_check": last_check
        }

    def _format_response(self, result: dict, has_api_key: bool, new_status: dict) -> dict:
        return {
            "has_openrouter_api_key": has_api_key,
            "openrouter_api_key_valid": result["valid"],
            "models_available": result["models_count"],
            "status": "ready" if result["valid"] else "configured_invalid",
            "cached": False,
            "last_check": "Just now"
        }

    def _format_not_configured_response(self) -> dict:
        return {
            "has_openrouter_api_key": False,
            "openrouter_api_key_valid": False,
            "models_available": 0,
            "status": "not_configured",
            "cached": False,
            "last_check": "Never"
        }

    def _build_cache_status(self, result: dict, now: str, cached_status: dict) -> dict:
        return {
            "validated": result["valid"],
            "validated_at": now if result["valid"] else cached_status.get("validated_at"),
            "validation_error": None if result["valid"] else "API key validation failed",
            "last_check": now,
            "models_available": result["models_count"]
        }


class PhoenixStatusChecker:
    """Status checker for Phoenix observability service (no API key needed)."""

    async def get_status(self) -> dict:
        """Get Phoenix status. Phoenix is self-hosted and doesn't require API keys."""
        from config import settings as app_settings
        from utils.phoenix_integration import check_phoenix_health

        health = await check_phoenix_health()

        return {
            "phoenix_enabled": app_settings.PHOENIX_ENABLED,
            "phoenix_host": app_settings.PHOENIX_HOST,
            "phoenix_healthy": health.get("healthy", False),
            "status": "ready" if health.get("healthy") else ("disabled" if not app_settings.PHOENIX_ENABLED else "unavailable"),
            "error": health.get("error"),
        }


# Singleton instances for use by endpoints
google_status_checker = GoogleAPIStatusChecker()
litellm_status_checker = LiteLLMStatusChecker()
openrouter_status_checker = OpenRouterStatusChecker()
phoenix_status_checker = PhoenixStatusChecker()
