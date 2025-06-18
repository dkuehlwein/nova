"""
Configuration loader with hot-reload capabilities.
Handles YAML configuration files with debounced file watching.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from pydantic import ValidationError

from utils.logging import get_logger
from models.config import MCPServersConfig, ConfigValidationResult, ConfigBackupInfo

logger = get_logger("config_loader")


class ConfigLoader:
    """
    Configuration loader with hot-reload capabilities.
    Supports debounced file watching to avoid race conditions.
    """
    
    def __init__(self, config_path: Path, debounce_seconds: float = 0.5):
        self.config_path = Path(config_path)
        self.debounce_seconds = debounce_seconds
        self._config_cache: Optional[Dict[str, Any]] = None
        self._load_timestamp: Optional[float] = None
        self._lock = threading.RLock()
        self._observer: Optional[Observer] = None
        self._pending_reload: Optional[threading.Timer] = None
        
        # Initialize the config
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            with self._lock:
                if not self.config_path.exists():
                    logger.warning(
                        f"Configuration file not found: {self.config_path}",
                        extra={"data": {"path": str(self.config_path)}}
                    )
                    self._config_cache = {}
                    return
                
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    self._config_cache = yaml.safe_load(file) or {}
                    self._load_timestamp = time.time()
                
                logger.info(
                    f"Configuration loaded from {self.config_path.name}",
                    extra={
                        "data": {
                            "path": str(self.config_path),
                            "entries": len(self._config_cache),
                            "timestamp": self._load_timestamp
                        }
                    }
                )
                
        except yaml.YAMLError as e:
            logger.error(
                f"Failed to parse YAML configuration: {self.config_path}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            # Keep existing config on parse error
            if self._config_cache is None:
                self._config_cache = {}
                
        except Exception as e:
            logger.error(
                f"Failed to load configuration: {self.config_path}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            if self._config_cache is None:
                self._config_cache = {}
    
    def _debounced_reload(self) -> None:
        """Perform a debounced reload of the configuration."""
        with self._lock:
            # Cancel any pending reload
            if self._pending_reload:
                self._pending_reload.cancel()
            
            # Schedule a new reload
            self._pending_reload = threading.Timer(
                self.debounce_seconds,
                self._load_config
            )
            self._pending_reload.start()
            
            logger.debug(
                f"Configuration reload scheduled in {self.debounce_seconds}s",
                extra={"data": {"path": str(self.config_path)}}
            )
    
    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration."""
        with self._lock:
            return self._config_cache.copy() if self._config_cache else {}
    
    def get_load_timestamp(self) -> Optional[float]:
        """Get the timestamp when config was last loaded."""
        return self._load_timestamp
    
    def start_watching(self) -> None:
        """Start watching the configuration file for changes."""
        if self._observer:
            logger.warning("Configuration watcher already started")
            return
        
        class ConfigFileHandler(FileSystemEventHandler):
            def __init__(self, loader: ConfigLoader):
                self.loader = loader
            
            def on_modified(self, event):
                if not event.is_directory and Path(event.src_path) == self.loader.config_path:
                    logger.debug(
                        f"Configuration file modified: {event.src_path}",
                        extra={"data": {"path": event.src_path}}
                    )
                    self.loader._debounced_reload()
        
        self._observer = Observer()
        self._observer.schedule(
            ConfigFileHandler(self),
            str(self.config_path.parent),
            recursive=False
        )
        self._observer.start()
        
        logger.info(
            f"Started watching configuration file: {self.config_path}",
            extra={"data": {"path": str(self.config_path)}}
        )
    
    def stop_watching(self) -> None:
        """Stop watching the configuration file."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            
            logger.info(
                f"Stopped watching configuration file: {self.config_path}",
                extra={"data": {"path": str(self.config_path)}}
            )
        
        # Cancel any pending reload
        with self._lock:
            if self._pending_reload:
                self._pending_reload.cancel()
                self._pending_reload = None
    
    def reload_config(self) -> None:
        """Manually reload the configuration."""
        logger.info(
            f"Manually reloading configuration: {self.config_path}",
            extra={"data": {"path": str(self.config_path)}}
        )
        self._load_config()
    
    def validate_config(self, config: Optional[Dict[str, Any]] = None) -> ConfigValidationResult:
        """Validate MCP server configuration."""
        if config is None:
            config = self.get_config()
        
        errors = []
        warnings = []
        server_count = len(config)
        enabled_count = 0
        
        try:
            # Validate using Pydantic model
            validated_config = MCPServersConfig(config)
            
            # Count enabled servers
            for server_config in validated_config.values():
                if server_config.enabled:
                    enabled_count += 1
            
            # Check for warnings
            if enabled_count == 0:
                warnings.append("No MCP servers are enabled")
            
            if server_count > 10:
                warnings.append(f"Large number of servers configured ({server_count})")
            
            logger.info(
                "Configuration validation successful",
                extra={
                    "data": {
                        "server_count": server_count,
                        "enabled_count": enabled_count,
                        "warnings": len(warnings)
                    }
                }
            )
            
        except ValidationError as e:
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"]) if error["loc"] else "root"
                errors.append(f"{field_path}: {error['msg']}")
            
            logger.warning(
                "Configuration validation failed",
                extra={
                    "data": {
                        "error_count": len(errors),
                        "server_count": server_count
                    }
                }
            )
        
        except Exception as e:
            errors.append(f"Unexpected validation error: {str(e)}")
            logger.error(
                "Unexpected error during configuration validation",
                exc_info=True,
                extra={"data": {"error": str(e)}}
            )
        
        return ConfigValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            server_count=server_count,
            enabled_count=enabled_count
        )
    
    def create_backup(self, description: Optional[str] = None) -> ConfigBackupInfo:
        """Create a backup of the current configuration."""
        config = self.get_config()
        
        # Generate backup ID with timestamp
        timestamp = datetime.now()
        backup_id = f"mcp_config_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Create backup directory relative to config file
        backup_dir = self.config_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        # Save backup
        backup_path = backup_dir / f"{backup_id}.yaml"
        with open(backup_path, 'w', encoding='utf-8') as file:
            yaml.safe_dump(config, file, default_flow_style=False, sort_keys=True, indent=2)
        
        backup_info = ConfigBackupInfo(
            backup_id=backup_id,
            timestamp=timestamp.isoformat(),
            server_count=len(config),
            description=description
        )
        
        logger.info(
            f"Configuration backup created: {backup_id}",
            extra={
                "data": {
                    "backup_id": backup_id,
                    "path": str(backup_path),
                    "server_count": len(config)
                }
            }
        )
        
        return backup_info
    
    def list_backups(self) -> List[ConfigBackupInfo]:
        """List available configuration backups."""
        backup_dir = self.config_path.parent / "backups"
        if not backup_dir.exists():
            return []
        
        backups = []
        for backup_file in backup_dir.glob("mcp_config_*.yaml"):
            try:
                # Parse timestamp from filename
                name_parts = backup_file.stem.split("_")
                if len(name_parts) >= 4:  # mcp_config_YYYYMMDD_HHMMSS
                    date_str = "_".join(name_parts[2:4])
                    timestamp = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                    
                    # Load backup to get server count
                    with open(backup_file, 'r', encoding='utf-8') as file:
                        backup_config = yaml.safe_load(file) or {}
                    
                    backups.append(ConfigBackupInfo(
                        backup_id=backup_file.stem,
                        timestamp=timestamp.isoformat(),
                        server_count=len(backup_config)
                    ))
                    
            except Exception as e:
                logger.warning(
                    f"Failed to parse backup file: {backup_file}",
                    extra={"data": {"error": str(e)}}
                )
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.timestamp, reverse=True)
        return backups
    
    def restore_backup(self, backup_id: str) -> bool:
        """Restore configuration from backup."""
        backup_dir = self.config_path.parent / "backups"
        backup_path = backup_dir / f"{backup_id}.yaml"
        
        if not backup_path.exists():
            logger.error(
                f"Backup not found: {backup_id}",
                extra={"data": {"backup_id": backup_id, "path": str(backup_path)}}
            )
            return False
        
        try:
            # Load backup configuration
            with open(backup_path, 'r', encoding='utf-8') as file:
                backup_config = yaml.safe_load(file) or {}
            
            # Validate backup before restoring
            validation_result = self.validate_config(backup_config)
            if not validation_result.valid:
                logger.error(
                    f"Backup configuration is invalid: {backup_id}",
                    extra={
                        "data": {
                            "backup_id": backup_id,
                            "errors": validation_result.errors
                        }
                    }
                )
                return False
            
            # Create current backup before restoring
            self.create_backup("Pre-restore backup")
            
            # Restore configuration
            self.save_config(backup_config)
            
            logger.info(
                f"Configuration restored from backup: {backup_id}",
                extra={
                    "data": {
                        "backup_id": backup_id,
                        "server_count": len(backup_config)
                    }
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to restore backup: {backup_id}",
                exc_info=True,
                extra={"data": {"backup_id": backup_id, "error": str(e)}}
            )
            return False

    def save_config(self, config: Dict[str, Any], validate: bool = True) -> None:
        """Save configuration to YAML file with optional validation."""
        try:
            # Validate configuration before saving if requested
            if validate:
                validation_result = self.validate_config(config)
                if not validation_result.valid:
                    error_msg = f"Configuration validation failed: {'; '.join(validation_result.errors)}"
                    logger.error(
                        "Cannot save invalid configuration",
                        extra={
                            "data": {
                                "errors": validation_result.errors,
                                "server_count": validation_result.server_count
                            }
                        }
                    )
                    raise ValueError(error_msg)
            
            with self._lock:
                # Create backup before saving
                if self.config_path.exists():
                    self.create_backup("Auto-backup before save")
                
                # Create parent directory if it doesn't exist
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write to temporary file first, then move (atomic operation)
                temp_path = self.config_path.with_suffix('.tmp')
                with open(temp_path, 'w', encoding='utf-8') as file:
                    yaml.safe_dump(
                        config,
                        file,
                        default_flow_style=False,
                        sort_keys=True,
                        indent=2
                    )
                
                # Atomic move
                temp_path.replace(self.config_path)
                
                # Update cache
                self._config_cache = config.copy()
                self._load_timestamp = time.time()
                
                logger.info(
                    f"Configuration saved to {self.config_path.name}",
                    extra={
                        "data": {
                            "path": str(self.config_path),
                            "entries": len(config),
                            "timestamp": self._load_timestamp
                        }
                    }
                )
                
        except Exception as e:
            logger.error(
                f"Failed to save configuration: {self.config_path}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            raise


# Global MCP servers configuration loader
_mcp_config_loader: Optional[ConfigLoader] = None


def get_mcp_config_loader() -> ConfigLoader:
    """Get the global MCP configuration loader."""
    global _mcp_config_loader
    
    if _mcp_config_loader is None:
        config_path = Path(__file__).parent.parent.parent / "configs" / "mcp_servers.yaml"
        _mcp_config_loader = ConfigLoader(config_path)
    
    return _mcp_config_loader


def load_mcp_yaml() -> Dict[str, Any]:
    """Load MCP servers configuration from YAML."""
    return get_mcp_config_loader().get_config()


def save_mcp_yaml(config: Dict[str, Any]) -> None:
    """Save MCP servers configuration to YAML."""
    get_mcp_config_loader().save_config(config)


def start_mcp_config_watching() -> None:
    """Start watching MCP configuration file for changes."""
    get_mcp_config_loader().start_watching()


def stop_mcp_config_watching() -> None:
    """Stop watching MCP configuration file for changes."""
    if _mcp_config_loader:
        _mcp_config_loader.stop_watching() 