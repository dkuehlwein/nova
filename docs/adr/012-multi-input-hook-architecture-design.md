# ADR-012: Multi-Input Hook Architecture Design

## Status
Proposed

## Context
Nova currently implements an email processing system that converts emails into tasks. We need to extend this to support multiple input sources (calendar, IMAP, Outlook, etc.) with a flexible hook system where each input can have custom polling sequences and either create new tasks or update existing ones.

This ADR documents the current email system as baseline and proposes a Registry-Based Hook Architecture for extensibility.

## Current Architecture

### Components Overview

The email system consists of 6 main components in `backend/email_processing/`:

1. **Interface Layer** (`interface.py`) - Configurable tool mapping
2. **Fetcher** (`fetcher.py`) - MCP email tool interactions  
3. **Normalizer** (`normalizer.py`) - Format standardization
4. **Processor** (`processor.py`) - Orchestration pipeline
5. **Task Creator** (`task_creator.py`) - Email-to-task conversion
6. **Background Tasks** (`tasks/email_tasks.py`) - Celery worker implementation

### Data Flow

```
User Settings → Celery Beat → Email Queue → EmailProcessor Pipeline
     ↓              ↓             ↓              ↓
Configuration   Scheduling   Background      1. Fetch (MCP)
                            Processing      2. Normalize  
                                           3. Deduplicate
                                           4. Convert to Task
                                           5. Store Record
```

### Key Design Patterns

#### 1. Configurable Interface Pattern
- Abstract email operations mapped to concrete MCP tool names
- `EMAIL_TOOL_INTERFACE` supports multiple email providers
- Parameter mapping for different tool schemas
- Location: `interface.py`

#### 2. Pipeline Architecture
- Each stage has single responsibility (Fetch → Normalize → Process → Create)
- Async processing with proper error isolation
- Individual email failures don't stop batch processing
- Location: `processor.py`

#### 3. Format Normalization
- Handles Gmail API format vs simplified MCP formats
- Unified output structure: `{id, thread_id, subject, from, to, date, content, has_attachments, labels}`
- Graceful fallbacks for missing data
- Location: `normalizer.py`

#### 4. Dynamic Configuration
- User settings control all email behavior
- Real-time configuration updates via Redis events
- Celery Beat schedule updates without restart
- Location: `celery_app.py`, user settings integration

#### 5. Robust Error Handling
- Celery retry with exponential backoff
- Dead letter queue for failed tasks
- Replay capability for manual intervention
- Structured logging throughout pipeline

### Current Limitations

1. **Single Input Type**: Only supports email sources
2. **Hardcoded Pipeline**: Email-specific processing stages
3. **Fixed Task Format**: "Read Email: {subject}" pattern
4. **Monolithic Processor**: All logic in EmailProcessor class
5. **Email-Specific Models**: ProcessedEmail table, EmailMetadata
6. **Static Interface**: EMAIL_TOOL_INTERFACE not extensible at runtime

### Configuration Points

- **User Settings**: `email_polling_enabled`, `email_polling_interval`, `email_create_tasks`, `email_max_per_fetch`
- **MCP Integration**: Dynamic tool discovery and health checks
- **Task Creation**: Timezone-aware formatting, custom descriptions
- **Deduplication**: Database-backed processed email tracking

## Decision
Document this architecture as the baseline for multi-input system design. The current email system demonstrates solid patterns for:
- Configurable tool interfaces
- Pipeline processing
- Dynamic configuration
- Error handling
- Background task management

## Consequences

### Positive
- Clear separation of concerns
- Proven patterns for external system integration
- Robust error handling and retry logic
- Dynamic configuration capabilities
- MCP abstraction layer working well

### Areas for Extension
- Need generalized input source abstraction
- Pipeline stages should be configurable per input type
- Task creation should support different formats
- Polling schedules should be per-input-source
- Database models need generalization

### Technical Debt
- Email-specific hardcoding throughout
- Limited extensibility for new input types
- Monolithic processor design
- Single queue for all email processing

