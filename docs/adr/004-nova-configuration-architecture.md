# ADR-004: Nova Configuration Architecture

**Status**: Accepted - Implemented
**Date**: Original 2025-06 (Unified from ADR-004 and ADR-008)
**Updated**: 2025-12-31

> **Implementation Notes**: Fully implemented with BaseConfigManager pattern, ConfigRegistry, 3-tier configuration system, and hot-reload support. Key files: `backend/utils/base_config_manager.py`, `backend/utils/config_registry.py`, `backend/utils/yaml_config_manager.py`, `backend/utils/markdown_config_manager.py`.

---

## Overview

This ADR defines Nova's unified configuration management architecture, combining:
1. **Unified Configuration API** - BaseConfigManager pattern for consistent config handling
2. **3-Tier Configuration System** - Clear separation of development, deployment, and user settings
3. **Hot-Reload Support** - File watching with automatic config refresh
4. **ConfigRegistry** - Centralized management of all configuration managers

## Problem Statement

Nova originally had multiple inconsistent configuration approaches:
- Different APIs for similar functionality (MCP config vs user profile vs prompts)
- Inconsistent feature sets (validation, backups, hot-reload)
- Hardcoded values scattered across files
- No clear separation between development defaults, deployment config, and user preferences

## Solution: 3-Tier Configuration System

### Tier 1: Development Defaults (Built-in)
- **Purpose**: Zero-config development setup
- **Location**: `backend/config.py` (Pydantic Settings)
- **Examples**: `LOG_LEVEL=INFO`, `HOST="0.0.0.0"`, `PORT=8000`
- **Override**: Environment variables or `.env` file

### Tier 2: Deployment Environment
Split into three sub-tiers for better organization:

**Tier 2A - Secrets (.env)**
- **Purpose**: Infrastructure secrets and deployment-specific settings
- **Location**: `.env` file (gitignored)
- **Examples**: Database URLs, API keys, service passwords

**Tier 2B - Hook Configurations**
- **Purpose**: Input source configurations
- **Location**: `configs/input_hooks.yaml`
- **Examples**: Email polling intervals, calendar sync settings
- **Hot-reload**: Yes, via ConfigRegistry

**Tier 2C - Tool Configurations**
- **Purpose**: MCP server and tool definitions
- **Location**: `configs/mcp_servers.yaml`
- **Examples**: Available MCP tools, tool endpoints
- **Hot-reload**: Yes, via ConfigRegistry

### Tier 3: User Settings (Database)
- **Purpose**: Runtime configurable user preferences
- **Location**: `user_settings` table
- **Examples**: User profile, LLM model selection, notification preferences
- **Hot-reload**: Immediate via API updates

## Unified Configuration API

### BaseConfigManager Pattern

All configuration types inherit from a common base class:

```python
# backend/utils/base_config_manager.py
class BaseConfigManager(ABC, Generic[ConfigType]):
    """Base class for all configuration managers."""

    @abstractmethod
    def _load_config_data(self) -> Dict[str, Any]:
        """Load raw configuration data from storage."""

    @abstractmethod
    def _save_config_data(self, data: Dict[str, Any]) -> None:
        """Save configuration data to storage."""

    def get_config(self, use_cache: bool = True) -> ConfigType:
        """Get typed configuration object with caching."""

    def validate(self, config: ConfigType) -> ValidationResult:
        """Validate configuration against Pydantic model."""

    def create_backup(self, description: str) -> BackupInfo:
        """Create configuration backup."""

    def restore_backup(self, backup_id: str) -> bool:
        """Restore from backup."""

    def start_watching(self) -> None:
        """Start file watching for hot-reload."""

    def stop_watching(self) -> None:
        """Stop file watching."""
```

### Implementation Classes

**YamlConfigManager** - For YAML-based configs (MCP servers, input hooks, tool permissions):
```python
class YamlConfigManager(BaseConfigManager[ConfigType]):
    """YAML-based configuration manager with Pydantic validation."""
```

