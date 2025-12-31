# ADR-007: User Context Design

**Status**: Accepted - Implemented
**Date**: 2025-06
**Updated**: 2025-12-31

> **Implementation Notes**: User profile stored in database (`user_settings` table) rather than YAML. Fields: `full_name`, `email`, `timezone`, `notes`. Integrated into system prompt via template variables.

---

## Context

Nova lacked an authoritative profile for the user. Without basic facts (name, email, timezone), the agent cannot:
- Interpret references like "me", "my email", or "9 AM my time"
- Match memory entries indexed by name/email
- Personalize responses appropriately

## Decision

Implement user context with:
- **Database storage** in `user_settings` table (Tier 3 per ADR-004)
- **Required fields**: full name, email, timezone
- **Optional field**: free-text notes for additional context
- **System prompt integration** via template variables

## Architecture

```
User Settings (Database)
        │
        ▼
System Prompt Template
        │
        ▼
Agent Context
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| UserSettings Model | `backend/models/user_settings.py` | Database model |
| Settings Endpoints | `backend/api/settings_endpoints.py` | CRUD API |
| Prompt Loader | `backend/utils/prompt_loader.py` | Template rendering |
| Settings UI | `frontend/src/app/settings/page.tsx` | User settings form |

## User Profile Fields

| Field | Required | Purpose |
|-------|----------|---------|
| `full_name` | Yes | Identity, memory matching |
| `email` | Yes | Email operations, "my email" resolution |
| `timezone` | Yes | Time interpretation, scheduling |
| `notes` | No | Custom instructions, preferences |

## System Prompt Integration

Template variables inject user context:

```markdown
**User Context:**
- Name: {{user.full_name}}
- Email: {{user.email}}
- Timezone: {{user.timezone}}
{{user.notes}}
```

## Runtime Usage

The agent uses user context for:
1. **Pronoun resolution**: "my email" → user's email address
2. **Time conversion**: "9 AM" → user's timezone
3. **Memory matching**: Link stored information to user identity

## Consequences

### Positive

- Accurate interpretation of user references
- Personalized agent responses
- Memory system can match user by name/email
- Consistent timezone handling

### Negative

- PII stored in database (acceptable for personal agent)
- Additional database queries for prompt rendering

### Design Notes

- Originally proposed as YAML file, moved to database for:
  - Easier runtime updates via UI
  - Consistency with other user settings
  - ADR-004 Tier 3 compliance

## Related ADRs

- **ADR-004**: Configuration tiers (user settings in Tier 3)
- **ADR-003**: Memory system (uses user context for matching)

---
*Last reviewed: 2025-12-31*
