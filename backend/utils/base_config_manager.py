"""
Base configuration manager with common functionality.
Provides abstract base class for all configuration types.
"""

import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, Generic, Union
from pydantic import BaseModel, ValidationError
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from utils.logging import get_logger

logger = get_logger("base_config_manager")

ConfigType = TypeVar('ConfigType', bound=Union[BaseModel, str])


class ValidationResult(BaseModel):
    """Result of configuration validation."""
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    details: Dict[str, Any] = {}


class BackupInfo(BaseModel):
    """Information about a configuration backup."""
    backup_id: str
    timestamp: str
    description: str
    size_bytes: int
    config_type: str


class BaseConfigManager(ABC, Generic[ConfigType]):
    """
    Abstract base class for all configuration managers.
    Provides common functionality: hot-reload, validation, backups, events.
    """
    
    def __init__(self, config_path: Path, config_name: str, debounce_seconds: float = 0.5):
        self.config_path = Path(config_path)
        self.config_name = config_name
        self.debounce_seconds = debounce_seconds
        self._config_cache: Optional[ConfigType] = None
        self._load_timestamp: Optional[float] = None
        self._lock = threading.RLock()
        self._observer: Optional[Observer] = None
        self._pending_reload: Optional[threading.Timer] = None
        
        # Initialize configuration
        self._load_config()
    
    @abstractmethod
    def _load_config_data(self) -> Union[Dict[str, Any], str]:
        """Load raw configuration data from storage."""
        pass
    
    @abstractmethod
    def _save_config_data(self, data: Union[Dict[str, Any], str]) -> None:
        """Save configuration data to storage."""
        pass
    
    @abstractmethod
    def _create_config_instance(self, data: Union[Dict[str, Any], str]) -> ConfigType:
        """Create typed configuration instance from raw data."""
        pass
    
    @abstractmethod
    def _serialize_config(self, config: ConfigType) -> Union[Dict[str, Any], str]:
        """Serialize configuration instance to raw data."""
        pass
    
    @abstractmethod
    def _validate_config_data(self, data: Union[Dict[str, Any], str]) -> ValidationResult:
        """Validate configuration data."""
        pass
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            if not self.config_path.exists():
                self._create_default_config()
            
            data = self._load_config_data()
            config = self._create_config_instance(data)
            
            with self._lock:
                self._config_cache = config
                self._load_timestamp = time.time()
            
            logger.info(
                f"Configuration loaded: {self.config_name}",
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "size": self.config_path.stat().st_size,
                        "timestamp": self._load_timestamp
                    }
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to load configuration: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            raise
    
    def _create_default_config(self) -> None:
        """Create default configuration if it doesn't exist."""
        logger.info(
            f"Creating default configuration: {self.config_name}",
            extra={"data": {"path": str(self.config_path)}}
        )
        # Subclasses should override this if they need custom defaults
        pass
    
    def _debounced_reload(self) -> None:
        """Debounced configuration reload."""
        with self._lock:
            if self._pending_reload:
                self._pending_reload.cancel()
            
            def reload_and_publish():
                try:
                    self._load_config()
                    self._publish_config_event("updated", "file-watcher")
                except Exception as e:
                    logger.error(f"Failed to reload config: {e}")
            
            self._pending_reload = threading.Timer(
                self.debounce_seconds,
                reload_and_publish
            )
            self._pending_reload.start()
    
    def _publish_config_event(self, operation: str, source: str) -> None:
        """Publish configuration event."""
        try:
            # Import here to avoid circular dependencies
            import asyncio
            from utils.config_events import publish_config_event
            
            # Try to run in existing event loop if available
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(publish_config_event(
                    config_type=self.config_name,
                    operation=operation,
                    source=source,
                    details={"timestamp": time.time(), "path": str(self.config_path)}
                ))
            except RuntimeError:
                # No running event loop, just log
                logger.info(
                    f"Configuration {operation}: {self.config_name}",
                    extra={
                        "data": {
                            "operation": operation,
                            "source": source,
                            "path": str(self.config_path)
                        }
                    }
                )
        except Exception as e:
            logger.error(f"Failed to publish config event: {e}")
    
    def get_config(self) -> ConfigType:
        """Get the current configuration."""
        with self._lock:
            if self._config_cache is None:
                self._load_config()
            return self._config_cache
    
    def save_config(self, config: ConfigType) -> None:
        """Save configuration to file."""
        try:
            data = self._serialize_config(config)
            self._save_config_data(data)
            
            with self._lock:
                self._config_cache = config
                self._load_timestamp = time.time()
            
            logger.info(
                f"Configuration saved: {self.config_name}",
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "timestamp": self._load_timestamp
                    }
                }
            )
            
            self._publish_config_event("updated", "api")
            
        except Exception as e:
            logger.error(
                f"Failed to save configuration: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            raise
    
    def validate_config(self, config: Optional[ConfigType] = None) -> ValidationResult:
        """Validate configuration."""
        if config is None:
            config = self.get_config()
        
        data = self._serialize_config(config)
        return self._validate_config_data(data)
    
    def create_backup(self, description: str = "Manual backup") -> BackupInfo:
        """Create a backup of the current configuration."""
        config = self.get_config()
        
        # Generate backup ID with timestamp
        timestamp = datetime.now()
        backup_id = f"{self.config_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Create backup directory
        backup_dir = self.config_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        # Save backup
        backup_path = backup_dir / f"{backup_id}{self.config_path.suffix}"
        data = self._serialize_config(config)
        
        with open(backup_path, 'w', encoding='utf-8') as file:
            if isinstance(data, str):
                file.write(data)
            else:
                import yaml
                yaml.safe_dump(data, file, default_flow_style=False, sort_keys=True, indent=2)
        
        backup_info = BackupInfo(
            backup_id=backup_id,
            timestamp=timestamp.isoformat(),
            description=description,
            size_bytes=backup_path.stat().st_size,
            config_type=self.config_name
        )
        
        logger.info(
            f"Configuration backup created: {backup_id}",
            extra={
                "data": {
                    "backup_id": backup_id,
                    "path": str(backup_path),
                    "size": backup_info.size_bytes
                }
            }
        )
        
        return backup_info
    
    def restore_backup(self, backup_id: str) -> bool:
        """Restore configuration from backup."""
        backup_dir = self.config_path.parent / "backups"
        backup_path = backup_dir / f"{backup_id}{self.config_path.suffix}"
        
        if not backup_path.exists():
            return False
        
        try:
            # Create automatic backup before restore
            self.create_backup(f"Pre-restore backup for {backup_id}")
            
            # Load backup data
            with open(backup_path, 'r', encoding='utf-8') as file:
                if self.config_path.suffix == '.yaml':
                    import yaml
                    data = yaml.safe_load(file)
                else:
                    data = file.read()
            
            # Validate and save
            config = self._create_config_instance(data)
            self.save_config(config)
            
            logger.info(
                f"Configuration restored from backup: {backup_id}",
                extra={
                    "data": {
                        "backup_id": backup_id,
                        "path": str(backup_path)
                    }
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to restore backup: {backup_id}",
                exc_info=True,
                extra={
                    "data": {
                        "backup_id": backup_id,
                        "error": str(e)
                    }
                }
            )
            return False
    
    def start_watching(self) -> None:
        """Start watching configuration file for changes."""
        if self._observer:
            logger.warning(f"File watcher already started for {self.config_name}")
            return
        
        class ConfigFileHandler(FileSystemEventHandler):
            def __init__(self, manager: BaseConfigManager):
                self.manager = manager
            
            def on_modified(self, event):
                if not event.is_directory and Path(event.src_path) == self.manager.config_path:
                    logger.debug(
                        f"Configuration file modified: {event.src_path}",
                        extra={"data": {"path": event.src_path}}
                    )
                    self.manager._debounced_reload()
        
        self._observer = Observer()
        self._observer.schedule(
            ConfigFileHandler(self),
            str(self.config_path.parent),
            recursive=False
        )
        self._observer.start()
        
        logger.info(
            f"Started watching configuration: {self.config_name}",
            extra={"data": {"path": str(self.config_path)}}
        )
    
    def stop_watching(self) -> None:
        """Stop watching configuration file."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            
            logger.info(
                f"Stopped watching configuration: {self.config_name}",
                extra={"data": {"path": str(self.config_path)}}
            )
        
        # Cancel any pending reload
        with self._lock:
            if self._pending_reload:
                self._pending_reload.cancel()
                self._pending_reload = None
    
    def reload_config(self) -> None:
        """Manually reload configuration."""
        logger.info(
            f"Manually reloading configuration: {self.config_name}",
            extra={"data": {"path": str(self.config_path)}}
        )
        self._load_config()
        self._publish_config_event("reloaded", "manual")
    
    def get_load_timestamp(self) -> Optional[float]:
        """Get the timestamp when configuration was last loaded."""
        return self._load_timestamp 