**MarkdownConfigManager** - For text-based configs (system prompts):
```python
class MarkdownConfigManager(BaseConfigManager[str]):
    """Markdown-based configuration manager with template variable support."""
```

### ConfigRegistry

Centralized management of all configuration managers:

```python
# backend/utils/config_registry.py
class ConfigRegistry:
    """Global registry for all configuration managers."""

    def register(self, name: str, manager: BaseConfigManager) -> None:
        """Register a configuration manager."""

    def get_manager(self, name: str) -> BaseConfigManager:
        """Get configuration manager by name."""

    def get_config(self, name: str) -> Any:
        """Get configuration directly by name."""

    def start_all_watchers(self) -> None:
        """Start all configuration file watchers."""

    def stop_all_watchers(self) -> None:
        """Stop all configuration file watchers."""

# Global singleton
config_registry = ConfigRegistry()
```

### Registered Configurations

The following configurations are registered at startup via `initialize_standard_configs()`:

| Name | Type | File | Model |
|------|------|------|-------|
| `mcp_servers` | YamlConfigManager | `configs/mcp_servers.yaml` | MCPServersConfig |
| `system_prompt` | MarkdownConfigManager | `agent/prompts/NOVA_SYSTEM_PROMPT.md` | str |
| `input_hooks` | YamlConfigManager | `configs/input_hooks.yaml` | InputHooksConfig |
| `tool_permissions` | YamlConfigManager | `configs/tool_permissions.yaml` | ToolPermissionsConfig |

## Event System

Configuration changes publish events via Redis for real-time updates:

```python
# backend/utils/config_events.py
class ConfigUpdatedEvent(BaseModel):
    config_type: str    # "mcp_servers", "system_prompt", etc.
    operation: str      # "updated", "validated", "backed_up"
    source: str         # "config-api", "file-watcher"
    details: Dict[str, Any]
    timestamp: datetime
```

## File Structure

```
nova/
├── backend/
│   ├── config.py                    # Tier 1: Development defaults
│   ├── utils/
│   │   ├── base_config_manager.py   # Base class
│   │   ├── yaml_config_manager.py   # YAML implementation
│   │   ├── markdown_config_manager.py # Markdown implementation
│   │   ├── config_registry.py       # Central registry
│   │   └── config_events.py         # Event publishing
│   └── models/
│       ├── config.py                # MCPServersConfig, etc.
│       ├── user_settings.py         # Tier 3 database model
│       └── tool_permissions_config.py
├── configs/
│   ├── mcp_servers.yaml             # Tier 2C: Tool configs
│   ├── input_hooks.yaml             # Tier 2B: Hook configs
│   └── tool_permissions.yaml        # Tier 2C: Permission configs
└── .env                             # Tier 2A: Secrets (gitignored)
```

## Service Restart Logic

| Tier | Change Type | Restart Required |
|------|-------------|------------------|
| Tier 1 | Code defaults | Full restart |
| Tier 2A | .env secrets | Service restart |
| Tier 2B | Hook configs | Hot reload |
| Tier 2C | Tool configs | Hot reload |
| Tier 3 | User settings | Immediate |

## Benefits

1. **Consistency**: All configuration types use the same API and patterns
2. **Feature Parity**: All configs get validation, backups, hot-reload automatically
3. **Maintainability**: Single codebase for common functionality
4. **Testability**: Unified testing patterns
5. **Extensibility**: Easy to add new configuration types
6. **Security**: Clear separation of secrets from runtime config

## Related ADRs

- **ADR-011**: Uses configuration system for LLM model settings
- **ADR-012**: Adds input_hooks.yaml as Tier 2B configuration
- **ADR-013**: Adds tool_permissions.yaml for approval system

## Historical Notes

This ADR consolidates:
- Original ADR-004: Unified Configuration Management Proposal (BaseConfigManager pattern)
- Original ADR-008: 3-Tier Configuration System (development/deployment/user tiers)

Both proposals have been fully implemented and merged into this unified architecture document.
