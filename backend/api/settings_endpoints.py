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

from database.database import db_manager
from models.user_settings import (
    UserSettings, 
    UserSettingsModel, 
    UserSettingsUpdateModel,
    OnboardingStatusModel
)
from utils.logging import get_logger

logger = get_logger("settings_api")

router = APIRouter(prefix="/api/user-settings", tags=["user-settings"])


async def get_db_session():
    """Dependency to get database session."""
    async with db_manager.get_session() as session:
        yield session


@router.get("/status", response_model=OnboardingStatusModel)
async def get_onboarding_status(session: AsyncSession = Depends(get_db_session)):
    """
    Check if user has completed onboarding and what setup is required.
    """
    try:
        # Get or create user settings (assume single user for MVP)
        result = await session.execute(select(UserSettings).limit(1))
        settings = result.scalar_one_or_none()
        
        if not settings:
            # No settings exist - first time setup required
            return OnboardingStatusModel(
                onboarding_complete=False,
                missing_required_settings=["user_profile", "api_keys"],
                setup_required=True
            )
        
        missing = []
        if not settings.full_name or not settings.email:
            missing.append("user_profile")
        
        # Check if API keys are configured (read from Tier 2 - but don't expose values)
        from config import settings as app_settings
        if not app_settings.GOOGLE_API_KEY:
            missing.append("google_api_key")
        
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
        # Get or create user settings (assume single user for MVP)
        result = await session.execute(select(UserSettings).limit(1))
        settings = result.scalar_one_or_none()
        
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
        # Get existing settings
        result = await session.execute(select(UserSettings).limit(1))
        settings = result.scalar_one_or_none()
        
        if not settings:
            # Create new settings if none exist
            settings = UserSettings()
            session.add(settings)
        
        # Apply updates (only non-None values)
        update_data = updates.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in update_data.items():
            if hasattr(settings, field):
                setattr(settings, field, value)
        
        await session.commit()
        await session.refresh(settings)
        
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
        # Get or create settings
        result = await session.execute(select(UserSettings).limit(1))
        settings = result.scalar_one_or_none()
        
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


@router.get("/system-status")
async def get_system_status():
    """
    Get read-only system status information.
    Shows non-sensitive Tier 1 and Tier 2 info for debugging.
    NEVER exposes secrets like API keys or passwords.
    """
    try:
        from config import settings as app_settings
        
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
                "core_agent_port": app_settings.CORE_AGENT_PORT
            },
            "api_keys_configured": {
                "google": bool(app_settings.GOOGLE_API_KEY),
                "langsmith": bool(app_settings.LANGCHAIN_API_KEY)
            }
        }
        
        return status
        
    except Exception as e:
        logger.error("Failed to get system status", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get system status")


@router.post("/migrate-user-profile")
async def migrate_user_profile_from_yaml(session: AsyncSession = Depends(get_db_session)):
    """
    One-time migration: Move user profile data from YAML to database.
    """
    try:
        from utils.config_registry import get_config
        
        # Check if settings already exist
        result = await session.execute(select(UserSettings).limit(1))
        existing_settings = result.scalar_one_or_none()
        
        if existing_settings and existing_settings.full_name:
            return {"status": "skipped", "message": "User profile already exists in database"}
        
        # Try to load from YAML
        try:
            user_profile = get_config("user_profile")
            
            # Create or update settings with YAML data
            if not existing_settings:
                settings = UserSettings()
                session.add(settings)
            else:
                settings = existing_settings
            
            settings.full_name = user_profile.full_name
            settings.email = user_profile.email
            settings.timezone = user_profile.timezone
            settings.notes = user_profile.notes
            
            await session.commit()
            
            logger.info("User profile migrated from YAML to database")
            return {"status": "success", "message": "User profile migrated from YAML"}
            
        except Exception as yaml_error:
            logger.warning(f"Could not load user profile from YAML: {yaml_error}")
            return {"status": "skipped", "message": "No user profile YAML found to migrate"}
            
    except Exception as e:
        logger.error("Failed to migrate user profile", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to migrate user profile")


@router.post("/validate-api-key")
async def validate_api_key(request: dict):
    """
    Validate an API key by making a test call to the service.
    Only validates - does not store the key.
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
        
        if key_type == "google_api_key":
            # Validate Google API key by making a simple AI request
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Simple test request
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content("Hello")
                
                result = {
                    "valid": True,
                    "message": "Google API key is valid",
                    "service": "google"
                }
                logger.info("Google API key validation successful", extra={"data": result})
                return result
            except Exception as e:
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
                
                # Test LangSmith API
                response = requests.get(
                    "https://api.smith.langchain.com/sessions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"limit": 1},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = {
                        "valid": True,
                        "message": "LangSmith API key is valid",
                        "service": "langsmith"
                    }
                    logger.info("LangSmith API key validation successful", extra={"data": result})
                    return result
                else:
                    result = {
                        "valid": False,
                        "message": f"LangSmith API key validation failed: {response.status_code}",
                        "service": "langsmith"
                    }
                    logger.warning("LangSmith API key validation failed", extra={"data": {"status_code": response.status_code, "result": result}})
                    return result
            except Exception as e:
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
async def save_api_keys(request: dict):
    """
    Save validated API keys to .env file (Tier 2 configuration).
    Only saves keys that have been previously validated.
    """
    try:
        import os
        from pathlib import Path
        
        api_keys = request.get("api_keys", {})
        if not api_keys:
            raise HTTPException(status_code=400, detail="No API keys provided")
        
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
            
            logger.info(
                "API keys saved to .env file",
                extra={
                    "data": {
                        "env_file": str(env_file),
                        "updated_keys": updated_keys
                    }
                }
            )
        
        return {
            "status": "success",
            "message": f"Saved {len(updated_keys)} API keys to .env file",
            "updated_keys": updated_keys,
            "env_file": str(env_file)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save API keys", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save API keys: {str(e)}")