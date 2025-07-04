# Unified Configuration Management Proposal

## Problem Statement

Nova currently has three different approaches for configuration management:

1. **MCP Config** (`utils/config_loader.py`): Uses `ConfigLoader` class with validation, backups, hot-reload, singleton pattern
2. **User Profile** (`utils/config_loader.py`): Uses standalone functions, no hot-reload, no validation, no backups
3. **Prompt Config** (`utils/prompt_loader.py`): Uses `PromptLoader` class with hot-reload, different backup pattern

This inconsistency creates:
- Different APIs for similar functionality
- Inconsistent error handling and logging
- Varying feature sets (validation, backups, hot-reload)
- Different event publishing patterns
- Code duplication and maintenance overhead

## Proposed Solution: Unified Configuration Architecture

### 1. Base Configuration Manager

Create a unified base class that all configuration types inherit from:

```python
# utils/base_config_manager.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar, Generic
from pydantic import BaseModel
from pathlib import Path

ConfigType = TypeVar('ConfigType', bound=BaseModel)

class BaseConfigManager(ABC, Generic[ConfigType]):
    """Base class for all configuration managers."""
    
    def __init__(self, config_path: Path, config_model: Type[ConfigType]):
        self.config_path = config_path
        self.config_model = config_model
        self._setup_common_features()
    
    @abstractmethod
    def _load_config_data(self) -> Dict[str, Any]:
        """Load raw configuration data from storage."""
        pass
    
    @abstractmethod
    def _save_config_data(self, data: Dict[str, Any]) -> None:
        """Save configuration data to storage."""
        pass
    
    def get_config(self) -> ConfigType:
        """Get typed configuration object."""
        pass
    
    def save_config(self, config: ConfigType) -> None:
        """Save typed configuration object."""
        pass
    
    def validate_config(self, config: Optional[ConfigType] = None) -> ValidationResult:
        """Validate configuration."""
        pass
    
    def create_backup(self, description: str = "Manual backup") -> BackupInfo:
        """Create configuration backup."""
        pass
    
    def restore_backup(self, backup_id: str) -> bool:
        """Restore from backup."""
        pass
    
    def start_watching(self) -> None:
        """Start hot-reload watching."""
        pass
    
    def stop_watching(self) -> None:
        """Stop hot-reload watching."""
        pass
```

### 2. Unified Configuration Types

**YAML Configuration Manager:**
```python
# utils/yaml_config_manager.py
class YamlConfigManager(BaseConfigManager[ConfigType]):
    """YAML-based configuration manager."""
    
    def _load_config_data(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _save_config_data(self, data: Dict[str, Any]) -> None:
        with open(self.config_path, 'w') as f:
            yaml.safe_dump(data, f, default_flow_style=False)
```

**Markdown Configuration Manager:**
```python
# utils/markdown_config_manager.py  
class MarkdownConfigManager(BaseConfigManager[str]):
    """Markdown-based configuration manager (for prompts)."""
    
    def _load_config_data(self) -> str:
        with open(self.config_path, 'r') as f:
            return f.read()
    
    def _save_config_data(self, data: str) -> None:
        with open(self.config_path, 'w') as f:
            f.write(data)
```

### 3. Standardized Event Publishing

**Common Event Pattern:**
```python
# models/config_events.py
class ConfigUpdatedEvent(BaseModel):
    config_type: str  # "mcp_servers", "user_profile", "system_prompt"
    operation: str    # "updated", "validated", "backed_up", "restored"
    source: str       # "config-api", "file-watcher", "user-action"
    details: Dict[str, Any]
    timestamp: datetime
```

**Unified Event Publisher:**
```python
# utils/config_manager.py
async def publish_config_event(
    config_type: str, 
    operation: str, 
    details: Dict[str, Any], 
    source: str = "config-api"
) -> None:
    """Publish standardized configuration event."""
    event = ConfigUpdatedEvent(
        config_type=config_type,
        operation=operation,
        source=source,
        details=details,
        timestamp=datetime.now()
    )
    await publish(event)
```

