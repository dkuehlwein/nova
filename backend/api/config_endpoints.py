"""
Configuration Management API Endpoints

Provides REST API for validating configurations and managing backups.
Implements work package B9 from the settings realization roadmap.
"""

from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.config_loader import get_mcp_config_loader
from utils.logging import get_logger, log_config_change
from utils.redis_manager import publish
from models.config import ConfigValidationResult, ConfigBackupInfo
from models.events import create_config_validated_event

logger = get_logger("config-api")
router = APIRouter(prefix="/api/config", tags=["Configuration"])


class ConfigValidateRequest(BaseModel):
    """Request body for configuration validation."""
    config: Dict[str, Any]


class ConfigValidateResponse(BaseModel):
    """Response for configuration validation."""
    validation_result: ConfigValidationResult
    message: str


class ConfigRestoreRequest(BaseModel):
    """Request body for configuration restore."""
    backup_id: str


@router.post("/validate", response_model=ConfigValidateResponse)
async def validate_configuration(request: ConfigValidateRequest):
    """
    Validate MCP server configuration without saving.
    
    Tests the provided configuration against validation rules
    and returns detailed feedback about any issues found.
    """
    try:
        config_loader = get_mcp_config_loader()
        validation_result = config_loader.validate_config(request.config)
        
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
                "server_count": validation_result.server_count
            },
            logger=logger
        )
        
        message = "Configuration is valid" if validation_result.valid else "Configuration has validation errors"
        if validation_result.warnings:
            message += f" with {len(validation_result.warnings)} warnings"
        
        return {
            "validation_result": validation_result.model_dump(),
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
        config_loader = get_mcp_config_loader()
        validation_result = config_loader.validate_config()
        
        message = "Current configuration is valid" if validation_result.valid else "Current configuration has validation errors"
        if validation_result.warnings:
            message += f" with {len(validation_result.warnings)} warnings"
        
        return {
            "validation_result": validation_result.model_dump(),
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
        config_loader = get_mcp_config_loader()
        backups = config_loader.list_backups()
        
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
        config_loader = get_mcp_config_loader()
        backup_info = config_loader.create_backup(description)
        
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
        config_loader = get_mcp_config_loader()
        
        # Attempt to restore
        success = config_loader.restore_backup(backup_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Backup '{backup_id}' not found or invalid"
            )
        
        # Log restoration
        log_config_change(
            operation="config_backup_restored",
            config_type="mcp_servers",
            details={
                "backup_id": backup_id,
                "user_action": True
            },
            logger=logger
        )
        
        # Publish configuration change event
        validation_result = config_loader.validate_config()
        event = create_config_validated_event(
            config_type="mcp_servers",
            valid=validation_result.valid,
            errors=validation_result.errors,
            source="config-restore"
        )
        await publish(event)
        
        return {
            "backup_id": backup_id,
            "status": "success",
            "message": f"Configuration restored from backup '{backup_id}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to restore configuration backup: {backup_id}",
            exc_info=True,
            extra={"data": {"error": str(e), "backup_id": backup_id}}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore backup: {str(e)}"
        ) 