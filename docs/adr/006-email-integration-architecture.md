# Nova Email Integration Architecture

**Status**: SUPERSEDED by [ADR-012: Multi-Input Hook Architecture Design](./012-multi-input-hook-architecture-design.md)

## Overview

Nova will integrate email processing capabilities to automatically create tasks from incoming emails. This document outlines the architecture using Celery for robust background job processing with comprehensive error handling and deduplication.

**Note**: This ADR has been superseded by ADR-012's Registry-Based Hook Architecture. The email integration is now implemented as an `EmailInputHook` within the broader multi-input system. The core patterns and components described here remain valid but are now part of the generalized hook system.

## Architecture Components

### 1. Background Job Processing (Celery)

**Why Celery?**
- Battle-tested scheduling with Celery Beat
- Built-in retry policies and error handling
- Uses existing Redis infrastructure
- Separation of concerns (background jobs vs web services)
- Mature monitoring and scaling capabilities

**Components:**
- **Celery Worker**: Processes email fetching jobs
- **Celery Beat**: Schedules periodic email checks
- **Redis**: Message broker (already exists)

### 2. Email Processing Flow

```mermaid
graph TD
    A[Celery Beat Scheduler] -->|Every N minutes| B[fetch_emails Task]
    B --> C[Check Dynamic Config]
    C -->|Enabled| D[MCP Google Workspace Client]
    C -->|Disabled| E[Skip Processing]
    D --> F[Fetch New Emails]
    F --> G[Database Deduplication Check]
    G --> H[Process New Emails Only]
    H --> I[Create Task: "Read Email: Subject"]
    I --> J[Mark Email as Processed in DB]
    J --> K[Publish Redis Event]
    K --> L[Frontend Updates]
    
    B -->|Max Retries Exceeded| M[Dead Letter Queue]
    M --> N[Store Failure Info]
    M --> O[Alert for Manual Review]
```

### 3. Robust Deduplication Strategy

**Database-Based Tracking:**
- **ProcessedEmail Table**: Stores email_id, thread_id, subject, sender, processed_at, task_id
- **Unique Constraint**: On email_id to prevent duplicates
- **Indexed Lookups**: Fast queries to check processed status
- **Audit Trail**: Full history of processed emails with task relationships

**Benefits:**
- Survives service restarts (persistent deduplication)
- Fast database lookups with proper indexing
- Comprehensive audit trail for debugging
- Handles edge cases like task deletion

### 4. Dynamic Configuration Support

**Runtime Config Checking:**
- **Fresh Config Loading**: Each task checks current configuration
- **Hot Reloading**: Changes take effect without service restart
- **Granular Controls**: Enable/disable processing, polling intervals, label filters
- **Beat Schedule Updates**: Dynamic task scheduling based on config