### 4. Standardized API Endpoints

**Unified Endpoint Pattern:**
```python
# api/config_endpoints.py
def create_config_router(config_manager: BaseConfigManager, config_type: str):
    """Create standardized config router for any config type."""
    router = APIRouter(prefix=f"/api/config/{config_type}")
    
    @router.get("/")
    async def get_config():
        return config_manager.get_config()
    
    @router.put("/")
    async def update_config(config: config_manager.config_model):
        result = config_manager.save_config(config)
        await publish_config_event(config_type, "updated", result.details)
        return result
    
    @router.post("/validate")
    async def validate_config(config: Optional[config_manager.config_model] = None):
        result = config_manager.validate_config(config)
        await publish_config_event(config_type, "validated", result.details)
        return result
    
    @router.post("/backups")
    async def create_backup(description: str = "Manual backup"):
        result = config_manager.create_backup(description)
        await publish_config_event(config_type, "backed_up", result.details)
        return result
    
    return router
```

### 5. Implementation Migration Plan

**Phase 1: Base Infrastructure**
- [ ] Create `BaseConfigManager` abstract class
- [ ] Create `YamlConfigManager` and `MarkdownConfigManager` implementations
- [ ] Create unified event models and publisher
- [ ] Create standardized endpoint generator

**Phase 2: MCP Config Migration**
- [ ] Refactor `ConfigLoader` to inherit from `YamlConfigManager`
- [ ] Update MCP endpoints to use unified pattern
- [ ] Ensure backward compatibility
- [ ] Update tests

**Phase 3: User Profile Migration**
- [ ] Create `UserProfileManager` class using `YamlConfigManager`
- [ ] Add hot-reload capabilities to user profile
- [ ] Add validation and backup features
- [ ] Update API endpoints to use unified pattern
- [ ] Add user profile file watching

**Phase 4: Prompt Config Migration**
- [ ] Refactor `PromptLoader` to inherit from `MarkdownConfigManager`
- [ ] Standardize backup functionality
- [ ] Update prompt endpoints to use unified pattern
- [ ] Fix template rendering to use proper formatting

**Phase 5: Cleanup and Testing**
- [ ] Remove old standalone functions
- [ ] Update all imports and references
- [ ] Add comprehensive integration tests
- [ ] Update documentation

## Benefits

1. **Consistency**: All configuration types use the same API and patterns
2. **Feature Parity**: All configs get validation, backups, hot-reload automatically
3. **Maintainability**: Single codebase for common functionality
4. **Testability**: Unified testing patterns and mocks
5. **Extensibility**: Easy to add new configuration types

## Implementation Details

### Template Rendering Fix (Immediate)

The prompt loader's template rendering should be fixed immediately:

```python
# Current (bad):
prompt = prompt_template.replace("{{user_full_name}}", user_profile.full_name)
prompt = prompt.replace("{{user_email}}", user_profile.email)
# ... more replace calls

# Proposed (good):
from string import Template

template = Template(prompt_template)
prompt = template.safe_substitute(
    user_full_name=user_profile.full_name,
    user_email=user_profile.email,
    user_timezone=user_profile.timezone,
    current_time_user_tz=current_time_str,
    user_notes_section=user_notes_section
)
```

### Configuration Registry

Create a global registry for all configuration managers:

```python
# utils/config_registry.py
class ConfigRegistry:
    """Global registry for all configuration managers."""
    
    def __init__(self):
        self._managers: Dict[str, BaseConfigManager] = {}
    
    def register(self, config_type: str, manager: BaseConfigManager):
        """Register a configuration manager."""
        self._managers[config_type] = manager
    
    def get_manager(self, config_type: str) -> BaseConfigManager:
        """Get configuration manager by type."""
        return self._managers[config_type]
    
    def start_all_watchers(self):
        """Start all configuration watchers."""
        for manager in self._managers.values():
            manager.start_watching()

# Global registry instance
config_registry = ConfigRegistry()
```

This proposal provides a path to unified, consistent configuration management across Nova while maintaining all existing functionality and adding missing features where needed. 