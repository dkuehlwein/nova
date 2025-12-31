# Nova Email Integration Architecture

> **Status**: ARCHIVED - SUPERSEDED
> **Archived Date**: 2025-12-31
> **Superseded By**: [ADR-012: Multi-Input Hook Architecture Design](../012-multi-input-hook-architecture-design.md)
> **Reason**: The email-specific architecture has been generalized into the multi-input hook system. Email processing now operates as an `EmailInputHook` within the broader registry-based hook architecture.

---

*Original content preserved below for historical reference:*

---

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

### 4. Dynamic Configuration Support

**Runtime Config Checking:**
- **Fresh Config Loading**: Each task checks current configuration
- **Hot Reloading**: Changes take effect without service restart
- **Granular Controls**: Enable/disable processing, polling intervals, label filters
- **Beat Schedule Updates**: Dynamic task scheduling based on config

## Migration to Hook System

The email processing components have been preserved and wrapped by the new hook system:

**Current Location**: `backend/input_hooks/email_processing/`
- `fetcher.py` - MCP email tool interactions
- `normalizer.py` - Format standardization
- `processor.py` - Orchestration pipeline
- `task_creator.py` - Email-to-task conversion
- `interface.py` - Configurable tool mapping

**Hook Wrapper**: `backend/input_hooks/email_hook.py`
- `EmailInputHook` class extends `BaseInputHook`
- Delegates to existing email processing components
- Configuration via `configs/input_hooks.yaml`

See ADR-012 for the current architecture.
