"""
Input Hook Registry for managing multiple input source hooks.

Extends Nova's ConfigRegistry pattern to provide centralized management
of all input hooks with dynamic configuration and lifecycle management.
"""

from typing import Dict, Type, Optional, Any, List
from pathlib import Path
import importlib
import inspect

from utils.config_registry import ConfigRegistry  
from utils.logging import get_logger
from .base_hook import BaseInputHook
from .models import InputHooksConfig, HookConfig, AnyHookConfig, EmailHookConfig, CalendarHookConfig, OutlookEmailHookConfig

logger = get_logger("input_hook_registry")


class InputHookRegistry(ConfigRegistry):
    """
    Registry for managing input hooks.
    
    Extends ConfigRegistry to provide:
    - Dynamic hook registration and discovery
    - Hook lifecycle management (start/stop polling)
    - Configuration-driven hook instantiation
    - Health monitoring and statistics
    """
    
    def __init__(self):
        super().__init__()
        self._hook_instances: Dict[str, BaseInputHook] = {}
        self._hook_classes: Dict[str, Type[BaseInputHook]] = {}
        self._initialized = False
    
    def initialize_hooks(self) -> None:
        """Initialize the hook registry and discover available hooks."""
        if self._initialized:
            logger.warning("Hook registry already initialized")
            return
        
        try:
            logger.info("Initializing input hook registry")
            
            # Register built-in hook types
            self._register_builtin_hook_types()
            
            # Load hook configurations
            self._load_hook_configurations()
            
            # Initialize hook instances
            self._initialize_hook_instances()
            
            self._initialized = True
            logger.info("Input hook registry initialized successfully")
            
        except Exception as e:
            logger.error(
                "Failed to initialize hook registry", 
                exc_info=True,
                extra={"data": {"error": str(e)}}
            )
            raise
    
    def _register_builtin_hook_types(self) -> None:
        """Register built-in hook types."""
        # Import hook classes dynamically to avoid circular imports
        # Use relative imports when running from within backend directory (Docker containers)
        # Use absolute imports when running from project root (local development)
        import os
        if os.getcwd().endswith('backend') or os.path.exists('/.dockerenv'):
            # Running in Docker container or from backend directory
            hook_types = {
                "email": "input_hooks.email_hook.EmailInputHook",
                "calendar": "input_hooks.calendar_hook.CalendarInputHook",
                "outlook_email": "input_hooks.outlook_email_hook.OutlookEmailHook",
                # Future hook types will be added here:
                # "slack": "input_hooks.slack_hook.SlackInputHook",
            }
        else:
            # Running from project root (local development)
            hook_types = {
                "email": "backend.input_hooks.email_hook.EmailInputHook",
                "calendar": "backend.input_hooks.calendar_hook.CalendarInputHook",
                "outlook_email": "backend.input_hooks.outlook_email_hook.OutlookEmailHook",
                # Future hook types will be added here:
                # "slack": "backend.input_hooks.slack_hook.SlackInputHook",
            }
        
        for hook_type, class_path in hook_types.items():
            try:
                self._register_hook_class(hook_type, class_path)
            except Exception as e:
                logger.warning(
                    f"Failed to register hook type {hook_type}: {e}",
                    extra={"data": {"hook_type": hook_type, "error": str(e)}}
                )
    
    def _register_hook_class(self, hook_type: str, class_path: str) -> None:
        """Register a hook class by import path."""
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            hook_class = getattr(module, class_name)
            
            # Import BaseInputHook dynamically to avoid module identity issues
            # Use same import strategy as hook classes to ensure same module context
            import os
            if os.getcwd().endswith('backend') or os.path.exists('/.dockerenv'):
                base_module_path = "input_hooks.base_hook"
            else:
                base_module_path = "backend.input_hooks.base_hook"
            
            base_module = importlib.import_module(base_module_path)
            BaseInputHookDynamic = getattr(base_module, "BaseInputHook")
            
            # Validate it's a proper hook class
            if not issubclass(hook_class, BaseInputHookDynamic):
                raise ValueError(f"Class {class_name} is not a subclass of BaseInputHook")
            
            self._hook_classes[hook_type] = hook_class
            logger.info(
                f"Registered hook type: {hook_type}",
                extra={"data": {"hook_type": hook_type, "class_path": class_path}}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to register hook class: {class_path}",
                exc_info=True,
                extra={"data": {"hook_type": hook_type, "class_path": class_path, "error": str(e)}}
            )
            raise
    
    def _load_hook_configurations(self) -> None:
        """Load hook configurations from the config registry."""
        try:
            # Import the global config registry
            from utils.config_registry import config_registry
            
            # Check if input_hooks config is available
            config_manager = config_registry.get_manager("input_hooks")
            if not config_manager:
                logger.info("No input_hooks configuration found, using defaults")
                return
            
            hooks_config = config_manager.get_config()
            logger.info(
                f"Loaded hook configurations for {len(hooks_config.hooks)} hooks",
                extra={"data": {"hook_count": len(hooks_config.hooks)}}
            )
            
        except Exception as e:
            logger.warning(
                f"Failed to load hook configurations: {e}",
                extra={"data": {"error": str(e)}}
            )
    
    def _initialize_hook_instances(self) -> None:
        """Initialize hook instances from configurations."""
        try:
            # Import the global config registry
            from utils.config_registry import config_registry
            
            config_manager = config_registry.get_manager("input_hooks")
            if not config_manager:
                logger.info("No hook configurations to initialize")
                return
            
            hooks_config = config_manager.get_config()
            
            for hook_name, hook_config in hooks_config.hooks.items():
                try:
                    self._create_hook_instance(hook_name, hook_config)
                except Exception as e:
                    logger.error(
                        f"Failed to create hook instance: {hook_name}",
                        exc_info=True,
                        extra={"data": {"hook_name": hook_name, "error": str(e)}}
                    )
                    continue
            
            logger.info(
                f"Initialized {len(self._hook_instances)} hook instances",
                extra={"data": {
                    "initialized_hooks": list(self._hook_instances.keys()),
                    "total_configured": len(hooks_config.hooks)
                }}
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize hook instances",
                exc_info=True,
                extra={"data": {"error": str(e)}}
            )
    
    def _create_hook_instance(self, hook_name: str, hook_config: AnyHookConfig) -> BaseInputHook:
        """Create a hook instance from configuration."""
        hook_type = hook_config.hook_type
        
        if hook_type not in self._hook_classes:
            raise ValueError(f"Unknown hook type: {hook_type}. Available types: {list(self._hook_classes.keys())}")
        
        hook_class = self._hook_classes[hook_type]
        
        # Create instance
        hook_instance = hook_class(hook_name, hook_config)
        
        # Store in registry
        self._hook_instances[hook_name] = hook_instance
        
        logger.info(
            f"Created hook instance: {hook_name}",
            extra={"data": {
                "hook_name": hook_name,
                "hook_type": hook_type,
                "enabled": hook_config.enabled
            }}
        )
        
        return hook_instance
    
    # Hook management methods
    def get_hook(self, hook_name: str) -> Optional[BaseInputHook]:
        """Get a hook instance by name."""
        return self._hook_instances.get(hook_name)
    
    def list_hooks(self) -> List[str]:
        """List all registered hook names."""
        return list(self._hook_instances.keys())
    
    def list_enabled_hooks(self) -> List[str]:
        """List enabled hook names."""
        enabled_hooks = []
        for hook_name, hook in self._hook_instances.items():
            if hook.config.enabled:
                enabled_hooks.append(hook_name)
        return enabled_hooks
    
    def get_hook_config(self, hook_name: str) -> Optional[AnyHookConfig]:
        """Get configuration for a specific hook."""
        hook = self.get_hook(hook_name)
        return hook.config if hook else None
    
    def update_hook_config(self, hook_name: str, new_config: AnyHookConfig) -> bool:
        """Update configuration for a specific hook."""
        try:
            # Update in config file
            from utils.config_registry import config_registry
            config_manager = config_registry.get_manager("input_hooks")
            if not config_manager:
                raise ValueError("No input_hooks configuration manager available")
            
            hooks_config = config_manager.get_config()
            hooks_config.hooks[hook_name] = new_config
            config_manager.save_config(hooks_config)
            
            # Recreate hook instance with new config
            if hook_name in self._hook_instances:
                old_hook = self._hook_instances[hook_name]
                # Clean up old hook if needed
                try:
                    old_hook.stop_watching()  # Remove await - this is sync
                except:
                    pass
            
            # Create new instance
            self._create_hook_instance(hook_name, new_config)
            
            logger.info(
                f"Updated hook configuration: {hook_name}",
                extra={"data": {"hook_name": hook_name}}
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to update hook configuration: {hook_name}",
                exc_info=True,
                extra={"data": {"hook_name": hook_name, "error": str(e)}}
            )
            return False
    
    # Celery integration methods
    def get_celery_schedules(self) -> Dict[str, Dict[str, Any]]:
        """Get Celery Beat schedules for all enabled hooks."""
        schedules = {}
        
        for hook_name, hook in self._hook_instances.items():
            if hook.config.enabled and hook.config.polling_interval > 0:
                schedules[f"process-{hook_name}"] = {
                    "task": "tasks.hook_tasks.process_hook_items",
                    "schedule": hook.config.polling_interval,
                    "args": [hook_name],
                    "options": {"queue": hook.config.queue_name or "hooks"}
                }
        
        return schedules
    
    def get_celery_routes(self) -> Dict[str, Dict[str, str]]:
        """Get Celery task routes for hook processing."""
        routes = {
            # Generic hook processing tasks
            "tasks.hook_tasks.process_hook_items": {"queue": "hooks"},
            "tasks.hook_tasks.process_single_item": {"queue": "hooks"},
        }
        
        # Add hook-specific routing if needed
        for hook_name, hook in self._hook_instances.items():
            if hook.config.queue_name and hook.config.queue_name != "hooks":
                routes[f"tasks.hook_tasks.process_hook_items[{hook_name}]"] = {
                    "queue": hook.config.queue_name
                }
        
        return routes
    
    # Health and monitoring methods
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all hooks."""
        health_results = {}
        
        for hook_name, hook in self._hook_instances.items():
            try:
                health_results[hook_name] = await hook.health_check()
            except Exception as e:
                health_results[hook_name] = {
                    "hook_name": hook_name,
                    "healthy": False,
                    "error": str(e)
                }
        
        return health_results
    
    def get_hook_stats(self, hook_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific hook."""
        hook = self.get_hook(hook_name)
        return hook.get_stats() if hook else None
    
    def get_all_hook_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all hooks."""
        stats = {}
        for hook_name, hook in self._hook_instances.items():
            stats[hook_name] = hook.get_stats()
        return stats
    
    # Registry management methods
    def reload_all_hooks(self) -> None:
        """Reload all hook configurations and instances."""
        logger.info("Reloading all hooks")
        
        # Clear existing instances
        self._hook_instances.clear()
        
        # Reinitialize
        self._initialize_hook_instances()
        
        logger.info("All hooks reloaded")
    
    def cleanup(self) -> None:
        """Clean up all hooks and registry resources."""
        logger.info("Cleaning up input hook registry")
        
        # Stop all hooks
        for hook_name, hook in self._hook_instances.items():
            try:
                # Stop file watchers if any
                hook.stop_watching()
            except Exception as e:
                logger.warning(f"Error stopping hook {hook_name}: {e}")
        
        # Clear registries
        self._hook_instances.clear()
        self._hook_classes.clear()
        
        # Call parent cleanup
        super().cleanup()
        
        self._initialized = False
        logger.info("Input hook registry cleaned up")


# Global input hook registry instance
input_hook_registry = InputHookRegistry()


# Convenience functions
def get_hook(hook_name: str) -> Optional[BaseInputHook]:
    """Get a hook instance by name."""
    return input_hook_registry.get_hook(hook_name)


def list_hooks() -> List[str]:
    """List all registered hook names."""
    return input_hook_registry.list_hooks()


def list_enabled_hooks() -> List[str]:
    """List enabled hook names.""" 
    return input_hook_registry.list_enabled_hooks()


def initialize_hooks() -> None:
    """Initialize the hook registry."""
    input_hook_registry.initialize_hooks()


def cleanup_hooks() -> None:
    """Clean up hook registry."""
    input_hook_registry.cleanup()