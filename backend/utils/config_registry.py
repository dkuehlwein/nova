"""
Configuration registry for centralized management.
Provides a single point of access for all configuration managers.
"""

from typing import Dict, Optional, Any, List
from pathlib import Path

from utils.base_config_manager import BaseConfigManager
from utils.logging import get_logger

logger = get_logger("config_registry")


class ConfigRegistry:
    """
    Global registry for all configuration managers.
    Provides centralized access and lifecycle management.
    """
    
    def __init__(self):
        self._managers: Dict[str, BaseConfigManager] = {}
        self._initialized = False
    
    def register(self, config_name: str, manager: BaseConfigManager) -> None:
        """Register a configuration manager."""
        if config_name in self._managers:
            logger.warning(
                f"Overwriting existing config manager: {config_name}",
                extra={"data": {"config_name": config_name}}
            )
        
        self._managers[config_name] = manager
        
        logger.info(
            f"Configuration manager registered: {config_name}",
            extra={
                "data": {
                    "config_name": config_name,
                    "manager_type": type(manager).__name__,
                    "config_path": str(manager.config_path)
                }
            }
        )
    
    def get_manager(self, config_name: str) -> Optional[BaseConfigManager]:
        """Get configuration manager by name."""
        return self._managers.get(config_name)
    
    def get_config(self, config_name: str) -> Any:
        """Get configuration by name."""
        manager = self.get_manager(config_name)
        if manager is None:
            raise ValueError(f"Configuration manager not found: {config_name}")
        return manager.get_config()
    
    def save_config(self, config_name: str, config: Any) -> None:
        """Save configuration by name."""
        manager = self.get_manager(config_name)
        if manager is None:
            raise ValueError(f"Configuration manager not found: {config_name}")
        manager.save_config(config)
    
    def validate_config(self, config_name: str, config: Any = None) -> Any:
        """Validate configuration by name."""
        manager = self.get_manager(config_name)
        if manager is None:
            raise ValueError(f"Configuration manager not found: {config_name}")
        return manager.validate_config(config)
    
    def create_backup(self, config_name: str, description: str = "Manual backup") -> Any:
        """Create backup for configuration by name."""
        manager = self.get_manager(config_name)
        if manager is None:
            raise ValueError(f"Configuration manager not found: {config_name}")
        return manager.create_backup(description)
    
    def restore_backup(self, config_name: str, backup_id: str) -> bool:
        """Restore configuration from backup by name."""
        manager = self.get_manager(config_name)
        if manager is None:
            raise ValueError(f"Configuration manager not found: {config_name}")
        return manager.restore_backup(backup_id)
    
    def reload_config(self, config_name: str) -> None:
        """Reload configuration by name."""
        manager = self.get_manager(config_name)
        if manager is None:
            raise ValueError(f"Configuration manager not found: {config_name}")
        manager.reload_config()
    
    def list_configs(self) -> List[str]:
        """List all registered configuration names."""
        return list(self._managers.keys())
    
    def get_config_info(self, config_name: str) -> Dict[str, Any]:
        """Get information about a configuration."""
        manager = self.get_manager(config_name)
        if manager is None:
            raise ValueError(f"Configuration manager not found: {config_name}")
        
        return {
            "config_name": config_name,
            "manager_type": type(manager).__name__,
            "config_path": str(manager.config_path),
            "last_loaded": manager.get_load_timestamp(),
            "exists": manager.config_path.exists(),
            "size": manager.config_path.stat().st_size if manager.config_path.exists() else 0
        }
    
    def get_all_config_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all configurations."""
        return {
            config_name: self.get_config_info(config_name)
            for config_name in self._managers.keys()
        }
    
    def start_all_watchers(self) -> None:
        """Start file watchers for all configuration managers."""
        logger.info("Starting all configuration watchers")
        
        for config_name, manager in self._managers.items():
            try:
                manager.start_watching()
                logger.info(
                    f"Started watcher for config: {config_name}",
                    extra={"data": {"config_name": config_name}}
                )
            except Exception as e:
                logger.error(
                    f"Failed to start watcher for config: {config_name}",
                    exc_info=True,
                    extra={
                        "data": {
                            "config_name": config_name,
                            "error": str(e)
                        }
                    }
                )
    
    def stop_all_watchers(self) -> None:
        """Stop file watchers for all configuration managers."""
        logger.info("Stopping all configuration watchers")
        
        for config_name, manager in self._managers.items():
            try:
                manager.stop_watching()
                logger.info(
                    f"Stopped watcher for config: {config_name}",
                    extra={"data": {"config_name": config_name}}
                )
            except Exception as e:
                logger.error(
                    f"Failed to stop watcher for config: {config_name}",
                    exc_info=True,
                    extra={
                        "data": {
                            "config_name": config_name,
                            "error": str(e)
                        }
                    }
                )
    
    def reload_all_configs(self) -> None:
        """Reload all configurations."""
        logger.info("Reloading all configurations")
        
        for config_name, manager in self._managers.items():
            try:
                manager.reload_config()
                logger.info(
                    f"Reloaded config: {config_name}",
                    extra={"data": {"config_name": config_name}}
                )
            except Exception as e:
                logger.error(
                    f"Failed to reload config: {config_name}",
                    exc_info=True,
                    extra={
                        "data": {
                            "config_name": config_name,
                            "error": str(e)
                        }
                    }
                )
    
    def validate_all_configs(self) -> Dict[str, Any]:
        """Validate all configurations."""
        logger.info("Validating all configurations")
        
        results = {}
        for config_name, manager in self._managers.items():
            try:
                result = manager.validate_config()
                results[config_name] = result
                
                status = "valid" if result.valid else "invalid"
                logger.info(
                    f"Validated config: {config_name} - {status}",
                    extra={
                        "data": {
                            "config_name": config_name,
                            "valid": result.valid,
                            "error_count": len(result.errors),
                            "warning_count": len(result.warnings)
                        }
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to validate config: {config_name}",
                    exc_info=True,
                    extra={
                        "data": {
                            "config_name": config_name,
                            "error": str(e)
                        }
                    }
                )
                results[config_name] = {
                    "valid": False,
                    "errors": [f"Validation failed: {str(e)}"],
                    "warnings": [],
                    "details": {}
                }
        
        return results
    
    def initialize_standard_configs(self) -> None:
        """Initialize standard Nova configurations."""
        if self._initialized:
            logger.warning("Configuration registry already initialized")
            return
        
        logger.info("Initializing standard Nova configurations")
        
        try:
            # Import here to avoid circular dependencies
            from utils.yaml_config_manager import DictConfigManager, YamlConfigManager
            from utils.markdown_config_manager import MarkdownConfigManager
            from models.user_profile import UserProfile
            
            # Base paths
            base_path = Path(__file__).parent.parent
            configs_path = base_path.parent / "configs"
            prompts_path = base_path / "agent" / "prompts"
            
            # 1. MCP Servers Configuration
            mcp_manager = DictConfigManager(
                config_path=configs_path / "mcp_servers.yaml",
                config_name="mcp_servers",
                default_config={}
            )
            self.register("mcp_servers", mcp_manager)
            
            # 2. User Profile Configuration
            default_profile = UserProfile(
                full_name="Nova User",
                email="user@example.com",
                timezone="UTC",
                notes="Add your personal context here."
            )
            user_profile_manager = YamlConfigManager(
                config_path=configs_path / "user_profile.yaml",
                config_name="user_profile",
                config_model=UserProfile,
                default_config=default_profile
            )
            self.register("user_profile", user_profile_manager)
            
            # 3. System Prompt Configuration
            system_prompt_manager = MarkdownConfigManager(
                config_path=prompts_path / "NOVA_SYSTEM_PROMPT.md",
                config_name="system_prompt",
                default_config="You are Nova, an AI assistant."
            )
            self.register("system_prompt", system_prompt_manager)
            
            self._initialized = True
            logger.info("Standard Nova configurations initialized successfully")
            
        except Exception as e:
            logger.error(
                "Failed to initialize standard configurations",
                exc_info=True,
                extra={"data": {"error": str(e)}}
            )
            raise
    
    def cleanup(self) -> None:
        """Clean up all configuration managers."""
        logger.info("Cleaning up configuration registry")
        
        # Stop all watchers
        self.stop_all_watchers()
        
        # Clear registry
        self._managers.clear()
        self._initialized = False
        
        logger.info("Configuration registry cleaned up")


# Global configuration registry instance
config_registry = ConfigRegistry()


# Convenience functions for common operations
def get_config(config_name: str) -> Any:
    """Get configuration by name."""
    return config_registry.get_config(config_name)


def save_config(config_name: str, config: Any) -> None:
    """Save configuration by name."""
    config_registry.save_config(config_name, config)


def validate_config(config_name: str, config: Any = None) -> Any:
    """Validate configuration by name."""
    return config_registry.validate_config(config_name, config)


def reload_config(config_name: str) -> None:
    """Reload configuration by name."""
    config_registry.reload_config(config_name)


def initialize_configs() -> None:
    """Initialize standard Nova configurations."""
    config_registry.initialize_standard_configs()


def start_config_watchers() -> None:
    """Start all configuration watchers."""
    config_registry.start_all_watchers()


def stop_config_watchers() -> None:
    """Stop all configuration watchers."""
    config_registry.stop_all_watchers() 