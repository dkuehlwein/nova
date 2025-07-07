"""
Configuration Management API Endpoints

Provides REST API for validating configurations and managing backups.
Implements unified configuration management system.
"""

from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.config_registry import config_registry
from utils.logging import get_logger, log_config_change
from utils.redis_manager import publish
from models.config import ConfigValidationResult, ConfigBackupInfo
from models.events import create_config_validated_event
from models.user_profile import UserProfile, UserProfileUpdate

logger = get_logger("config-api")
router = APIRouter(prefix="/api/config", tags=["Configuration"])

# Import domain-specific models
from models.config import ConfigValidateRequest, ConfigValidateResponse, ConfigRestoreRequest


@router.post("/validate", response_model=ConfigValidateResponse)
async def validate_configuration(request: ConfigValidateRequest):
    """
    Validate MCP server configuration without saving.
    
    Tests the provided configuration against validation rules
    and returns detailed feedback about any issues found.
    """
    try:
        config_manager = config_registry.get_manager("mcp_servers")
        validation_result = config_manager.validate_config(request.config)
        
        # Publish validation event
        event = create_config_validated_event(
            config_type="mcp_servers",
            valid=validation_result.valid,
            errors=validation_result.errors,
            source="config-api"
        )
        await publish(event)
        
        # Log validation attempt
        log_config_change(
            operation="config_validated",
            config_type="mcp_servers",
            details={
                "valid": validation_result.valid,
                "error_count": len(validation_result.errors),
                "warning_count": len(validation_result.warnings),
                "server_count": validation_result.details.get("server_count", validation_result.details.get("key_count", 0))
            },
            logger=logger
        )
        
        message = "Configuration is valid" if validation_result.valid else "Configuration has validation errors"
        if validation_result.warnings:
            message += f" with {len(validation_result.warnings)} warnings"
        
        # Convert ValidationResult to ConfigValidationResult for API response
        # For MCP servers, map key_count to server_count since DictConfigManager counts keys
        server_count = validation_result.details.get("server_count", validation_result.details.get("key_count", 0))
        config_validation_result = ConfigValidationResult(
            valid=validation_result.valid,
            errors=validation_result.errors,
            warnings=validation_result.warnings,
            server_count=server_count,
            enabled_count=validation_result.details.get("enabled_count", server_count)  # Default to all servers enabled
        )
        
        return {
            "validation_result": config_validation_result.model_dump(),
            "message": message
        }
        
    except Exception as e:
        logger.error(
            "Configuration validation failed",
            exc_info=True,
            extra={"data": {"error": str(e)}}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Configuration validation failed: {str(e)}"
        )


@router.get("/validate", response_model=ConfigValidateResponse)
async def validate_current_configuration():
    """
    Validate the current MCP server configuration.
    
    Validates the currently loaded configuration and returns
    detailed feedback about any issues found.
    """
    try:
        config_manager = config_registry.get_manager("mcp_servers")
        validation_result = config_manager.validate_config()
        
        message = "Current configuration is valid" if validation_result.valid else "Current configuration has validation errors"
        if validation_result.warnings:
            message += f" with {len(validation_result.warnings)} warnings"
        
        # Convert ValidationResult to ConfigValidationResult for API response
        # For MCP servers, map key_count to server_count since DictConfigManager counts keys
        server_count = validation_result.details.get("server_count", validation_result.details.get("key_count", 0))
        config_validation_result = ConfigValidationResult(
            valid=validation_result.valid,
            errors=validation_result.errors,
            warnings=validation_result.warnings,
            server_count=server_count,
            enabled_count=validation_result.details.get("enabled_count", server_count)  # Default to all servers enabled
        )
        
        return {
            "validation_result": config_validation_result.model_dump(),
            "message": message
        }
        
    except Exception as e:
        logger.error(
            "Current configuration validation failed",
            exc_info=True,
            extra={"data": {"error": str(e)}}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Configuration validation failed: {str(e)}"
        )


