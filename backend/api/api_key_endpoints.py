"""
API Key Management Endpoints

Provides API endpoints for validating, saving, and checking status of external service API keys.
Extracted from settings_endpoints.py to separate API key concerns from user settings CRUD.
"""

from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database.database import get_db_session
from utils.logging import get_logger

logger = get_logger("api_key_endpoints")

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


@router.post("/validate")
async def validate_api_key(
    request: dict,
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Validate an API key by making a test call to the service.
    Caches validation results in user settings for future reference.
    """
    from database.database import UserSettingsService
    from services.api_key_validator import VALIDATION_METHODS

    try:
        key_type = request.get("key_type")
        api_key = request.get("api_key")

        logger.info(
            "API key validation request",
            extra={
                "data": {
                    "key_type": key_type,
                    "api_key_length": len(api_key) if api_key else 0,
                    "has_api_key": bool(api_key)
                }
            }
        )

        if not key_type or not api_key:
            raise HTTPException(status_code=400, detail="key_type and api_key are required")

        settings = await UserSettingsService.get_user_settings(db_session)
        if not settings:
            settings = await UserSettingsService.create_user_settings(db_session)

        logger.info("Performing fresh API key validation", extra={"data": {"key_type": key_type}})

        if key_type not in VALIDATION_METHODS:
            raise HTTPException(status_code=400, detail=f"Unknown key_type: {key_type}")

        result = await VALIDATION_METHODS[key_type](db_session, api_key, settings)

        if result["valid"]:
            logger.info("API key validation successful", extra={"data": result})
        else:
            logger.warning("API key validation failed", extra={"data": result})

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to validate API key", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to validate API key")


@router.post("/save")
async def save_api_keys(
    request: dict,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Save validated API keys to .env file (Tier 2 configuration).
    Also updates validation status cache in user settings (Tier 3).
    Only saves keys that have been previously validated.
    """
    from database.database import UserSettingsService

    try:
        api_keys = request.get("api_keys", {})
        if not api_keys:
            raise HTTPException(status_code=400, detail="No API keys provided")

        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            settings = await UserSettingsService.create_user_settings(session)

        # Path to .env file
        env_paths = [
            Path(__file__).parent.parent.parent / ".env",
            Path(__file__).parent.parent / ".env"
        ]

        env_file = None
        for path in env_paths:
            if path.exists():
                env_file = path
                break

        if not env_file:
            env_file = env_paths[0]
            env_file.parent.mkdir(parents=True, exist_ok=True)

        # Read existing .env content
        env_content = ""
        if env_file.exists():
            env_content = env_file.read_text()

        env_lines = env_content.strip().split('\n') if env_content.strip() else []

        key_mappings = {
            "google_api_key": "GOOGLE_API_KEY",
            "litellm_master_key": "LITELLM_MASTER_KEY",
            "openrouter_api_key": "OPENROUTER_API_KEY"
        }

        updated_keys = []
        for key_type, api_key in api_keys.items():
            if not api_key or not api_key.strip():
                continue

            env_var_name = key_mappings.get(key_type)
            if not env_var_name:
                continue

            updated = False
            for i, line in enumerate(env_lines):
                if line.startswith(f"{env_var_name}="):
                    env_lines[i] = f'{env_var_name}="{api_key}"'
                    updated = True
                    break

            if not updated:
                env_lines.append(f'{env_var_name}="{api_key}"')

            updated_keys.append(env_var_name)

        should_refresh_models = False
        if updated_keys:
            env_file.write_text('\n'.join(env_lines) + '\n')

            now = datetime.now(timezone.utc).isoformat()
            for key_type in api_keys.keys():
                if key_type == "google_api_key":
                    if key_type not in settings.api_key_validation_status:
                        settings.api_key_validation_status[key_type] = {}

                    settings.api_key_validation_status[key_type].update({
                        "configured": True,
                        "configured_at": now,
                        "last_updated": now
                    })

            flag_modified(settings, "api_key_validation_status")
            await UserSettingsService.update_user_settings(session, settings)

            logger.info(
                "API keys saved to .env file and validation cache updated",
                extra={
                    "data": {
                        "env_file": str(env_file),
                        "updated_keys": updated_keys,
                        "validation_cache_updated": list(api_keys.keys())
                    }
                }
            )

            provider_keys = {"GOOGLE_API_KEY", "OPENROUTER_API_KEY"}
            should_refresh_models = bool(set(updated_keys) & provider_keys)

            if should_refresh_models:
                try:
                    from services.llm_service import llm_service
                    from database.database import db_manager

                    async with db_manager.get_session() as refresh_session:
                        await llm_service.refresh_models_after_api_key_update(refresh_session)

                    updated_providers = [key for key in updated_keys if key in provider_keys]
                    logger.info("Triggered model refresh after API key update", extra={"data": {"updated_providers": updated_providers}})
                except Exception as e:
                    logger.warning("Failed to refresh models after API key update", extra={"data": {"error": str(e)}})

        return {
            "status": "success",
            "message": f"Saved {len(updated_keys)} API keys to .env file",
            "updated_keys": updated_keys,
            "env_file": str(env_file),
            "models_refreshed": should_refresh_models
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save API keys", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save API keys: {str(e)}")


@router.get("/google-status")
async def get_google_api_status(
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the current status of Google API key and model availability.
    Uses cached validation status unless force_refresh=True.
    """
    from database.database import UserSettingsService
    from services.external_service_status import google_status_checker

    try:
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            settings = await UserSettingsService.create_user_settings(session)

        return await google_status_checker.get_status(session, settings, force_refresh)

    except Exception as e:
        logger.error("Failed to get Google API status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get Google API status")


@router.get("/litellm-status")
async def get_litellm_api_status(
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the current status of LiteLLM master key and availability.
    Uses cached validation status unless force_refresh=True.
    """
    from database.database import UserSettingsService
    from services.external_service_status import litellm_status_checker

    try:
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            settings = await UserSettingsService.create_user_settings(session)

        return await litellm_status_checker.get_status(session, settings, force_refresh)

    except Exception as e:
        logger.error("Failed to get LiteLLM API status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get LiteLLM API status")


@router.get("/openrouter-status")
async def get_openrouter_api_status(
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the current status of OpenRouter API key and availability.
    Uses cached validation status unless force_refresh=True.
    """
    from database.database import UserSettingsService
    from services.external_service_status import openrouter_status_checker

    try:
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            settings = await UserSettingsService.create_user_settings(session)

        return await openrouter_status_checker.get_status(session, settings, force_refresh)

    except Exception as e:
        logger.error("Failed to get OpenRouter API status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get OpenRouter API status")


@router.get("/phoenix-status")
async def get_phoenix_status():
    """
    Get the current status of Phoenix observability service.
    Phoenix is self-hosted and doesn't require API keys.
    """
    from services.external_service_status import phoenix_status_checker

    try:
        return await phoenix_status_checker.get_status()

    except Exception as e:
        logger.error("Failed to get Phoenix status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get Phoenix status")
