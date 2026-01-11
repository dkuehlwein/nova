"""
Settings API Endpoints for Nova's 3-Tier Configuration System

Provides API endpoints for managing Tier 3 (database) user settings.
NEVER exposes Tier 1 (config.py) or Tier 2 (.env) values for security.

API key management endpoints have been moved to api_key_endpoints.py.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config import Defaults
from database.database import get_db_session
from models.user_settings import (
    UserSettings,
    UserSettingsModel,
    UserSettingsUpdateModel,
    OnboardingStatusModel
)
from utils.logging import get_logger

logger = get_logger("settings_api")

router = APIRouter(prefix="/api/user-settings", tags=["user-settings"])


async def _handle_chat_model_change(model_name: str) -> None:
    """
    Handle LLM model changes.

    In the LiteLLM-first architecture, all models route through LiteLLM.
    Model loading is handled by the external LLM API (e.g., LM Studio, Ollama).
    No container restarts needed - just log the change.

    Args:
        model_name: The new model name selected by the user
    """
    logger.info(f"Model change detected: {model_name}")


@router.get("/status", response_model=OnboardingStatusModel)
async def get_onboarding_status(session: AsyncSession = Depends(get_db_session)):
    """
    Check if user has completed onboarding and what setup is required.
    """
    try:
        from database.database import UserSettingsService

        # Get user settings using the current session
        settings = await UserSettingsService.get_user_settings(session)

        if not settings:
            # No settings exist - first time setup required
            return OnboardingStatusModel(
                onboarding_complete=False,
                missing_required_settings=["user_profile"],
                setup_required=True
            )

        missing = []
        if not settings.full_name or not settings.email:
            missing.append("user_profile")

        return OnboardingStatusModel(
            onboarding_complete=settings.onboarding_complete,
            missing_required_settings=missing,
            setup_required=len(missing) > 0 or not settings.onboarding_complete
        )

    except Exception as e:
        logger.error("Failed to get onboarding status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get onboarding status")


@router.get("/", response_model=UserSettingsModel)
async def get_user_settings(session: AsyncSession = Depends(get_db_session)):
    """
    Get current user settings (Tier 3 only).
    NEVER returns Tier 1 or Tier 2 configuration values.
    """
    try:
        from database.database import UserSettingsService

        # Get user settings using the current session
        settings = await UserSettingsService.get_user_settings(session)

        if not settings:
            # Create default settings for first-time user
            settings = UserSettings()
            session.add(settings)
            await session.commit()
            await session.refresh(settings)

        return UserSettingsModel.model_validate(settings)

    except Exception as e:
        logger.error("Failed to get user settings", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get user settings")


@router.patch("/", response_model=UserSettingsModel)
async def update_user_settings(
    updates: UserSettingsUpdateModel,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Update user settings (Tier 3 only).
    Performs partial updates - only provided fields are changed.
    """
    try:
        from database.database import UserSettingsService
        settings = await UserSettingsService.get_user_settings(session)

        if not settings:
            # Create new settings if none exist
            settings = UserSettings()
            session.add(settings)
            # Flush to get the ID for the new object
            await session.flush()

        # Apply updates (only non-None values)
        update_data = updates.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in update_data.items():
            if hasattr(settings, field):
                setattr(settings, field, value)

        await session.commit()
        await session.refresh(settings)  # Refresh to ensure all attributes are loaded

        # If LLM-related settings were updated, publish Redis event for chat agent cache clearing
        llm_fields = {
            "chat_llm_model", "chat_llm_temperature", "chat_llm_max_tokens",
            "memory_llm_model", "memory_llm_temperature", "memory_llm_max_tokens",
            "embedding_model", "litellm_base_url", "litellm_master_key"
        }
        if any(field in update_data for field in llm_fields):
            try:
                # Publish Redis event for real-time updates
                from models.events import create_llm_settings_updated_event
                from utils.redis_manager import publish

                llm_event = create_llm_settings_updated_event(
                    model=settings.chat_llm_model,
                    temperature=settings.chat_llm_temperature,
                    max_tokens=settings.chat_llm_max_tokens,
                    source="settings-api"
                )

                await publish(llm_event)

                logger.info(
                    "Published LLM settings update event",
                    extra={"data": {"event_id": llm_event.id, "updated_fields": list(update_data.keys())}}
                )

                # Log model change - external LLM API (LM Studio, etc.) handles model loading
                if "chat_llm_model" in update_data:
                    await _handle_chat_model_change(settings.chat_llm_model)

            except Exception as e:
                logger.warning(f"Failed to publish LLM settings event: {e}")

        logger.info(
            "User settings updated",
            extra={
                "data": {
                    "settings_id": str(settings.id),
                    "updated_fields": list(update_data.keys())
                }
            }
        )

        return UserSettingsModel.model_validate(settings)

    except Exception as e:
        logger.error("Failed to update user settings", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update user settings")


class OnboardingCompleteRequest(BaseModel):
    """Request model for completing onboarding with model selection."""
    chat_llm_model: Optional[str] = Field(default=Defaults.CHAT_LLM_MODEL, description="Chat model selection")
    memory_llm_model: Optional[str] = Field(default=Defaults.MEMORY_LLM_MODEL, description="Memory model selection")
    memory_small_llm_model: Optional[str] = Field(default=None, description="Memory small model selection (defaults to memory_llm_model if not set)")
    embedding_model: Optional[str] = Field(default=Defaults.EMBEDDING_MODEL, description="Embedding model selection")
    litellm_base_url: Optional[str] = Field(default=Defaults.LITELLM_BASE_URL, description="LiteLLM base URL")
    litellm_master_key: Optional[str] = Field(default="sk-1234", description="LiteLLM master key")


@router.post("/complete-onboarding")
async def complete_onboarding(
    request: OnboardingCompleteRequest = OnboardingCompleteRequest(),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Complete onboarding with optional model selection (LiteLLM-first approach).
    """
    try:
        from database.database import UserSettingsService

        # Get or create settings using the current session
        settings = await UserSettingsService.get_user_settings(session)

        if not settings:
            settings = UserSettings()
            session.add(settings)

        # Mark onboarding complete and set selected models and connection settings
        settings.onboarding_complete = True
        settings.chat_llm_model = request.chat_llm_model
        settings.memory_llm_model = request.memory_llm_model
        # Use memory_small_llm_model if provided, otherwise default to memory_llm_model
        settings.memory_small_llm_model = request.memory_small_llm_model or request.memory_llm_model
        settings.embedding_model = request.embedding_model
        settings.litellm_base_url = request.litellm_base_url
        settings.litellm_master_key = request.litellm_master_key

        await session.commit()

        logger.info(f"Onboarding completed with models: chat={request.chat_llm_model}, memory={request.memory_llm_model}, memory_small={settings.memory_small_llm_model}, embedding={request.embedding_model}, litellm_url={request.litellm_base_url}")

        return {
            "status": "success",
            "message": "Onboarding completed with LiteLLM-first defaults",
            "models": {
                "chat_llm_model": request.chat_llm_model,
                "memory_llm_model": request.memory_llm_model,
                "memory_small_llm_model": settings.memory_small_llm_model,
                "embedding_model": request.embedding_model,
                "litellm_base_url": request.litellm_base_url,
                "litellm_master_key": request.litellm_master_key
            }
        }

    except Exception as e:
        logger.error("Failed to complete onboarding", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to complete onboarding")


async def _check_service_connections(app_settings):
    """Check connectivity to external services."""
    import aiohttp
    import asyncio
    from neo4j import GraphDatabase

    async def check_http_service(url: str, api_key: Optional[str] = None, timeout: int = 5) -> dict:
        """Check if HTTP service is reachable, with optional API key authentication."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    return {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "status_code": response.status,
                        "url": url
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "url": url
            }

    def check_neo4j_service(uri: str, user: str, password: str) -> dict:
        """Check if Neo4j service is reachable."""
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            return {
                "status": "healthy",
                "uri": uri
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "uri": uri
            }

    # Run checks in parallel
    local_llm_check = check_http_service(f"{app_settings.LLM_API_BASE_URL}/v1/models")
    litellm_check = check_http_service(f"{app_settings.LITELLM_BASE_URL}/health", app_settings.LITELLM_MASTER_KEY)

    # Neo4j check (synchronous)
    neo4j_status = check_neo4j_service(
        app_settings.NEO4J_URI,
        app_settings.NEO4J_USER,
        app_settings.NEO4J_PASSWORD
    )

    # Wait for HTTP checks
    local_llm_status, litellm_status = await asyncio.gather(
        local_llm_check, litellm_check, return_exceptions=True
    )

    # Handle exceptions
    if isinstance(local_llm_status, Exception):
        local_llm_status = {"status": "unhealthy", "error": str(local_llm_status)}
    if isinstance(litellm_status, Exception):
        litellm_status = {"status": "unhealthy", "error": str(litellm_status)}

    return {
        "local_llm": local_llm_status,
        "litellm": litellm_status,
        "neo4j": neo4j_status
    }


@router.get("/system-status")
async def get_system_status():
    """
    Get read-only system status information.
    Shows non-sensitive Tier 1 and Tier 2 info for debugging.
    NEVER exposes secrets like API keys or passwords.
    """
    try:
        from config import settings as app_settings

        # Test service connections
        service_status = await _check_service_connections(app_settings)

        # Safe, non-sensitive system information
        status = {
            "environment": "docker" if app_settings._is_running_in_docker() else "local",
            "log_level": app_settings.LOG_LEVEL,
            "email_enabled": app_settings.EMAIL_ENABLED,
            # MCP servers are now managed by LiteLLM (ADR-015)
            # Use /api/mcp endpoint for MCP server status
            "mcp_servers_source": "litellm",
            "services": {
                "chat_agent_port": app_settings.CHAT_AGENT_PORT,
                "core_agent_port": app_settings.CORE_AGENT_PORT,
                "local_llm": service_status["local_llm"],
                "litellm": service_status["litellm"],
                "neo4j": service_status["neo4j"]
            },
            "api_keys_configured": {
                "google": bool(app_settings.GOOGLE_API_KEY),
                "openrouter": bool(app_settings.OPENROUTER_API_KEY)
            },
            "observability": {
                "phoenix_enabled": app_settings.PHOENIX_ENABLED,
                "phoenix_host": app_settings.PHOENIX_HOST,
            },
            "google_models_available": bool(app_settings.GOOGLE_API_KEY)  # Indicates if Gemini models should be available
        }

        return status

    except Exception as e:
        logger.error("Failed to get system status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get system status")
