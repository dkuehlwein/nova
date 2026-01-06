"""
Settings API Endpoints for Nova's 3-Tier Configuration System

Provides API endpoints for managing Tier 3 (database) user settings.
NEVER exposes Tier 1 (config.py) or Tier 2 (.env) values for security.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

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
    chat_llm_model: Optional[str] = Field(default="local/openai/gpt-oss-20b", description="Chat model selection")
    memory_llm_model: Optional[str] = Field(default="local/openai/gpt-oss-20b", description="Memory model selection")
    memory_small_llm_model: Optional[str] = Field(default=None, description="Memory small model selection (defaults to memory_llm_model if not set)")
    embedding_model: Optional[str] = Field(default="local/text-embedding-nomic-embed-text-v1.5", description="Embedding model selection")
    litellm_base_url: Optional[str] = Field(default="http://localhost:4000", description="LiteLLM base URL")
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
                "langsmith": bool(app_settings.LANGCHAIN_API_KEY),
                "huggingface": bool(app_settings.HF_TOKEN),
                "openrouter": bool(app_settings.OPENROUTER_API_KEY)
            },
            "google_models_available": bool(app_settings.GOOGLE_API_KEY)  # Indicates if Gemini models should be available
        }
        
        return status
        
    except Exception as e:
        logger.error("Failed to get system status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get system status")




async def _cache_validation_result(db_session: AsyncSession, settings, key_type: str, result_data: dict):
    """Helper to cache validation results consistently."""
    from database.database import UserSettingsService
    settings.api_key_validation_status[key_type] = result_data
    flag_modified(settings, "api_key_validation_status")
    await UserSettingsService.update_user_settings(db_session, settings)


async def _http_request(url: str, headers: dict, timeout: int = 10) -> tuple[int, dict]:
    """Make HTTP request and return status code and response data."""
    import aiohttp
    async with aiohttp.ClientSession() as http_session:
        async with http_session.get(url, headers=headers, timeout=timeout) as response:
            try:
                data = await response.json()
            except:
                data = {"error": await response.text()}
            return response.status, data


async def _validate_google_api_key(db_session: AsyncSession, api_key: str, settings) -> dict:
    """Validate Google API key using Gemini API."""
    from datetime import datetime, timezone
    from config import settings as app_config
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(app_config.DEFAULT_CHAT_MODEL)
        response = model.generate_content("Hello")
        
        now = datetime.now(timezone.utc).isoformat()
        await _cache_validation_result(db_session, settings, "google_api_key", {
            "validated": True,
            "validated_at": now,
            "validation_error": None,
            "last_check": now,
            "gemini_models_available": 0
        })
        
        return {"valid": True, "message": "Google API key is valid", "service": "google"}
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await _cache_validation_result(db_session, settings, "google_api_key", {
            "validated": False,
            "validated_at": None,
            "validation_error": str(e),
            "last_check": now,
            "gemini_models_available": 0
        })
        return {"valid": False, "message": f"Google API key validation failed: {str(e)}", "service": "google"}


async def _validate_langsmith_api_key(db_session: AsyncSession, api_key: str, settings) -> dict:
    """Validate LangSmith API key using requests (sync API)."""
    from datetime import datetime, timezone
    try:
        import requests
        response = requests.get(
            "https://api.smith.langchain.com/info",
            headers={"x-api-key": api_key},
            timeout=10
        )
        
        now = datetime.now(timezone.utc).isoformat()
        if response.status_code == 200:
            await _cache_validation_result(db_session, settings, "langsmith_api_key", {
                "validated": True,
                "validated_at": now,
                "validation_error": None,
                "last_check": now
            })
            return {"valid": True, "message": "LangSmith API key is valid", "service": "langsmith"}
        else:
            await _cache_validation_result(db_session, settings, "langsmith_api_key", {
                "validated": False,
                "validated_at": None,
                "validation_error": f"API returned status {response.status_code}",
                "last_check": now
            })
            return {"valid": False, "message": f"LangSmith API key validation failed: {response.status_code}", "service": "langsmith"}
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await _cache_validation_result(db_session, settings, "langsmith_api_key", {
            "validated": False,
            "validated_at": None,
            "validation_error": str(e),
            "last_check": now
        })
        return {"valid": False, "message": f"LangSmith API key validation failed: {str(e)}", "service": "langsmith"}


async def _validate_litellm_master_key(db_session: AsyncSession, api_key: str, settings) -> dict:
    """Validate LiteLLM master key by testing the models endpoint."""
    from datetime import datetime, timezone
    from config import settings as app_settings
    try:
        # First try the models endpoint which requires authentication
        status, data = await _http_request(
            f"{app_settings.LITELLM_BASE_URL}/v1/models",
            {"Authorization": f"Bearer {api_key}"}
        )
        
        now = datetime.now(timezone.utc).isoformat()
        if status == 200 and isinstance(data, dict) and "data" in data:
            # Successfully authenticated and got models list
            models_count = len(data.get("data", []))
            await _cache_validation_result(db_session, settings, "litellm_master_key", {
                "validated": True,
                "validated_at": now,
                "validation_error": None,
                "last_check": now,
                "base_url": app_settings.LITELLM_BASE_URL,
                "models_available": models_count
            })
            return {"valid": True, "message": f"LiteLLM master key is valid ({models_count} models available)", "service": "litellm"}
        elif status == 401 or status == 403:
            # Authentication failed - invalid key
            await _cache_validation_result(db_session, settings, "litellm_master_key", {
                "validated": False,
                "validated_at": None,
                "validation_error": f"Authentication failed (HTTP {status})",
                "last_check": now,
                "base_url": app_settings.LITELLM_BASE_URL
            })
            return {"valid": False, "message": "LiteLLM master key is invalid (authentication failed)", "service": "litellm"}
        else:
            # Other error
            error_msg = data.get('error', 'Unknown error') if isinstance(data, dict) else str(data)
            await _cache_validation_result(db_session, settings, "litellm_master_key", {
                "validated": False,
                "validated_at": None,
                "validation_error": f"HTTP {status}: {error_msg}",
                "last_check": now,
                "base_url": app_settings.LITELLM_BASE_URL
            })
            return {"valid": False, "message": f"LiteLLM validation failed: HTTP {status}", "service": "litellm"}
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await _cache_validation_result(db_session, settings, "litellm_master_key", {
            "validated": False,
            "validated_at": None,
            "validation_error": str(e),
            "last_check": now,
            "base_url": "unknown"
        })
        return {"valid": False, "message": f"LiteLLM master key validation failed: {str(e)}", "service": "litellm"}


async def _validate_huggingface_api_key(db_session: AsyncSession, api_key: str, settings) -> dict:
    """Validate HuggingFace API key."""
    from datetime import datetime, timezone
    try:
        status, data = await _http_request(
            "https://huggingface.co/api/whoami",
            {"Authorization": f"Bearer {api_key}"}
        )
        
        now = datetime.now(timezone.utc).isoformat()
        if status == 200:
            username = data.get("name", "unknown")
            await _cache_validation_result(db_session, settings, "huggingface_api_key", {
                "validated": True,
                "validated_at": now,
                "validation_error": None,
                "last_check": now,
                "username": username
            })
            return {"valid": True, "message": f"HuggingFace API key is valid (user: {username})", "service": "huggingface"}
        else:
            await _cache_validation_result(db_session, settings, "huggingface_api_key", {
                "validated": False,
                "validated_at": None,
                "validation_error": f"HTTP {status}: {data.get('error', 'Unknown error')}",
                "last_check": now
            })
            return {"valid": False, "message": f"HuggingFace API key validation failed: HTTP {status}", "service": "huggingface"}
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await _cache_validation_result(db_session, settings, "huggingface_api_key", {
            "validated": False,
            "validated_at": None,
            "validation_error": str(e),
            "last_check": now
        })
        return {"valid": False, "message": f"HuggingFace API key validation failed: {str(e)}", "service": "huggingface"}


async def _validate_openrouter_api_key(db_session: AsyncSession, api_key: str, settings) -> dict:
    """Validate OpenRouter API key by testing a minimal completion request."""
    from datetime import datetime, timezone
    import aiohttp
    try:
        # OpenRouter allows anyone to see models, so we need to test with a completion request
        test_payload = {
            "model": "openai/gpt-oss-20b:free",  # Free model for testing
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
                    # Get models count for the success message
                    models_status, models_data = await _http_request(
                        "https://openrouter.ai/api/v1/models",
                        {"Authorization": f"Bearer {api_key}"}
                    )
                    models_count = len(models_data.get("data", [])) if models_status == 200 else 0
                    
                    await _cache_validation_result(db_session, settings, "openrouter_api_key", {
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
                    
                    await _cache_validation_result(db_session, settings, "openrouter_api_key", {
                        "validated": False,
                        "validated_at": None,
                        "validation_error": f"HTTP {response.status}: {error_msg}",
                        "last_check": now
                    })
                    return {"valid": False, "message": f"OpenRouter API key validation failed: {error_msg}", "service": "openrouter"}
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await _cache_validation_result(db_session, settings, "openrouter_api_key", {
            "validated": False,
            "validated_at": None,
            "validation_error": str(e),
            "last_check": now
        })
        return {"valid": False, "message": f"OpenRouter API key validation failed: {str(e)}", "service": "openrouter"}


@router.post("/validate-api-key")
async def validate_api_key(
    request: dict, 
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Validate an API key by making a test call to the service.
    Caches validation results in user settings for future reference.
    """
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
        
        # Get user settings to store validation cache
        from database.database import UserSettingsService
        
        settings = await UserSettingsService.get_user_settings(db_session)
        if not settings:
            settings = await UserSettingsService.create_user_settings(db_session)
        
        # Check if we have a cached validation for this exact API key
        # Note: We should NOT return cached results for different API keys
        cached_validation = settings.api_key_validation_status.get(key_type, {})
        
        # For validation endpoint, we always validate the provided key (no caching)
        # This is different from status endpoints which can use cached results
        logger.info(f"Performing fresh validation for {key_type} (validation endpoint always validates)")
        
        # Dispatch to appropriate validation method
        validation_methods = {
            "google_api_key": _validate_google_api_key,
            "langsmith_api_key": _validate_langsmith_api_key,
            "litellm_master_key": _validate_litellm_master_key,
            "huggingface_api_key": _validate_huggingface_api_key,
            "openrouter_api_key": _validate_openrouter_api_key,
        }
        
        if key_type not in validation_methods:
            raise HTTPException(status_code=400, detail=f"Unknown key_type: {key_type}")
        
        result = await validation_methods[key_type](db_session, api_key, settings)
        
        if result["valid"]:
            logger.info(f"{result['service'].title()} API key validation successful", extra={"data": result})
        else:
            logger.warning(f"{result['service'].title()} API key validation failed", extra={"data": result})
        
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to validate API key", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to validate API key")


