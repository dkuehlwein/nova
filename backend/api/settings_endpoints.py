"""
Settings API Endpoints for Nova's 3-Tier Configuration System

Provides API endpoints for managing Tier 3 (database) user settings.
NEVER exposes Tier 1 (config.py) or Tier 2 (.env) values for security.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        
        # Google API key is optional but provide status info
        # Users can choose to use only local models or add Google API key for cloud models
        
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
        
        # If email-related settings were updated, publish Redis event and trigger beat schedule update
        email_fields = {
            "email_polling_enabled", "email_polling_interval", "email_label_filter", 
            "email_max_per_fetch", "email_create_tasks"
        }
        if any(field in update_data for field in email_fields):
            try:
                # Publish Redis event for real-time updates
                from models.events import create_email_settings_updated_event
                from utils.redis_manager import publish
                
                email_event = create_email_settings_updated_event(
                    enabled=settings.email_polling_enabled,
                    polling_interval_minutes=settings.email_polling_interval,
                    email_label_filter=settings.email_label_filter,
                    max_emails_per_fetch=settings.email_max_per_fetch,
                    create_tasks_from_emails=settings.email_create_tasks,
                    source="settings-api"
                )
                
                await publish(email_event)
                
                logger.info(
                    "Published email settings update event",
                    extra={"data": {"event_id": email_event.id, "updated_fields": list(update_data.keys())}}
                )
                
                # Also trigger traditional Celery Beat schedule update as fallback
                from celery_app import update_beat_schedule_task
                update_beat_schedule_task.delay()
                
            except Exception as e:
                logger.warning(f"Failed to publish email settings event or trigger beat schedule update: {e}")
        
        # If LLM-related settings were updated, publish Redis event for chat agent cache clearing
        llm_fields = {
            "llm_model", "llm_temperature", "llm_max_tokens"
        }
        if any(field in update_data for field in llm_fields):
            try:
                # Publish Redis event for real-time updates
                from models.events import create_llm_settings_updated_event
                from utils.redis_manager import publish
                
                llm_event = create_llm_settings_updated_event(
                    model=settings.llm_model,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                    source="settings-api"
                )
                
                await publish(llm_event)
                
                logger.info(
                    "Published LLM settings update event",
                    extra={"data": {"event_id": llm_event.id, "updated_fields": list(update_data.keys())}}
                )
                
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


@router.post("/complete-onboarding")
async def complete_onboarding(session: AsyncSession = Depends(get_db_session)):
    """
    Mark onboarding as complete.
    """
    try:
        from database.database import UserSettingsService
        
        # Get or create settings using the current session
        settings = await UserSettingsService.get_user_settings(session)
        
        if not settings:
            settings = UserSettings()
            session.add(settings)
        
        settings.onboarding_complete = True
        await session.commit()
        
        logger.info("Onboarding marked as complete")
        
        return {"status": "success", "message": "Onboarding completed"}
        
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
    llamacpp_check = check_http_service(f"{app_settings.LLAMACPP_BASE_URL}/health")
    litellm_check = check_http_service(f"{app_settings.LITELLM_BASE_URL}/health", app_settings.LITELLM_MASTER_KEY)
    
    # Neo4j check (synchronous)
    neo4j_status = check_neo4j_service(
        app_settings.NEO4J_URI,
        app_settings.NEO4J_USER,
        app_settings.NEO4J_PASSWORD
    )
    
    # Wait for HTTP checks
    llamacpp_status, litellm_status = await asyncio.gather(
        llamacpp_check, litellm_check, return_exceptions=True
    )
    
    # Handle exceptions
    if isinstance(llamacpp_status, Exception):
        llamacpp_status = {"status": "unhealthy", "error": str(llamacpp_status)}
    if isinstance(litellm_status, Exception):
        litellm_status = {"status": "unhealthy", "error": str(litellm_status)}
    
    return {
        "llamacpp": llamacpp_status,
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
            "mcp_servers": [
                {
                    "name": server["name"],
                    "url": server["url"],
                    "description": server["description"]
                }
                for server in app_settings.MCP_SERVERS
            ],
            "services": {
                "chat_agent_port": app_settings.CHAT_AGENT_PORT,
                "core_agent_port": app_settings.CORE_AGENT_PORT,
                "llamacpp": service_status["llamacpp"],
                "litellm": service_status["litellm"],
                "neo4j": service_status["neo4j"]
            },
            "api_keys_configured": {
                "google": bool(app_settings.GOOGLE_API_KEY),
                "langsmith": bool(app_settings.LANGCHAIN_API_KEY)
            },
            "google_models_available": bool(app_settings.GOOGLE_API_KEY)  # Indicates if Gemini models should be available
        }
        
        return status
        
    except Exception as e:
        logger.error("Failed to get system status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get system status")




@router.post("/validate-api-key")
async def validate_api_key(
    request: dict, 
    session: AsyncSession = Depends(get_db_session)
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
        from datetime import datetime, timezone
        
        settings = await UserSettingsService.get_user_settings(session)
        if not settings:
            # Create default settings if none exist
            settings = await UserSettingsService.create_user_settings(session)
        
        if key_type == "google_api_key":
            # Validate Google API key by making a simple AI request
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Simple test request - use model from config
                from config import settings
                model_name = "gemini-2.5-flash-lite-preview-06-17" # TODO
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("Hello")
                
                # Cache successful validation
                now = datetime.now(timezone.utc).isoformat()
                settings.api_key_validation_status["google_api_key"] = {
                    "validated": True,
                    "validated_at": now,
                    "validation_error": None,
                    "last_check": now,
                    "gemini_models_available": 0  # Will be updated by google-api-status endpoint
                }
                await UserSettingsService.update_user_settings(session, settings)
                
                result = {
                    "valid": True,
                    "message": "Google API key is valid",
                    "service": "google"
                }
                logger.info("Google API key validation successful", extra={"data": result})
                return result
            except Exception as e:
                # Cache failed validation
                now = datetime.now(timezone.utc).isoformat()
                settings.api_key_validation_status["google_api_key"] = {
                    "validated": False,
                    "validated_at": None,
                    "validation_error": str(e),
                    "last_check": now,
                    "gemini_models_available": 0
                }
                await UserSettingsService.update_user_settings(session, settings)
                
                result = {
                    "valid": False,
                    "message": f"Google API key validation failed: {str(e)}",
                    "service": "google"
                }
                logger.warning("Google API key validation failed", extra={"data": {"error": str(e), "result": result}})
                return result
                
        elif key_type == "langsmith_api_key":
            # Validate LangSmith API key
            try:
                import requests
                
                # Test LangSmith API using minimal permissions endpoint
                response = requests.get(
                    "https://api.smith.langchain.com/info",
                    headers={"x-api-key": api_key},
                    timeout=10
                )
                
                now = datetime.now(timezone.utc).isoformat()
                
                if response.status_code == 200:
                    # Cache successful validation
                    settings.api_key_validation_status["langsmith_api_key"] = {
                        "validated": True,
                        "validated_at": now,
                        "validation_error": None,
                        "last_check": now,
                        "features_available": ["tracing", "monitoring", "debugging"]
                    }
                    await UserSettingsService.update_user_settings(session, settings)
                    
                    result = {
                        "valid": True,
                        "message": "LangSmith API key is valid",
                        "service": "langsmith"
                    }
                    logger.info("LangSmith API key validation successful", extra={"data": result})
                    return result
                else:
                    # Cache failed validation
                    settings.api_key_validation_status["langsmith_api_key"] = {
                        "validated": False,
                        "validated_at": None,
                        "validation_error": f"API returned status {response.status_code}",
                        "last_check": now,
                        "features_available": []
                    }
                    await UserSettingsService.update_user_settings(session, settings)
                    
                    result = {
                        "valid": False,
                        "message": f"LangSmith API key validation failed: {response.status_code}",
                        "service": "langsmith"
                    }
                    logger.warning("LangSmith API key validation failed", extra={"data": {"status_code": response.status_code, "result": result}})
                    return result
            except Exception as e:
                # Cache failed validation
                now = datetime.now(timezone.utc).isoformat()
                settings.api_key_validation_status["langsmith_api_key"] = {
                    "validated": False,
                    "validated_at": None,
                    "validation_error": str(e),
                    "last_check": now,
                    "features_available": []
                }
                await UserSettingsService.update_user_settings(session, settings)
                
                result = {
                    "valid": False,
                    "message": f"LangSmith API key validation failed: {str(e)}",
                    "service": "langsmith"
                }
                logger.warning("LangSmith API key validation exception", extra={"data": {"error": str(e), "result": result}})
                return result
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown key_type: {key_type}")
            
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
            "langsmith_api_key": "LANGCHAIN_API_KEY"
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
            
            # Refresh LiteLLM models if Google API key was updated
            if "GOOGLE_API_KEY" in updated_keys:
                try:
                    from services.llm_service import llm_service
                    from database.database import db_manager
                    
                    async with db_manager.get_session() as session:
                        await llm_service.refresh_models_after_api_key_update(session)
                    
                    logger.info("Triggered model refresh after Google API key update")
                except Exception as e:
                    logger.warning(f"Failed to refresh models after API key update: {e}")
        
        return {
            "status": "success",
            "message": f"Saved {len(updated_keys)} API keys to .env file",
            "updated_keys": updated_keys,
            "env_file": str(env_file),
            "models_refreshed": "GOOGLE_API_KEY" in updated_keys
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
                is_valid = await llm_service.is_google_api_key_valid()
                
                # Get available models
                available_models = await llm_service.get_available_models()
                gemini_models_count = len(available_models.get("cloud", []))
                
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
            features_available = cached_status.get("features_available", [])
            last_check = cached_status.get("last_check", "Unknown")
            
            logger.info("Using cached LangSmith API validation status", extra={"data": {
                "cached": True,
                "valid": is_valid,
                "features_count": len(features_available),
                "last_check": last_check
            }})
        else:
            # Perform real-time validation
            is_valid = False
            features_available = []
            
            if has_api_key:
                logger.info("Performing real-time LangSmith API validation", extra={"data": {"force_refresh": force_refresh}})
                try:
                    # Test LangSmith API using minimal permissions endpoint
                    response = requests.get(
                        "https://api.smith.langchain.com/info",
                        headers={"x-api-key": app_settings.LANGCHAIN_API_KEY},
                        timeout=10
                    )
                    
                    is_valid = response.status_code == 200
                    features_available = ["tracing", "monitoring", "debugging"] if is_valid else []
                except Exception as e:
                    logger.warning(f"LangSmith API validation failed: {e}")
                    is_valid = False
                    features_available = []
                
                # Cache the validation results
                now = datetime.now(timezone.utc).isoformat()
                new_status = {
                    "validated": is_valid,
                    "validated_at": now if is_valid else cached_status.get("validated_at"),
                    "validation_error": None if is_valid else "API key validation failed",
                    "last_check": now,
                    "features_available": features_available
                }
                
                # Update cached status
                settings.api_key_validation_status["langsmith_api_key"] = new_status
                await UserSettingsService.update_user_settings(session, settings)
                
                logger.info("Cached LangSmith API validation results", extra={"data": new_status})
        
        return {
            "has_langsmith_api_key": has_api_key,
            "langsmith_api_key_valid": is_valid,
            "features_available": len(features_available) if isinstance(features_available, list) else 0,
            "features": features_available,
            "status": "ready" if is_valid else ("configured_invalid" if has_api_key else "not_configured"),
            "cached": not force_refresh and bool(cached_status),
            "last_check": cached_status.get("last_check", "Never") if not force_refresh else "Just now"
        }
        
    except Exception as e:
        logger.error("Failed to get LangSmith API status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get LangSmith API status")