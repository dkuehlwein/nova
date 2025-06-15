"""
Prompt loader with hot-reload capabilities.
Handles markdown prompt files with debounced file watching and Redis event publishing.
"""

import threading
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from utils.logging import get_logger
from models.events import create_prompt_updated_event

logger = get_logger("prompt_loader")


class PromptLoader:
    """
    Prompt loader with hot-reload capabilities.
    Supports debounced file watching and Redis event publishing.
    """
    
    def __init__(self, prompt_path: Path, debounce_seconds: float = 0.5):
        self.prompt_path = Path(prompt_path)
        self.debounce_seconds = debounce_seconds
        self._prompt_cache: Optional[str] = None
        self._load_timestamp: Optional[float] = None
        self._lock = threading.RLock()
        self._observer: Optional[Observer] = None
        self._pending_reload: Optional[threading.Timer] = None
        
        # Initialize the prompt
        self._load_prompt()
    
    def _load_prompt(self) -> None:
        """Load prompt from markdown file."""
        try:
            with self._lock:
                if not self.prompt_path.exists():
                    logger.warning(
                        f"Prompt file not found: {self.prompt_path}",
                        extra={"data": {"path": str(self.prompt_path)}}
                    )
                    self._prompt_cache = ""
                    return
                
                with open(self.prompt_path, 'r', encoding='utf-8') as file:
                    self._prompt_cache = file.read()
                    self._load_timestamp = time.time()
                
                logger.info(
                    f"Prompt loaded from {self.prompt_path.name}",
                    extra={
                        "data": {
                            "path": str(self.prompt_path),
                            "size": len(self._prompt_cache),
                            "timestamp": self._load_timestamp
                        }
                    }
                )
                
        except Exception as e:
            logger.error(
                f"Failed to load prompt: {self.prompt_path}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.prompt_path),
                        "error": str(e)
                    }
                }
            )
            if self._prompt_cache is None:
                self._prompt_cache = ""
    
    def _debounced_reload(self) -> None:
        """Perform a debounced reload of the prompt."""
        with self._lock:
            # Cancel any pending reload
            if self._pending_reload:
                self._pending_reload.cancel()
            
            # Schedule a new reload with Redis event publishing
            def reload_and_publish():
                self._load_prompt()
                self._publish_prompt_updated_event()
            
            self._pending_reload = threading.Timer(
                self.debounce_seconds,
                reload_and_publish
            )
            self._pending_reload.start()
            
            logger.debug(
                f"Prompt reload scheduled in {self.debounce_seconds}s",
                extra={"data": {"path": str(self.prompt_path)}}
            )
    
    def _publish_prompt_updated_event(self) -> None:
        """Publish prompt updated event to Redis."""
        try:
            # Import here to avoid circular dependencies
            import asyncio
            from utils.redis_manager import publish
            
            event = create_prompt_updated_event(
                prompt_file=self.prompt_path.name,
                change_type="modified",
                source="prompt-loader"
            )
            
            # Since this is called from a sync context, we need to handle async publishing
            # Try to run in existing event loop if available, otherwise skip
            try:
                loop = asyncio.get_running_loop()
                # Schedule the coroutine to run in the background
                loop.create_task(publish(event))
                
                logger.info(
                    f"Prompt updated event scheduled for publishing: {self.prompt_path.name}",
                    extra={
                        "data": {
                            "event_id": event.id,
                            "prompt_file": self.prompt_path.name
                        }
                    }
                )
            except RuntimeError:
                # No running event loop, just log the event creation
                logger.info(
                    f"Prompt updated event created (no event loop for publishing): {self.prompt_path.name}",
                    extra={
                        "data": {
                            "event_id": event.id,
                            "prompt_file": self.prompt_path.name,
                            "note": "Event created but not published - no event loop"
                        }
                    }
                )
            
        except ImportError:
            # Redis manager not yet implemented (B3)
            logger.debug("Redis manager not available, skipping event publishing")
        except Exception as e:
            logger.error(
                f"Failed to publish prompt updated event: {self.prompt_path}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.prompt_path),
                        "error": str(e)
                    }
                }
            )
    
    def get_prompt(self) -> str:
        """Get the current prompt content."""
        with self._lock:
            return self._prompt_cache or ""
    
    def get_load_timestamp(self) -> Optional[float]:
        """Get the timestamp when prompt was last loaded."""
        return self._load_timestamp
    
    def start_watching(self) -> None:
        """Start watching the prompt file for changes."""
        if self._observer:
            logger.warning("Prompt watcher already started")
            return
        
        class PromptFileHandler(FileSystemEventHandler):
            def __init__(self, loader: PromptLoader):
                self.loader = loader
            
            def on_modified(self, event):
                if not event.is_directory and Path(event.src_path) == self.loader.prompt_path:
                    logger.debug(
                        f"Prompt file modified: {event.src_path}",
                        extra={"data": {"path": event.src_path}}
                    )
                    self.loader._debounced_reload()
        
        self._observer = Observer()
        self._observer.schedule(
            PromptFileHandler(self),
            str(self.prompt_path.parent),
            recursive=False
        )
        self._observer.start()
        
        logger.info(
            f"Started watching prompt file: {self.prompt_path}",
            extra={"data": {"path": str(self.prompt_path)}}
        )
    
    def stop_watching(self) -> None:
        """Stop watching the prompt file."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            
            logger.info(
                f"Stopped watching prompt file: {self.prompt_path}",
                extra={"data": {"path": str(self.prompt_path)}}
            )
        
        # Cancel any pending reload
        with self._lock:
            if self._pending_reload:
                self._pending_reload.cancel()
                self._pending_reload = None
    
    def reload_prompt(self) -> None:
        """Manually reload the prompt."""
        logger.info(
            f"Manually reloading prompt: {self.prompt_path}",
            extra={"data": {"path": str(self.prompt_path)}}
        )
        self._load_prompt()


# Global Nova system prompt loader
_nova_prompt_loader: Optional[PromptLoader] = None


def get_nova_prompt_loader() -> PromptLoader:
    """Get the global Nova system prompt loader."""
    global _nova_prompt_loader
    
    if _nova_prompt_loader is None:
        prompt_path = Path(__file__).parent.parent / "agent" / "prompts" / "NOVA_SYSTEM_PROMPT.md"
        _nova_prompt_loader = PromptLoader(prompt_path)
    
    return _nova_prompt_loader


def load_nova_system_prompt() -> str:
    """Load Nova system prompt from markdown file."""
    return get_nova_prompt_loader().get_prompt()


def start_nova_prompt_watching() -> None:
    """Start watching Nova system prompt file for changes."""
    get_nova_prompt_loader().start_watching()


def stop_nova_prompt_watching() -> None:
    """Stop watching Nova system prompt file for changes."""
    if _nova_prompt_loader:
        _nova_prompt_loader.stop_watching() 