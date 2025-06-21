"""
Configuration validation models for Nova settings.

Provides Pydantic models for validating YAML configurations,
particularly MCP server configurations with comprehensive validation.
"""

from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator, HttpUrl, Field, RootModel


class MCPServerConfig(BaseModel):
    """MCP Server configuration with validation."""
    
    url: HttpUrl = Field(..., description="MCP server URL endpoint")
    health_url: Optional[HttpUrl] = Field(None, description="Optional health check endpoint URL (uses MCP tools/list if not provided)") 
    description: str = Field(..., min_length=1, max_length=500, description="Server description")
    enabled: bool = Field(default=True, description="Whether server is enabled")
    
    @field_validator('health_url')
    @classmethod
    def health_url_must_be_valid(cls, v):
        """Ensure health URL is a valid endpoint if provided."""
        if v is not None and not str(v).endswith(('/health', '/status', '/ping')):
            raise ValueError('Health URL should end with /health, /status, or /ping')
        return v
    
    @field_validator('description')
    @classmethod
    def description_not_empty(cls, v):
        """Ensure description is not just whitespace."""
        if not v.strip():
            raise ValueError('Description cannot be empty or just whitespace')
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health",
                "description": "Gmail MCP Server for email operations",
                "enabled": True
            }
        }


class MCPServersConfig(RootModel[Dict[str, MCPServerConfig]]):
    """Root configuration for MCP servers."""
    
    root: Dict[str, MCPServerConfig] = Field(
        ..., 
        description="Dictionary of MCP server configurations keyed by server name"
    )
    
    @field_validator('root')
    @classmethod
    def validate_server_names(cls, v):
        """Validate server names and prevent duplicates."""
        if not v:
            raise ValueError('At least one MCP server must be configured')
        
        # Check for reserved names
        reserved_names = {'admin', 'api', 'health', 'status', 'docs'}
        for name in v.keys():
            if name.lower() in reserved_names:
                raise ValueError(f'Server name "{name}" is reserved')
            
            # Check name format
            if not name.replace('_', '').replace('-', '').isalnum():
                raise ValueError(f'Server name "{name}" must be alphanumeric with optional - or _')
            
            if len(name) < 2 or len(name) > 50:
                raise ValueError(f'Server name "{name}" must be between 2-50 characters')
        
        # Check for URL conflicts
        urls = [str(config.url) for config in v.values()]
        health_urls = [str(config.health_url) for config in v.values() if config.health_url is not None]
        
        if len(set(urls)) != len(urls):
            raise ValueError('Duplicate MCP server URLs found')
        if health_urls and len(set(health_urls)) != len(health_urls):
            raise ValueError('Duplicate health check URLs found')
        
        return v
    
    def __iter__(self):
        return iter(self.root)
    
    def __getitem__(self, item):
        return self.root[item]
    
    def keys(self):
        return self.root.keys()
    
    def values(self):
        return self.root.values()
    
    def items(self):
        return self.root.items()


class ConfigValidationResult(BaseModel):
    """Result of configuration validation."""
    
    valid: bool = Field(..., description="Whether configuration is valid")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of validation warnings")
    server_count: int = Field(default=0, description="Number of configured servers")
    enabled_count: int = Field(default=0, description="Number of enabled servers")
    
    class Config:
        schema_extra = {
            "example": {
                "valid": True,
                "errors": [],
                "warnings": ["Server 'test' has no description"],
                "server_count": 2,
                "enabled_count": 1
            }
        }


class ConfigBackupInfo(BaseModel):
    """Information about configuration backup."""
    
    backup_id: str = Field(..., description="Unique backup identifier")
    timestamp: str = Field(..., description="ISO timestamp of backup")
    server_count: int = Field(..., description="Number of servers in backup")
    description: Optional[str] = Field(None, description="Optional backup description")
    
    class Config:
        schema_extra = {
            "example": {
                "backup_id": "20250606_143022_mcp_config",
                "timestamp": "2025-06-06T14:30:22Z", 
                "server_count": 3,
                "description": "Pre-update backup"
            }
        }


# API request/response models moved here from config_endpoints.py
class ConfigValidateRequest(BaseModel):
    """Request body for configuration validation."""
    config: Dict[str, Any] = Field(..., description="Configuration to validate")


class ConfigValidateResponse(BaseModel):
    """Response for configuration validation.""" 
    validation_result: ConfigValidationResult = Field(..., description="Detailed validation results")
    message: str = Field(..., description="Human-readable validation message")


class ConfigRestoreRequest(BaseModel):
    """Request body for configuration restore."""
    backup_id: str = Field(..., description="Backup identifier to restore from") 