This architecture provides a solid foundation for building a more flexible multi-input system while maintaining the proven patterns that work well.

## Proposed Solution: Registry-Based Hook Architecture

### Architecture Overview

We propose extending Nova's proven `ConfigRegistry` pattern to create an `InputHookRegistry` that manages different input source hooks. This leverages existing patterns while providing the flexibility needed for multiple input types.

```
┌─────────────────────────────────────────────────────────────────┐
│                      InputHookRegistry                          │
├─────────────────────────────────────────────────────────────────┤
│  register_hook(name, config) → BaseInputHook                   │
│  start_all_polling() → void                                    │
│  process_hook_items(hook_name) → ProcessingResult             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BaseInputHook (ABC)                         │
├─────────────────────────────────────────────────────────────────┤
│  + hook_name: str                                               │
│  + config: HookConfig                                          │
│  + fetch_items() → List[Dict]                                  │
│  + normalize_item(raw) → NormalizedItem                       │
│  + should_create_task(item) → bool                             │
│  + should_update_task(item, existing) → bool                  │
│  + process_items() → ProcessingResult                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────────┐
                    ▼                       ▼
        ┌───────────────────┐    ┌──────────────────────┐
        │   EmailInputHook  │    │   CalendarInputHook  │
        │   IMAPInputHook   │    │   OutlookInputHook   │
        │   SlackInputHook  │    │   JiraInputHook      │
        └───────────────────┘    └──────────────────────┘
```

### Key Design Principles

1. **Leverage Existing Patterns**: Extends `BaseConfigManager` and `ConfigRegistry` patterns
2. **Zero-Risk Migration**: Existing email system continues working unchanged
3. **Incremental Development**: Add one input type at a time
4. **Configuration-Driven**: Each hook configured via YAML with hot-reload
5. **Consistent Processing**: All hooks follow same pipeline pattern

### Hook Configuration Schema

```yaml
# configs/input_hooks.yaml
hooks:
  email:
    name: "email"
    hook_type: "email" 
    enabled: true
    polling_interval: 300
    queue_name: "email"
    create_tasks: true
    update_existing_tasks: false
    hook_settings:
      max_per_fetch: 50
      label_filter: null

  calendar:
    name: "calendar"
    hook_type: "calendar"
    enabled: true 
    polling_interval: 600
    queue_name: "calendar"
    create_tasks: true
    update_existing_tasks: true
    hook_settings:
      calendar_ids: ["primary"]
      look_ahead_days: 7
      event_types: ["meeting", "appointment"]
```

## Implementation Plan

### Phase 1: Foundation Layer (Week 1-2)

**Goal**: Build hook infrastructure without breaking existing email system

**New Components:**
```
backend/input_hooks/
├── __init__.py
├── base_hook.py           # BaseInputHook abstract class
├── hook_registry.py       # InputHookRegistry 
├── models.py              # Hook-specific Pydantic models
└── email_hook.py          # EmailInputHook wrapping existing processor
```

**Key Implementation:**
```python
class BaseInputHook(BaseConfigManager[HookConfig]):
    """Base class for all input source hooks"""
    
    @abstractmethod
    async def fetch_items(self) -> List[Dict[str, Any]]:
        """Fetch new items from input source"""
        
    @abstractmethod  
    async def normalize_item(self, raw_item: Dict) -> NormalizedItem:
        """Convert raw item to standard format"""
        
    async def process_items(self) -> ProcessingResult:
        """Common processing pipeline for all hooks"""
        items = await self.fetch_items()
        results = ProcessingResult()
        
        for raw_item in items:
            normalized = await self.normalize_item(raw_item)
            
            if await self.should_create_task(normalized):
                task_id = await self._create_task_from_item(normalized)
                results.tasks_created += 1
                
            elif existing_task := await self._find_existing_task(normalized):
                if await self.should_update_task(normalized, existing_task):
                    await self._update_task_from_item(normalized, existing_task)
                    results.tasks_updated += 1
                    
        return results
```

### Phase 2: Email System Wrapper (Week 3)