@router.get("/backups", response_model=List[ConfigBackupInfo])
async def list_configuration_backups():
    """
    List available configuration backups.
    
    Returns a list of all available configuration backups
    sorted by timestamp (newest first).
    """
    try:
        config_manager = config_registry.get_manager("mcp_servers")
        backups = config_manager.list_backups()
        
        logger.info(
            f"Listed configuration backups",
            extra={"data": {"backup_count": len(backups)}}
        )
        
        return backups
        
    except Exception as e:
        logger.error(
            "Failed to list configuration backups",
            exc_info=True,
            extra={"data": {"error": str(e)}}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list backups: {str(e)}"
        )


@router.post("/backups", response_model=ConfigBackupInfo)
async def create_configuration_backup(description: str = "Manual backup"):
    """
    Create a backup of the current configuration.
    
    Creates a timestamped backup of the current MCP server
    configuration for later restoration.
    """
    try:
        config_manager = config_registry.get_manager("mcp_servers")
        backup_info = config_manager.create_backup(description)
        
        # Log backup creation
        log_config_change(
            operation="config_backup_created",
            config_type="mcp_servers",
            details={
                "backup_id": backup_info.backup_id,
                "description": description,
                "server_count": backup_info.server_count
            },
            logger=logger
        )
        
        return backup_info
        
    except Exception as e:
        logger.error(
            "Failed to create configuration backup",
            exc_info=True,
            extra={"data": {"error": str(e), "description": description}}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create backup: {str(e)}"
        )


@router.post("/restore/{backup_id}")
async def restore_configuration_backup(backup_id: str):
    """
    Restore configuration from a backup.
    
    Restores the MCP server configuration from a specified backup.
    Creates an automatic backup of the current configuration before restoring.
    """
    try:
        config_manager = config_registry.get_manager("mcp_servers")
        
        # Attempt to restore
        success = config_manager.restore_backup(backup_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Backup {backup_id} not found"
            )
        
        # Log successful restore
        log_config_change(
            operation="config_backup_restored",
            config_type="mcp_servers",
            details={
                "backup_id": backup_id,
                "restored_at": backup_id  # backup_id contains timestamp
            },
            logger=logger
        )
        
        return {
            "message": f"Configuration restored from backup {backup_id}",
            "backup_id": backup_id,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to restore configuration backup",
            exc_info=True,
            extra={"data": {"error": str(e), "backup_id": backup_id}}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore backup: {str(e)}"
        )


# User Profile Endpoints
@router.get("/user-profile", response_model=UserProfile)
async def get_user_profile():
    """
    Get the current user profile configuration.
    
    Returns the user's profile information including name, email, timezone, and notes.
    """
    try:
        config_manager = config_registry.get_manager("user_profile")
        profile = config_manager.get_config()
        
        logger.info("User profile retrieved successfully")
        return profile
        
    except Exception as e:
        logger.error(
            "Failed to retrieve user profile",
            exc_info=True,
            extra={"data": {"error": str(e)}}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user profile: {str(e)}"
        )


@router.put("/user-profile", response_model=UserProfile)
async def update_user_profile(update: UserProfileUpdate):
    """
    Update the user profile configuration.
    
    Updates the user's profile information and publishes a profile update event.
    """
    try:
        config_manager = config_registry.get_manager("user_profile")
        current_profile = config_manager.get_config()
        
        # Apply updates
        updated_profile = current_profile.model_copy(update=update.model_dump(exclude_unset=True))
        
        # Save the updated profile
        config_manager.save_config(updated_profile)
        
        # Publish standardized config updated event
        event = create_config_validated_event(
            config_type="user_profile",
            valid=True,
            errors=[],
            source="config-api"
        )
        await publish(event)
        
        # Log profile update
        log_config_change(
            operation="user_profile_updated",
            config_type="user_profile",
            details={
                "full_name": updated_profile.full_name,
                "email": updated_profile.email,
                "timezone": updated_profile.timezone,
                "notes_length": len(updated_profile.notes or "")
            },
            logger=logger
        )
        
        return updated_profile
        
    except Exception as e:
        logger.error(
            "Failed to update user profile",
            exc_info=True,
            extra={"data": {"error": str(e)}}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update user profile: {str(e)}"
        ) 