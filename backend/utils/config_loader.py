"""
Configuration loader with hot-reload capabilities.
Handles YAML configuration files with debounced file watching.
"""

import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from utils.logging import get_logger

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
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to YAML file."""
        try:
            with self._lock:
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