**Configuration Options (Legacy - now in ADR-012's hook system):**
- Polling interval (default: 5 minutes) → `configs/input_hooks.yaml:hooks.email.polling_interval`
- Gmail label filter (default: "INBOX") → `configs/input_hooks.yaml:hooks.email.hook_settings.label_filter`
- Enable/disable auto-processing toggle → `configs/input_hooks.yaml:hooks.email.enabled`
- Maximum emails per fetch → `configs/input_hooks.yaml:hooks.email.hook_settings.max_per_fetch`
- Task creation toggle → `configs/input_hooks.yaml:hooks.email.create_tasks`

### 5. Dead Letter Queue Handling

**Comprehensive Error Recovery:**
- **Exponential Backoff**: 3 retries with increasing delays (60s, 120s, 300s)
- **Failure Tracking**: Store failed task information in Redis
- **Monitoring Events**: Publish dead letter queue events for alerting
- **Manual Replay**: API endpoints to retry failed tasks
- **Health Monitoring**: Track failed tasks over time

**Error Scenarios Covered:**
- Gmail API downtime
- MCP server connection failures
- Database connectivity issues
- Individual email processing errors

## Technical Implementation

### 1. Core Components (Improved Organization)

```
backend/
├── celery_app.py              # Enhanced Celery configuration with dynamic scheduling
├── tasks/                     # Core email processing components
│   ├── __init__.py
│   ├── email_tasks.py         # Celery tasks with robust error handling
│   └── email_processor.py     # Core email processing logic (moved from utils)
├── models/
│   ├── email.py               # Email-related Pydantic models
│   └── models.py              # SQLAlchemy models (includes ProcessedEmail)
├── database/
│   └── migration_001_add_processed_emails.sql  # Database migration
└── tests/integration/
    └── test_email_integration.py  # Comprehensive integration tests
```

### 2. Database Schema

**ProcessedEmail Table (Legacy - replaced by ADR-012's processed_items):**
```sql
-- Legacy table - replaced by processed_items in ADR-012
CREATE TABLE processed_emails (
    id UUID PRIMARY KEY,
    email_id VARCHAR(255) NOT NULL UNIQUE,  -- Gmail message ID
    thread_id VARCHAR(255) NOT NULL,        -- Gmail thread ID
    subject VARCHAR(1000) NOT NULL,         -- For auditing
    sender VARCHAR(500) NOT NULL,           -- For auditing
    processed_at TIMESTAMP DEFAULT NOW(),   -- Processing timestamp
    task_id UUID REFERENCES tasks(id)       -- Created task (nullable)
);

-- New generalized table from ADR-012
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
```

**Indexes for Performance:**
- `idx_processed_emails_email_id` (unique lookup)
- `idx_processed_emails_thread_id` (thread grouping)
- `idx_processed_emails_processed_at` (time-based queries)

### 3. Enhanced Celery Configuration

**Dynamic Scheduling:**
- Beat schedule updates based on configuration changes
- Worker signal handlers for lifecycle management
- Custom tasks for schedule updates and monitoring

**Retry Logic:**
- Automatic retries with exponential backoff
- Maximum 3 retries with jitter to prevent thundering herd
- Comprehensive failure logging and event publishing

**Dead Letter Queue Management:**
- Failed task information storage
- Monitoring tasks for health checks
- Manual replay capabilities

### 4. Error Handling & Monitoring

**Multi-Level Error Handling:**
1. **Individual Email Errors**: Log and continue processing other emails
2. **Batch Processing Errors**: Retry entire batch with backoff
3. **Dead Letter Queue**: Store failure info for manual review
4. **Health Monitoring**: Track failure rates and alert thresholds

**Monitoring Features:**
- Flower dashboard for Celery task monitoring (port 5555)
- Redis events for real-time frontend updates
- Structured logging for debugging
- Health check endpoints for system status

## Work Packages Status

### ✅ Completed Work Packages

### WP1: Core Celery Infrastructure ✅
- ✅ Created `backend/celery_app.py` with enhanced configuration
- ✅ Added Celery dependencies (`celery[redis]`, `flower`) to `pyproject.toml`
- ✅ Updated `docker-compose.yml` with celery-worker, celery-beat, and flower services
- ✅ Fixed backend Dockerfile to support Celery commands
- ✅ Added health checks and monitoring

### WP2: Email Processing Tasks ✅
- ✅ Created `backend/tasks/email_tasks.py` with robust error handling
- ✅ Created `backend/tasks/email_processor.py` (moved from utils for better organization)
- ✅ Created `backend/models/email.py` with comprehensive models
- ✅ Added `ProcessedEmail` SQLAlchemy model for deduplication
- ✅ Integrated with existing MCP Google Workspace client
- ✅ Added Redis event publishing and dead letter queue handling

### WP2.5: Database Migration & Testing ✅
- ✅ Created `backend/database/migration_001_add_processed_emails.sql`
- ✅ Created comprehensive integration tests in `tests/integration/test_email_integration.py`
- ✅ Added deduplication testing and error handling tests

## 🔜 Remaining Work Packages

- **WP3**: Configuration Management (email settings in Nova config)
- **WP4**: Frontend Integration (settings page)
- **WP5**: System Prompt Enhancement
- **WP6**: Testing & Monitoring (expanded)
- **WP7**: Documentation & Deployment

## Security Considerations

1. **Email Content**: Stored securely in database with proper access controls
2. **Credentials**: Google Workspace credentials via MCP server configuration
3. **Rate Limiting**: Respects Gmail API rate limits with retry backoff
4. **Privacy**: Email content sensitivity considered in structured logging
5. **Access Control**: Proper database permissions and API security

## Key Improvements Made

### 1. ✅ Email Deduplication
- **Database-backed tracking** instead of in-memory sets
- **Unique constraints** on email_id prevent duplicates
- **Indexed lookups** for fast deduplication checks
- **Audit trail** with full email metadata

### 2. ✅ Dynamic Configuration  
- **Runtime config checking** in each task execution
- **Hot-reload support** without service restarts
- **Dynamic beat scheduling** based on current settings
- **Granular enable/disable controls**

### 3. ✅ Dead Letter Queue Handling
- **Exponential backoff retry** with max 3 attempts
- **Failure information storage** for manual review
- **Monitoring events** for alerting systems
- **Manual replay capabilities** via API endpoints
- **Health tracking** over time

### 4. ✅ Better Code Organization
- **Moved email processor** from utils to tasks (core component)
- **Comprehensive error handling** at all levels
- **Integration tests** covering full workflow
- **Clear separation of concerns** between components

## Migration Strategy

**Legacy Migration Path (replaced by ADR-012's approach):**
1. **Phase 1**: Deploy enhanced Celery infrastructure ✅
2. **Phase 2**: Run database migration for ProcessedEmail table
3. **Phase 3**: Enable email processing with configuration management (WP3)
4. **Phase 4**: Add frontend integration and monitoring (WP4-6)

**New Migration Strategy (per ADR-012):**
1. **Phase 1**: Foundation Layer - Build InputHookRegistry and BaseInputHook
2. **Phase 2**: Email System Wrapper - Create EmailInputHook wrapping existing components
3. **Phase 3**: Celery Integration Enhancement - Generic hook tasks
4. **Phase 4**: Database Schema Evolution - processed_items table
5. **Phase 5**: Zero-Downtime Migration - Dual-mode operation with feature flags
6. **Phase 6**: New Input Types - Calendar, IMAP, etc.

This architecture provides a solid, production-ready foundation for email integration while addressing all major concerns around deduplication, dynamic configuration, and error handling. The approach has been generalized in ADR-012 to support multiple input sources through the Registry-Based Hook Architecture. 