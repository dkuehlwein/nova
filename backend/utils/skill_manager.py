"""
Skill Manager for Nova's dynamic pluggable skills system.

Manages skill discovery, loading, and lifecycle following ADR-014.
Unlike other config managers, SkillManager handles a directory of skills
rather than a single configuration file.
"""

import importlib.util
import threading
from pathlib import Path
from typing import Optional

import yaml
from langchain_core.tools import BaseTool
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from models.skill_models import (
    SkillDefinition,
    SkillManifest,
    SkillNotFoundError,
    SkillLoadError,
)
from utils.logging import get_logger

logger = get_logger("skill_manager")


class SkillManager:
    """
    Manages skill discovery and loading with hot-reload support.

    Scans the skills directory for valid skill packages (directories with manifest.yaml),
    maintains a lightweight registry of available skills, and loads full skill definitions
    (instructions + tools) on demand.
    """

    def __init__(self, skills_path: Path, debounce_seconds: float = 0.5):
        """
        Initialize the SkillManager.

        Args:
            skills_path: Path to the skills directory (e.g., backend/skills/)
            debounce_seconds: Debounce delay for file change events
        """
        self.skills_path = Path(skills_path)
        self.debounce_seconds = debounce_seconds
        self._registry: dict[str, SkillManifest] = {}
        self._lock = threading.RLock()
        self._observer: Optional[Observer] = None
        self._pending_reload: Optional[threading.Timer] = None

        # Ensure skills directory exists
        self.skills_path.mkdir(parents=True, exist_ok=True)

        # Initial scan
        self._scan_skills()

    def _scan_skills(self) -> None:
        """Scan skills directory and populate registry with manifests."""
        with self._lock:
            self._registry.clear()

            if not self.skills_path.exists():
                logger.warning(
                    "Skills directory does not exist",
                    extra={"data": {"path": str(self.skills_path)}},
                )
                return

            # Scan each subdirectory for valid skills
            for skill_dir in self.skills_path.iterdir():
                if not skill_dir.is_dir():
                    continue

                # Skip hidden directories and __pycache__
                if skill_dir.name.startswith(".") or skill_dir.name == "__pycache__":
                    continue

                manifest_path = skill_dir / "manifest.yaml"
                if not manifest_path.exists():
                    logger.debug(
                        "Skipping directory without manifest",
                        extra={"data": {"directory": skill_dir.name, "path": str(skill_dir)}},
                    )
                    continue

                try:
                    manifest = self._load_manifest(manifest_path)
                    self._registry[skill_dir.name] = manifest
                    logger.info(
                        "Discovered skill",
                        extra={
                            "data": {
                                "skill": skill_dir.name,
                                "name": manifest.name,
                                "version": manifest.version,
                                "description": manifest.description,
                            }
                        },
                    )
                except Exception as e:
                    logger.error(
                        "Failed to load skill manifest",
                        exc_info=True,
                        extra={"data": {"skill": skill_dir.name, "path": str(manifest_path), "error": str(e)}},
                    )

            logger.info(
                "Skill scan complete",
                extra={"data": {"count": len(self._registry), "skills": list(self._registry.keys())}},
            )

    def _load_manifest(self, manifest_path: Path) -> SkillManifest:
        """Load and validate a skill manifest from YAML file."""
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return SkillManifest(**data)

    def get_skill_summaries(self) -> dict[str, str]:
        """
        Return name -> description mapping for system prompt injection.

        This lightweight representation is used to advertise available skills
        to the LLM without loading full skill definitions.
        """
        with self._lock:
            return {name: info.description for name, info in self._registry.items()}

    def list_skills(self) -> list[str]:
        """Return list of available skill names."""
        with self._lock:
            return list(self._registry.keys())

    def get_manifest(self, skill_name: str) -> SkillManifest:
        """Get manifest for a specific skill."""
        with self._lock:
            if skill_name not in self._registry:
                raise SkillNotFoundError(f"Unknown skill: {skill_name}")
            return self._registry[skill_name]

    async def load_skill(self, skill_name: str) -> SkillDefinition:
        """
        Load full skill definition including instructions and tools.

        Args:
            skill_name: Name of the skill to load (directory name)

        Returns:
            SkillDefinition with manifest, instructions, and loaded tools

        Raises:
            SkillNotFoundError: If skill does not exist
            SkillLoadError: If skill fails to load
        """
        with self._lock:
            if skill_name not in self._registry:
                raise SkillNotFoundError(f"Unknown skill: {skill_name}")

            manifest = self._registry[skill_name]

        skill_path = self.skills_path / skill_name

        # Load instructions
        instructions_path = skill_path / "instructions.md"
        if not instructions_path.exists():
            raise SkillLoadError(f"Skill {skill_name} missing instructions.md")

        try:
            instructions = instructions_path.read_text(encoding="utf-8")
        except Exception as e:
            raise SkillLoadError(f"Failed to read instructions for {skill_name}: {e}")

        # Load tools
        tools_path = skill_path / "tools.py"
        tools = []
        if tools_path.exists():
            try:
                tools = self._import_tools(tools_path, skill_name)
            except Exception as e:
                raise SkillLoadError(f"Failed to load tools for {skill_name}: {e}")

        return SkillDefinition(manifest=manifest, instructions=instructions, tools=tools)

    def _import_tools(self, tools_path: Path, skill_name: str) -> list[BaseTool]:
        """
        Dynamically import tools from a skill's tools.py file.

        Expects the module to have a get_tools() function that returns
        a list of tool instances.
        """
        # Create a unique module name to avoid conflicts
        module_name = f"nova_skill_{skill_name}_tools"

        spec = importlib.util.spec_from_file_location(module_name, tools_path)
        if spec is None or spec.loader is None:
            raise SkillLoadError(f"Cannot create module spec for {tools_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for get_tools() function
        if not hasattr(module, "get_tools"):
            raise SkillLoadError(
                f"Skill {skill_name} tools.py must define get_tools() function"
            )

        tools = module.get_tools()
        if not isinstance(tools, list):
            raise SkillLoadError(
                f"get_tools() in {skill_name} must return a list of tools"
            )

        logger.info(
            "Loaded tools from skill",
            extra={"data": {"skill": skill_name, "count": len(tools), "tools": [t.name for t in tools]}},
        )

        return tools

    async def get_skill_tools(
        self, skill_name: str, namespace: bool = True
    ) -> list[BaseTool]:
        """
        Get tools for a specific skill, optionally namespaced and wrapped for approval.

        Args:
            skill_name: Name of the skill
            namespace: If True, prefix tool names with skill_name__ to avoid conflicts

        Returns:
            List of tools ready for use by the agent
        """
        skill = await self.load_skill(skill_name)

        if namespace:
            # Namespace tools to avoid conflicts: skill_name__tool_name
            namespaced_tools = []
            for tool in skill.tools:
                # Create a new tool with namespaced name
                namespaced_tool = self._namespace_tool(skill_name, tool)
                namespaced_tools.append(namespaced_tool)
            tools = namespaced_tools
        else:
            tools = skill.tools

        # Apply approval wrappers (import here to avoid circular import)
        from tools.tool_approval_helper import wrap_tools_for_approval

        return wrap_tools_for_approval(tools)

    def _namespace_tool(self, skill_name: str, tool: BaseTool) -> BaseTool:
        """Create a copy of a tool with namespaced name."""
        from langchain_core.tools import StructuredTool

        namespaced_name = f"{skill_name}__{tool.name}"

        # Create new tool with namespaced name but same functionality
        if hasattr(tool, "coroutine") and tool.coroutine is not None:
            # Async tool
            return StructuredTool.from_function(
                func=tool.func if hasattr(tool, "func") else None,
                coroutine=tool.coroutine,
                name=namespaced_name,
                description=tool.description,
                args_schema=tool.args_schema if hasattr(tool, "args_schema") else None,
            )
        else:
            # Sync tool
            return StructuredTool.from_function(
                func=tool.func if hasattr(tool, "func") else tool._run,
                name=namespaced_name,
                description=tool.description,
                args_schema=tool.args_schema if hasattr(tool, "args_schema") else None,
            )

    def reload(self) -> None:
        """Manually reload skill registry."""
        logger.info("Reloading skill registry")
        self._scan_skills()

    def _debounced_reload(self) -> None:
        """Debounced skill registry reload."""
        with self._lock:
            if self._pending_reload:
                self._pending_reload.cancel()

            def do_reload():
                try:
                    self._scan_skills()
                    logger.info("Skill registry reloaded via file watcher")
                except Exception as e:
                    logger.error("Failed to reload skill registry", extra={"data": {"error": str(e)}})

            self._pending_reload = threading.Timer(self.debounce_seconds, do_reload)
            self._pending_reload.start()

    def start_watching(self) -> None:
        """Start watching skills directory for changes."""
        if self._observer:
            logger.warning("Skill directory watcher already started")
            return

        class SkillDirectoryHandler(FileSystemEventHandler):
            def __init__(self, manager: "SkillManager"):
                self.manager = manager

            def on_any_event(self, event):
                # Trigger reload on any change in skills directory
                if not event.is_directory or event.event_type in (
                    "created",
                    "deleted",
                    "moved",
                ):
                    logger.debug(
                        "Skills directory change detected",
                        extra={"data": {"event_type": event.event_type, "path": event.src_path}},
                    )
                    self.manager._debounced_reload()

        self._observer = Observer()
        self._observer.schedule(
            SkillDirectoryHandler(self), str(self.skills_path), recursive=True
        )
        self._observer.start()

        logger.info(
            "Started watching skills directory",
            extra={"data": {"path": str(self.skills_path)}},
        )

    def stop_watching(self) -> None:
        """Stop watching skills directory."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

            logger.info(
                "Stopped watching skills directory",
                extra={"data": {"path": str(self.skills_path)}},
            )

        # Cancel any pending reload
        with self._lock:
            if self._pending_reload:
                self._pending_reload.cancel()
                self._pending_reload = None


# Global skill manager instance (initialized by config_registry)
_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """Get the global skill manager instance."""
    global _skill_manager
    if _skill_manager is None:
        # Fallback initialization if not registered via config_registry
        from pathlib import Path

        backend_path = Path(__file__).parent.parent
        skills_path = backend_path / "skills"
        _skill_manager = SkillManager(skills_path=skills_path)
    return _skill_manager


def set_skill_manager(manager: SkillManager) -> None:
    """Set the global skill manager instance."""
    global _skill_manager
    _skill_manager = manager