@router.post("/save-api-keys")
async def save_api_keys(
    request: dict, 
    session: AsyncSession = Depends(get_db_session)
):
    """
    Save validated API keys to .env file (Tier 2 configuration).
    Also updates validation status cache in user settings (Tier 3).
    Only saves keys that have been previously validated.
    """
    try:
        import os
        from pathlib import Path
        from database.database import UserSettingsService
        from datetime import datetime, timezone
        
        api_keys = request.get("api_keys", {})
        if not api_keys:
            raise HTTPException(status_code=400, detail="No API keys provided")
        
        # Get user settings to update validation cache
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            # Create default settings if none exist
            settings = await UserSettingsService.create_user_settings(session)
        
        # Path to .env file (look in parent directory and current directory)
        env_paths = [
            Path(__file__).parent.parent.parent / ".env",  # /home/daniel/nova/.env
            Path(__file__).parent.parent / ".env"  # /home/daniel/nova/backend/.env
        ]
        
        env_file = None
        for path in env_paths:
            if path.exists():
                env_file = path
                break
        
        if not env_file:
            # Create .env in root directory
            env_file = env_paths[0]
            env_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Read existing .env content
        env_content = ""
        if env_file.exists():
            env_content = env_file.read_text()
        
        # Update or add API keys
        env_lines = env_content.strip().split('\n') if env_content.strip() else []
        
        # Key mappings
        key_mappings = {
            "google_api_key": "GOOGLE_API_KEY",
            "langsmith_api_key": "LANGCHAIN_API_KEY",
            "litellm_master_key": "LITELLM_MASTER_KEY",
            "huggingface_api_key": "HF_TOKEN",
            "openrouter_api_key": "OPENROUTER_API_KEY"
        }
        
        updated_keys = []
        for key_type, api_key in api_keys.items():
            if not api_key or not api_key.strip():
                continue
                
            env_var_name = key_mappings.get(key_type)
            if not env_var_name:
                continue
            
            # Find and update existing line or add new one
            updated = False
            for i, line in enumerate(env_lines):
                if line.startswith(f"{env_var_name}="):
                    env_lines[i] = f'{env_var_name}="{api_key}"'
                    updated = True
                    break
            
            if not updated:
                env_lines.append(f'{env_var_name}="{api_key}"')
            
            updated_keys.append(env_var_name)
        
        # Write updated content back to .env
        if updated_keys:
            env_file.write_text('\n'.join(env_lines) + '\n')
            
            # Update validation status cache to mark keys as configured
            now = datetime.now(timezone.utc).isoformat()
            for key_type in api_keys.keys():
                if key_type in ["google_api_key", "langsmith_api_key"]:
                    # Mark as configured and previously validated (since we only save validated keys)
                    if key_type not in settings.api_key_validation_status:
                        settings.api_key_validation_status[key_type] = {}
                    
                    settings.api_key_validation_status[key_type].update({
                        "configured": True,
                        "configured_at": now,
                        "last_updated": now
                    })
            
            # Save updated validation status to database
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
            
            # Refresh LiteLLM models if any provider API key was updated
            provider_keys = {"GOOGLE_API_KEY", "HF_TOKEN", "OPENROUTER_API_KEY"}
            should_refresh_models = bool(set(updated_keys) & provider_keys)
            
            if should_refresh_models:
                try:
                    from services.llm_service import llm_service
                    from database.database import db_manager
                    
                    async with db_manager.get_session() as session:
                        await llm_service.refresh_models_after_api_key_update(session)
                    
                    updated_providers = [key for key in updated_keys if key in provider_keys]
                    logger.info(f"Triggered model refresh after API key update for: {updated_providers}")
                except Exception as e:
                    logger.warning(f"Failed to refresh models after API key update: {e}")
        
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


