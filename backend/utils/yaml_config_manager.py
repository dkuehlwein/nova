"""
YAML configuration manager implementation.
Handles YAML-based configuration files with validation and type safety.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Type, TypeVar
from pydantic import BaseModel, ValidationError

from utils.base_config_manager import BaseConfigManager, ValidationResult
from utils.logging import get_logger

logger = get_logger("yaml_config_manager")

YamlConfigType = TypeVar('YamlConfigType', bound=BaseModel)


class YamlConfigManager(BaseConfigManager[YamlConfigType]):
    """
    YAML-based configuration manager.
    Handles Pydantic models with YAML serialization.
    """
    
    def __init__(self, config_path: Path, config_name: str, config_model: Type[YamlConfigType], 
                 default_config: YamlConfigType = None, debounce_seconds: float = 0.5):
        self.config_model = config_model
        self.default_config = default_config
        super().__init__(config_path, config_name, debounce_seconds)
    
    def _load_config_data(self) -> Dict[str, Any]:
        """Load raw YAML data from file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                return data or {}
        except Exception as e:
            logger.error(
                f"Failed to load YAML data: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            raise
    
    def _save_config_data(self, data: Dict[str, Any]) -> None:
        """Save YAML data to file."""
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, default_flow_style=False, sort_keys=True, indent=2)
                
        except Exception as e:
            logger.error(
                f"Failed to save YAML data: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            raise
    
    def _create_config_instance(self, data: Dict[str, Any]) -> YamlConfigType:
        """Create Pydantic model instance from YAML data."""
        try:
            if self.config_model == dict:
                # For raw dict configs (like MCP servers)
                return data
            else:
                # For Pydantic models
                return self.config_model(**data)
                
        except ValidationError as e:
            logger.error(
                f"Config validation failed: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "validation_errors": e.errors()
                    }
                }
            )
            raise
        except Exception as e:
            logger.error(
                f"Failed to create config instance: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            raise
    
    def _serialize_config(self, config: YamlConfigType) -> Dict[str, Any]:
        """Serialize Pydantic model to YAML data."""
        try:
            if isinstance(config, dict):
                # For raw dict configs
                return config
            elif hasattr(config, 'model_dump'):
                # For Pydantic v2 models
                return config.model_dump()
            elif hasattr(config, 'dict'):
                # For Pydantic v1 models
                return config.dict()
            else:
                # Fallback for other types
                return dict(config)
                
        except Exception as e:
            logger.error(
                f"Failed to serialize config: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "config_type": type(config).__name__,
                        "error": str(e)
                    }
                }
            )
            raise
    
    def _validate_config_data(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate YAML configuration data."""
        errors = []
        warnings = []
        details = {}
        
        try:
            # Try to create instance to validate
            if self.config_model == dict:
                # For raw dict configs, perform basic validation
                if not isinstance(data, dict):
                    errors.append("Configuration must be a dictionary")
                else:
                    details['key_count'] = len(data)
                    
                    # Check for common issues
                    if len(data) == 0:
                        warnings.append("Configuration is empty")
                    
                    # Check for very large configs
                    if len(data) > 100:
                        warnings.append(f"Large configuration with {len(data)} items")
            else:
                # For Pydantic models
                try:
                    instance = self.config_model(**data)
                    details['validation_passed'] = True
                    
                    # Model-specific validation can be added here
                    if hasattr(instance, 'model_fields'):
                        details['field_count'] = len(instance.model_fields)
                        
                except ValidationError as e:
                    for error in e.errors():
                        error_msg = f"{'.'.join(str(x) for x in error['loc'])}: {error['msg']}"
                        errors.append(error_msg)
                    details['validation_passed'] = False
            
            # Additional custom validation can be added here
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            details['validation_error'] = str(e)
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def _create_default_config(self) -> None:
        """Create default configuration file."""
        if self.default_config is not None:
            logger.info(
                f"Creating default YAML config: {self.config_name}",
                extra={"data": {"path": str(self.config_path)}}
            )
            
            # Save default config
            data = self._serialize_config(self.default_config)
            self._save_config_data(data)
        else:
            # Create empty YAML file
            logger.info(
                f"Creating empty YAML config: {self.config_name}",
                extra={"data": {"path": str(self.config_path)}}
            )
            
            self._save_config_data({})


class DictConfigManager(YamlConfigManager):
    """
    Special YAML config manager for raw dictionary configurations.
    Used for configs like MCP servers that don't use Pydantic models.
    """
    
    def __init__(self, config_path: Path, config_name: str, 
                 default_config: Dict[str, Any] = None, debounce_seconds: float = 0.5):
        # Use dict as the "model" type
        super().__init__(config_path, config_name, dict, default_config, debounce_seconds)
    
    def _create_config_instance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return raw dictionary data."""
        return data or {}
    
    def _serialize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return raw dictionary data."""
        return config or {} 