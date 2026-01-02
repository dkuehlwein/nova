# Nova Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records documenting significant technical decisions made during Nova's development.

## ADR Index

### Active ADRs

| ADR | Title | Status | Description |
|-----|-------|--------|-------------|
| [002](002-human-in-the-loop-architecture.md) | Human-in-the-Loop Architecture | Partial | Bidirectional human communication via `ask_user` tool |
| [003](003-graphiti_integration_architecture_v6.md) | Graphiti Integration | Implemented | Knowledge graph memory system with Neo4j |
| [004](004-nova-configuration-architecture.md) | Configuration Architecture | Implemented | 3-tier config system with BaseConfigManager |
| [005](005-settings_realization_work_packages.md) | Real-time Infrastructure | Implemented | Hot-reload, Redis pub/sub, WebSocket |
| [007](007-user_context_design.md) | User Context Design | Implemented | User profile in system prompt |
| [010](010-unified-system-health-monitoring.md) | System Health Monitoring | Implemented | Cached health monitoring with criticality logic |
| [011](011-simplified-model-management-system.md) | LiteLLM-First Architecture | Implemented | Unified LLM routing through LiteLLM |
| [012](012-multi-input-hook-architecture-design.md) | Multi-Input Hook Architecture | Implemented | Registry-based hooks for email, calendar |
| [013](013-human-oversight-tool-approval-system.md) | Tool Approval System | Implemented | Human oversight for tool execution |
| [014](014-pluggable-skills-system.md) | Pluggable Skills System | Proposed | Dynamic workflow/skill loading system |

### Draft ADRs

| ADR | Title | Description |
|-----|-------|-------------|
| [DRAFT-hierarchical-agent](DRAFT-hierarchical-agent-architecture.md) | Hierarchical Agent | Supervisor/Worker pattern for complex tasks |
| [DRAFT-deepeval](DRAFT-deepeval-integration-for-llm-testing.md) | DeepEval Integration | LLM testing and evaluation framework |

### Archived ADRs

| ADR | Original Title | Reason |
|-----|---------------|--------|
| [001](archive/001-high-level-outline.md) | High-Level Outline | Outdated, see CLAUDE.md |
| [006](archive/006-email-integration-architecture.md) | Email Integration | Superseded by ADR-012 |
| [008](archive/008-configuration-management-proposal.md) | Configuration Management | Merged into ADR-004 |
| [009](archive/009-hybrid-llm-architecture.md) | Hybrid LLM Architecture | Superseded by ADR-011 |

## ADR Format

All ADRs follow this consistent format:

```markdown
# ADR-NNN: Title

**Status**: Proposed | Accepted | Implemented | Superseded
**Date**: YYYY-MM-DD
**Updated**: YYYY-MM-DD
**Supersedes**: ADR-XXX (if applicable)

> **Implementation Notes**: Brief note on current state with key file paths.

---

## Context
What problem are we solving? (2-4 paragraphs)

## Decision
What did we decide? High-level approach. (2-4 paragraphs)

## Architecture
Brief description with simple ASCII diagrams.
Reference file paths, don't include full code.

### Key Components
| Component | Location | Purpose |
|-----------|----------|---------|

## Consequences

### Positive
- Benefits

### Negative
- Trade-offs

### Risks (if applicable)
- Key risks and mitigations

## Related ADRs
- Links to related decisions

---
*Last reviewed: YYYY-MM-DD*
```

### Guidelines

- **Target length**: 100-200 lines (under 10KB)
- **No full code**: Reference file paths instead
- **No emojis**: Professional technical documentation
- **No work packages**: Use separate project management tools
- **No implementation diaries**: Status in header note only
- **Diagrams**: Simple ASCII, max 15-20 lines

## Status Definitions

- **Proposed**: Under consideration
- **Accepted**: Approved, ready for implementation
- **Implemented**: Fully implemented
- **Partial**: Partially implemented
- **Superseded**: Replaced by newer ADR

## Creating New ADRs

1. Use the next available number (currently 015)
2. Naming: `NNN-short-descriptive-name.md`
3. For drafts: `DRAFT-descriptive-name.md`
4. Follow the format above

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Project overview
- [Backend Code](../../backend/) - Implementation
- [Frontend Code](../../frontend/) - UI

---
*Last updated: 2025-12-31*