**Goal**: Wrap existing email components without modification

```python
class EmailInputHook(BaseInputHook):
    """Email hook wrapping existing EmailProcessor functionality"""
    
    def __init__(self, hook_name: str, config: EmailHookConfig):
        super().__init__(hook_name, config)
        # Reuse existing components - zero rewrite!
        self.email_processor = EmailProcessor()
        self.normalizer = EmailNormalizer()
        self.task_creator = EmailTaskCreator()
    
    async def fetch_items(self) -> List[Dict[str, Any]]:
        """Delegate to existing EmailProcessor.fetch_new_emails()"""
        return await self.email_processor.fetch_new_emails()
    
    async def normalize_item(self, raw_item: Dict) -> NormalizedItem:
        """Use existing EmailNormalizer"""
        email_dict = self.normalizer.normalize(raw_item)
        return NormalizedItem(
            source_type="email",
            source_id=email_dict["id"],
            content=email_dict,
            metadata=self._create_email_metadata(email_dict)
        )
```

**Files Unchanged:**
- ✅ `email_processing/fetcher.py` 
- ✅ `email_processing/normalizer.py`
- ✅ `email_processing/task_creator.py` 
- ✅ `email_processing/processor.py`

### Phase 3: Celery Integration Enhancement

**Enhanced Generic Hook Tasks:**
```python
# tasks/hook_tasks.py (NEW FILE)
@celery_app.task(
    bind=True,
    name="tasks.hook_tasks.process_hook_items",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60}
)
def process_hook_items(self, hook_name: str) -> Dict[str, Any]:
    """Generic task to process items from any hook type"""
    hook = input_hook_registry.get_manager(hook_name)
    result = asyncio.run(hook.process_items())
    return result.dict()
```

**Dynamic Celery Configuration:**
```python
# celery_app.py - Enhanced beat scheduling
def update_beat_schedule():
    """Update beat schedule for all enabled hooks"""
    schedule = {}
    
    for hook_name in input_hook_registry.list_configs():
        hook = input_hook_registry.get_manager(hook_name)
        
        if hook.config.enabled:
            schedule[f"process-{hook_name}"] = {
                "task": "tasks.hook_tasks.process_hook_items",
                "schedule": hook.config.polling_interval,
                "args": [hook_name],
                "options": {"queue": hook.config.queue_name or "hooks"}
            }
    
    celery_app.conf.beat_schedule = schedule
```

### Phase 4: Database Schema Evolution

**Backward Compatible Approach:**
```sql
-- New generalized table for all hooks
CREATE TABLE processed_items (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR NOT NULL,  -- 'email', 'calendar', 'slack'
    source_id VARCHAR NOT NULL,    -- Original item ID from source
    source_metadata JSONB,         -- Flexible metadata storage
    task_id VARCHAR,               -- Associated Nova task ID
    processed_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_type, source_id)
);

-- Keep existing table for backward compatibility
-- processed_emails table stays unchanged during migration
```

### Phase 5: Migration Strategy

**Zero-Downtime Migration:**

1. **Dual-Mode Operation**: Both systems run simultaneously
   ```python
   @celery_app.task(name="tasks.email_tasks.fetch_emails")
   def fetch_emails(self):
       if should_use_hook_system():
           return delegate_to_hook_system("email")
       else:
           return asyncio.run(_fetch_emails_async_legacy(task_id))
   ```

2. **Feature Flag Control**: Gradual switchover via user settings
   ```python
   class UserSettings(BaseModel):
       use_hook_system: bool = False  # Feature flag
   ```

3. **Emergency Rollback**: Immediate fallback to legacy system if needed

### Phase 6: New Input Types (Week 5-8)