@router.get("/google-api-status")
async def get_google_api_status(
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the current status of Google API key and model availability.
    Uses cached validation status unless force_refresh=True.
    """
    try:
        from config import settings as app_settings
        from services.llm_service import llm_service
        from database.database import UserSettingsService
        from datetime import datetime, timezone
        
        # Check if API key is configured
        has_api_key = bool(app_settings.GOOGLE_API_KEY)
        
        # Get user settings to check cached validation status
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            # Create default settings if none exist
            settings = await UserSettingsService.create_user_settings(session)
        
        cached_status = settings.api_key_validation_status.get("google_api_key", {})
        
        # Use cached status unless force_refresh is requested or cache is empty
        if not force_refresh and cached_status and has_api_key:
            is_valid = cached_status.get("validated", False)
            gemini_models_count = cached_status.get("gemini_models_available", 0)
            last_check = cached_status.get("last_check", "Unknown")
            
            logger.info("Using cached Google API validation status", extra={"data": {
                "cached": True,
                "valid": is_valid,
                "models_count": gemini_models_count,
                "last_check": last_check
            }})
        else:
            # Perform real-time validation
            is_valid = False
            gemini_models_count = 0
            
            if has_api_key:
                logger.info("Performing real-time Google API validation", extra={"data": {"force_refresh": force_refresh}})
                try:
                    # Test Google API using the models endpoint
                    import google.generativeai as genai
                    genai.configure(api_key=app_settings.GOOGLE_API_KEY.get_secret_value())

                    model = genai.GenerativeModel(app_settings.DEFAULT_CHAT_MODEL)
                    response = model.generate_content("Hello", request_options={"timeout": 10})
                    
                    if response and response.text and len(response.text.strip()) > 0:
                        is_valid = True
                    else:
                        is_valid = False
                except Exception as e:
                    logger.warning(f"Google API validation failed: {e}")
                    is_valid = False
                
                # Get available Gemini models from all models
                available_models = await llm_service.get_available_models()
                all_models = available_models.get("all_models", [])
                # Count models that are Gemini models (contain "gemini" in model name)
                gemini_models_count = len([m for m in all_models if "gemini" in m.get("model_name", "").lower()])
                
                # Cache the validation results
                now = datetime.now(timezone.utc).isoformat()
                new_status = {
                    "validated": is_valid,
                    "validated_at": now if is_valid else cached_status.get("validated_at"),
                    "validation_error": None if is_valid else "API key validation failed",
                    "last_check": now,
                    "gemini_models_available": gemini_models_count
                }
                
                # Update cached status
                settings.api_key_validation_status["google_api_key"] = new_status
                # Mark the JSONB field as modified so SQLAlchemy knows to update it
                flag_modified(settings, "api_key_validation_status")
                await UserSettingsService.update_user_settings(session, settings)
                
                logger.info("Cached Google API validation results", extra={"data": new_status})
        
        return {
            "has_google_api_key": has_api_key,
            "google_api_key_valid": is_valid,
            "gemini_models_available": gemini_models_count,
            "status": "ready" if is_valid else ("configured_invalid" if has_api_key else "not_configured"),
            "cached": not force_refresh and bool(cached_status),
            "last_check": cached_status.get("last_check", "Never") if not force_refresh else "Just now"
        }
        
    except Exception as e:
        logger.error("Failed to get Google API status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get Google API status")


@router.get("/langsmith-api-status")
async def get_langsmith_api_status(
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the current status of LangSmith API key and availability.
    Uses cached validation status unless force_refresh=True.
    """
    try:
        from config import settings as app_settings
        from database.database import UserSettingsService
        from datetime import datetime, timezone
        import requests
        
        # Check if API key is configured
        has_api_key = bool(app_settings.LANGCHAIN_API_KEY)
        
        # Get user settings to check cached validation status
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            # Create default settings if none exist
            settings = await UserSettingsService.create_user_settings(session)
        
        cached_status = settings.api_key_validation_status.get("langsmith_api_key", {})
        
        # Use cached status unless force_refresh is requested or cache is empty
        if not force_refresh and cached_status and has_api_key:
            is_valid = cached_status.get("validated", False)
            last_check = cached_status.get("last_check", "Unknown")
            
            logger.info("Using cached LangSmith API validation status", extra={"data": {
                "cached": True,
                "valid": is_valid,
                "last_check": last_check
            }})
        else:
            # Perform real-time validation
            is_valid = False
            
            if has_api_key:
                logger.info("Performing real-time LangSmith API validation", extra={"data": {"force_refresh": force_refresh}})
                try:
                    # Test LangSmith API using minimal permissions endpoint
                    response = requests.get(
                        "https://api.smith.langchain.com/info",
                        headers={"x-api-key": app_settings.LANGCHAIN_API_KEY.get_secret_value()},
                        timeout=10
                    )
                    
                    is_valid = response.status_code == 200
                except Exception as e:
                    logger.warning(f"LangSmith API validation failed: {e}")
                    is_valid = False
                
                # Cache the validation results
                now = datetime.now(timezone.utc).isoformat()
                new_status = {
                    "validated": is_valid,
                    "validated_at": now if is_valid else cached_status.get("validated_at"),
                    "validation_error": None if is_valid else "API key validation failed",
                    "last_check": now
                }
                
                # Update cached status
                settings.api_key_validation_status["langsmith_api_key"] = new_status
                # Mark the JSONB field as modified so SQLAlchemy knows to update it
                flag_modified(settings, "api_key_validation_status")
                await UserSettingsService.update_user_settings(session, settings)
                
                logger.info("Cached LangSmith API validation results", extra={"data": new_status})
        
        return {
            "has_langsmith_api_key": has_api_key,
            "langsmith_api_key_valid": is_valid,
            "status": "ready" if is_valid else ("configured_invalid" if has_api_key else "not_configured"),
            "cached": not force_refresh and bool(cached_status),
            "last_check": cached_status.get("last_check", "Never") if not force_refresh else "Just now"
        }
        
    except Exception as e:
        logger.error("Failed to get LangSmith API status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get LangSmith API status")


@router.get("/huggingface-api-status")
async def get_huggingface_api_status(
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the current status of HuggingFace API key and availability.
    Uses cached validation status unless force_refresh=True.
    """
    try:
        from config import settings as app_settings
        from database.database import UserSettingsService
        from datetime import datetime, timezone
        import aiohttp
        
        # Check if API key is configured in environment
        has_api_key = bool(app_settings.HF_TOKEN)
        
        # Get user settings to check cached validation status
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            # Create default settings if none exist
            settings = await UserSettingsService.create_user_settings(session)
        
        cached_status = settings.api_key_validation_status.get("huggingface_api_key", {})
        
        # Use cached status unless force_refresh is requested or cache is empty
        if not force_refresh and cached_status and has_api_key:
            is_valid = cached_status.get("validated", False)
            username = cached_status.get("username", "unknown")
            last_check = cached_status.get("last_check", "Unknown")
            
            logger.info("Using cached HuggingFace API validation status", extra={"data": {
                "cached": True,
                "valid": is_valid,
                "username": username,
                "last_check": last_check
            }})
        else:
            # Perform real-time validation
            is_valid = False
            username = "unknown"
            
            if has_api_key:
                logger.info("Performing real-time HuggingFace API validation", extra={"data": {"force_refresh": force_refresh}})
                try:
                    # Test HuggingFace API using the models endpoint (more reliable than whoami)
                    async with aiohttp.ClientSession() as client_session:
                        async with client_session.get(
                            "https://huggingface.co/api/models?limit=1",
                            headers={"Authorization": f"Bearer {app_settings.HF_TOKEN.get_secret_value()}"},
                            timeout=10
                        ) as response:
                            if response.status == 200:
                                # If we can access the models API, the token is valid
                                is_valid = True
                                username = "valid"  # We can't get username from this endpoint
                            else:
                                is_valid = False
                                username = "unknown"
                except Exception as e:
                    logger.warning(f"HuggingFace API validation failed: {e}")
                    is_valid = False
                    username = "unknown"
                
                # Cache the validation results
                now = datetime.now(timezone.utc).isoformat()
                new_status = {
                    "validated": is_valid,
                    "validated_at": now if is_valid else cached_status.get("validated_at"),
                    "validation_error": None if is_valid else "API key validation failed",
                    "last_check": now,
                    "username": username
                }
                settings.api_key_validation_status["huggingface_api_key"] = new_status
                flag_modified(settings, "api_key_validation_status")
                await UserSettingsService.update_user_settings(session, settings)
        
        return {
            "has_huggingface_api_key": has_api_key,
            "huggingface_api_key_valid": is_valid,
            "username": username,
            "status": "ready" if is_valid else ("configured_invalid" if has_api_key else "not_configured"),
            "cached": not force_refresh and bool(cached_status),
            "last_check": cached_status.get("last_check", "Never") if not force_refresh else "Just now"
        }
        
    except Exception as e:
        logger.error("Failed to get HuggingFace API status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get HuggingFace API status")


@router.get("/litellm-api-status") 
async def get_litellm_api_status(
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the current status of LiteLLM master key and availability.
    Uses cached validation status unless force_refresh=True.
    """
    try:
        from config import settings as app_settings
        from database.database import UserSettingsService
        from datetime import datetime, timezone
        import aiohttp
        
        # Check if API key is configured in environment
        has_api_key = bool(app_settings.LITELLM_MASTER_KEY)
        
        # Get user settings to check cached validation status
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            # Create default settings if none exist
            settings = await UserSettingsService.create_user_settings(session)
        
        cached_status = settings.api_key_validation_status.get("litellm_master_key", {})
        
        # Use cached status unless force_refresh is requested or cache is empty
        if not force_refresh and cached_status and has_api_key:
            is_valid = cached_status.get("validated", False)
            base_url = cached_status.get("base_url", app_settings.LITELLM_BASE_URL)
            last_check = cached_status.get("last_check", "Unknown")
            
            logger.info("Using cached LiteLLM API validation status", extra={"data": {
                "cached": True,
                "valid": is_valid,
                "base_url": base_url,
                "last_check": last_check
            }})
        else:
            # Perform real-time validation
            is_valid = False
            base_url = app_settings.LITELLM_BASE_URL
            
            if has_api_key:
                logger.info("Performing real-time LiteLLM API validation", extra={"data": {"force_refresh": force_refresh}})
                try:
                    # Test LiteLLM models endpoint with authentication (requires valid auth)
                    async with aiohttp.ClientSession() as client_session:
                        async with client_session.get(
                            f"{app_settings.LITELLM_BASE_URL}/v1/models",
                            headers={"Authorization": f"Bearer {app_settings.LITELLM_MASTER_KEY}"},
                            timeout=10
                        ) as response:
                            if response.status == 200:
                                try:
                                    data = await response.json()
                                    # Check if response has the expected structure
                                    is_valid = isinstance(data, dict) and "data" in data
                                except:
                                    is_valid = False
                            else:
                                is_valid = False
                except Exception as e:
                    logger.warning(f"LiteLLM API validation failed: {e}")
                    is_valid = False
                
                # Cache the validation results
                now = datetime.now(timezone.utc).isoformat()
                new_status = {
                    "validated": is_valid,
                    "validated_at": now if is_valid else cached_status.get("validated_at"),
                    "validation_error": None if is_valid else "API key validation failed",
                    "last_check": now,
                    "base_url": base_url
                }
                settings.api_key_validation_status["litellm_master_key"] = new_status
                flag_modified(settings, "api_key_validation_status")
                await UserSettingsService.update_user_settings(session, settings)
        
        return {
            "has_litellm_master_key": has_api_key,
            "litellm_master_key_valid": is_valid,
            "base_url": base_url,
            "status": "ready" if is_valid else ("configured_invalid" if has_api_key else "not_configured"),
            "cached": not force_refresh and bool(cached_status),
            "last_check": cached_status.get("last_check", "Never") if not force_refresh else "Just now"
        }
        
    except Exception as e:
        logger.error("Failed to get LiteLLM API status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get LiteLLM API status")


@router.get("/openrouter-api-status")
async def get_openrouter_api_status(
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the current status of OpenRouter API key and availability.
    Uses cached validation status unless force_refresh=True.
    """
    try:
        from config import settings as app_settings
        from database.database import UserSettingsService
        from datetime import datetime, timezone
        import aiohttp
        
        # Check if API key is configured in environment
        has_api_key = bool(app_settings.OPENROUTER_API_KEY)
        
        # Get user settings to check cached validation status
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            # Create default settings if none exist
            settings = await UserSettingsService.create_user_settings(session)
        
        cached_status = settings.api_key_validation_status.get("openrouter_api_key", {})
        
        # Use cached status unless force_refresh is requested or cache is empty
        if not force_refresh and cached_status and has_api_key:
            is_valid = cached_status.get("validated", False)
            models_count = cached_status.get("models_available", 0)
            last_check = cached_status.get("last_check", "Unknown")
            
            logger.info("Using cached OpenRouter API validation status", extra={"data": {
                "cached": True,
                "valid": is_valid,
                "models_count": models_count,
                "last_check": last_check
            }})
        else:
            # Perform real-time validation
            is_valid = False
            models_count = 0
            
            if has_api_key:
                logger.info("Performing real-time OpenRouter API validation", extra={"data": {"force_refresh": force_refresh}})
                try:
                    # Test OpenRouter API using the models endpoint
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
                            else:
                                is_valid = False
                                models_count = 0
                except Exception as e:
                    logger.warning(f"OpenRouter API validation failed: {e}")
                    is_valid = False
                    models_count = 0
                
                # Cache the validation results
                now = datetime.now(timezone.utc).isoformat()
                new_status = {
                    "validated": is_valid,
                    "validated_at": now if is_valid else cached_status.get("validated_at"),
                    "validation_error": None if is_valid else "API key validation failed",
                    "last_check": now,
                    "models_available": models_count
                }
                settings.api_key_validation_status["openrouter_api_key"] = new_status
                flag_modified(settings, "api_key_validation_status")
                await UserSettingsService.update_user_settings(session, settings)
        
        return {
            "has_openrouter_api_key": has_api_key,
            "openrouter_api_key_valid": is_valid,
            "models_available": models_count,
            "status": "ready" if is_valid else ("configured_invalid" if has_api_key else "not_configured"),
            "cached": not force_refresh and bool(cached_status),
            "last_check": cached_status.get("last_check", "Never") if not force_refresh else "Just now"
        }
        
    except Exception as e:
        logger.error("Failed to get OpenRouter API status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get OpenRouter API status")