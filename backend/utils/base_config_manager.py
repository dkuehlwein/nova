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

# Global shared observer registry - one Observer per directory
_shared_observers: Dict[str, Observer] = {}
_shared_observers_lock = threading.Lock()
_observer_handlers: Dict[str, Dict[str, FileSystemEventHandler]] = {}  # dir -> {config_name -> handler}


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
                "Configuration loaded",
                extra={
                    "data": {
                        "config_name": self.config_name,
                        "path": str(self.config_path),
                        "size": self.config_path.stat().st_size,
                        "timestamp": self._load_timestamp
                    }
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to load configuration",
                exc_info=True,
                extra={
                    "data": {
                        "config_name": self.config_name,
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            raise
    
    def _create_default_config(self) -> None:
        """Create default configuration if it doesn't exist."""
        logger.info(
            "Creating default configuration",
            extra={"data": {"config_name": self.config_name, "path": str(self.config_path)}}
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
                    logger.error("Failed to reload config", extra={"data": {"error": str(e)}})
            
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
                    "Configuration event published",
                    extra={
                        "data": {
                            "config_name": self.config_name,
                            "operation": operation,
                            "source": source,
                            "path": str(self.config_path)
                        }
                    }
                )
        except Exception as e:
            logger.error("Failed to publish config event", extra={"data": {"error": str(e)}})
    
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
                "Configuration saved",
                extra={
                    "data": {
                        "config_name": self.config_name,
                        "path": str(self.config_path),
                        "timestamp": self._load_timestamp
                    }
                }
            )
            
            self._publish_config_event("updated", "api")
            
        except Exception as e:
            logger.error(
                "Failed to save configuration",
                exc_info=True,
                extra={
                    "data": {
                        "config_name": self.config_name,
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
            "Configuration backup created",
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
                "Configuration restored from backup",
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
                "Failed to restore backup",
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
        """Start watching configuration file for changes.

        Uses a shared Observer per directory to avoid watchdog's
        'already scheduled' error when multiple configs share the same directory.
        """
        global _shared_observers, _observer_handlers

        if self._observer:
            logger.warning("File watcher already started", extra={"data": {"config_name": self.config_name}})
            return

        watch_dir = str(self.config_path.parent)

        class ConfigFileHandler(FileSystemEventHandler):
            def __init__(self, manager: BaseConfigManager):
                self.manager = manager

            def on_modified(self, event):
                if not event.is_directory and Path(event.src_path) == self.manager.config_path:
                    logger.debug(
                        "Configuration file modified",
                        extra={"data": {"config_name": self.manager.config_name, "path": event.src_path}}
                    )
                    self.manager._debounced_reload()

        handler = ConfigFileHandler(self)

        with _shared_observers_lock:
            # Check if we already have an observer for this directory
            if watch_dir in _shared_observers:
                # Reuse existing observer - schedule our handler
                observer = _shared_observers[watch_dir]
                try:
                    observer.schedule(handler, watch_dir, recursive=False)
                except RuntimeError:
                    # Directory already being watched - this is expected
                    # The existing watch will dispatch to all handlers
                    pass
                _observer_handlers[watch_dir][self.config_name] = handler
                self._observer = observer  # Share reference
            else:
                # Create new observer for this directory
                observer = Observer()
                observer.schedule(handler, watch_dir, recursive=False)
                observer.start()
                _shared_observers[watch_dir] = observer
                _observer_handlers[watch_dir] = {self.config_name: handler}
                self._observer = observer

        logger.info(
            "Started watching configuration",
            extra={"data": {"config_name": self.config_name, "path": str(self.config_path)}}
        )
    
    def stop_watching(self) -> None:
        """Stop watching configuration file.

        Only stops the shared Observer when all configs using it have stopped.
        """
        global _shared_observers, _observer_handlers

        watch_dir = str(self.config_path.parent)

        with _shared_observers_lock:
            if watch_dir in _observer_handlers and self.config_name in _observer_handlers[watch_dir]:
                # Remove our handler from the registry
                del _observer_handlers[watch_dir][self.config_name]

                # If no more handlers for this directory, stop the observer
                if not _observer_handlers[watch_dir]:
                    if watch_dir in _shared_observers:
                        observer = _shared_observers[watch_dir]
                        observer.stop()
                        observer.join()
                        del _shared_observers[watch_dir]
                    del _observer_handlers[watch_dir]

        self._observer = None

        logger.info(
            "Stopped watching configuration",
            extra={"data": {"config_name": self.config_name, "path": str(self.config_path)}}
        )

        # Cancel any pending reload
        with self._lock:
            if self._pending_reload:
                self._pending_reload.cancel()
                self._pending_reload = None
    
    def reload_config(self) -> None:
        """Manually reload configuration."""
        logger.info(
            "Manually reloading configuration",
            extra={"data": {"config_name": self.config_name, "path": str(self.config_path)}}
        )
        self._load_config()
        self._publish_config_event("reloaded", "manual")
    
    def get_load_timestamp(self) -> Optional[float]:
        """Get the timestamp when configuration was last loaded."""
        return self._load_timestamp 