**Calendar Hook Example:**
```python
class CalendarInputHook(BaseInputHook):
    async def fetch_items(self) -> List[Dict[str, Any]]:
        """Fetch calendar events via MCP tools"""
        # Use existing MCP calendar integration
        
    async def normalize_item(self, raw_item: Dict) -> NormalizedItem:
        """Convert calendar event to standard format"""
        return NormalizedItem(
            source_type="calendar",
            source_id=raw_item["id"],
            content={
                "title": raw_item["summary"],
                "description": raw_item["description"],
                "start_time": raw_item["start"]["dateTime"],
                "end_time": raw_item["end"]["dateTime"],
                "attendees": raw_item.get("attendees", [])
            }
        )
    
    async def should_update_task(self, item: NormalizedItem, existing_task_id: str) -> bool:
        """Calendar events can update existing tasks"""
        return True  # Support task updates for calendar changes
```

## Decision

Implement the Registry-Based Hook Architecture as the recommended solution for Nova's multi-input system extension.

**Rationale:**
1. **Proven Pattern**: Directly extends Nova's successful `ConfigRegistry` + `BaseConfigManager` patterns
2. **Fast Implementation**: Can port existing email system with minimal changes  
3. **Incremental Growth**: Easy to add new input types one at a time
4. **Consistent Architecture**: Maintains Nova's existing design philosophy
5. **Low Risk**: Zero-downtime migration with emergency rollback capability

## Consequences

### Positive
- **Rapid Development**: Leverage existing, proven patterns
- **Zero Risk Migration**: Email system continues working unchanged
- **Extensible Design**: Easy to add calendar, IMAP, Outlook, Slack hooks
- **Consistent Processing**: All input types follow same patterns
- **Configuration Flexibility**: Per-hook settings with hot-reload
- **Enhanced Capabilities**: Task creation AND updating support
- **Better Monitoring**: Unified logging and error handling

### Implementation Benefits
- **Minimal Code Changes**: Wraps existing email components
- **Familiar Debugging**: Same patterns developers already know
- **Incremental Testing**: Add and test one hook at a time
- **Future-Proof**: Registry pattern scales to many input types

### Technical Improvements
- **Generalized Database**: `processed_items` table supports all input types
- **Dynamic Celery Scheduling**: Per-hook polling intervals and queues
- **Enhanced Error Handling**: Hook-specific retry and failure strategies
- **Cross-Hook Capabilities**: Task updates, deduplication, notifications

This architecture provides Nova with a scalable, maintainable foundation for supporting unlimited input sources while preserving all existing functionality and maintaining development velocity.

---
### Senior Dev Review Comments

This is an excellent ADR. It not only documents the current system accurately but also proposes a robust, extensible, and well-thought-out architecture for the future. The breakdown of the problem, the proposed solution using a registry pattern, and the phased, low-risk migration plan are all hallmarks of a strong architectural proposal.

Regarding the question: **"Can this system send me a prep document 15 minutes before a meeting begins?"**

1.  **Current System:** No. The existing email-only system is based on periodic polling and is not designed for time-based triggers relative to an event like a meeting. It reacts to emails it finds in the inbox, it doesn't act on future scheduled events.

2.  **Proposed System:** Yes, absolutely. The proposed `Registry-Based Hook Architecture` is the perfect foundation for this functionality. The `CalendarInputHook` is the key.

    - The proposed `CalendarInputHook` would fetch upcoming calendar events.
    - When an event is fetched, the hook would have access to its `start_time`.
    - Instead of creating a task immediately, the hook's processing logic could be adapted to schedule a one-off, delayed task. For example, it could call a Celery task with an `eta` (estimated time of arrival) set to `meeting.start_time - 15 minutes`.

    This would look something like this inside the `CalendarInputHook`:

    ```python
    # Inside process_items() or a similar method
    from datetime import timedelta

    for event in upcoming_events:
        prep_time = event.start_time - timedelta(minutes=15)
        # Ensure we don't schedule for past events
        if prep_time > datetime.utcnow():
            # Schedule the prep task to run at the calculated time
            generate_prep_document.apply_async(
                args=[event.id],
                eta=prep_time
            )
    ```

This ADR is a great example of looking beyond the immediate problem to design a system that can grow and accommodate new features gracefully. The proposed architecture is approved. It's a solid plan for moving Nova's input processing capabilities forward.
