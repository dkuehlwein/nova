# ADR-010: Unified System Health Monitoring

**Status**: Accepted - Implemented
**Date**: 2025-07-14
**Updated**: 2025-12-31

> **Implementation Notes**: HealthMonitorService in `backend/services/health_monitor.py`. SystemHealthStatus model in `backend/models/system_health.py`. API at `/api/system/system-health`. Background monitoring with 180s check interval and 300s cache TTL.

---

## Context

Nova had multiple disconnected status monitoring approaches causing:
- **False green status**: Navbar showed green when services were failing
- **Inconsistent data**: 4 separate status systems with different results
- **Code duplication**: Status icons, colors, and logic repeated across components
- **Performance issues**: Frequent external API calls for validation

## Decision

Implement a **Unified System Health Monitoring Architecture** with:
- **Cached status monitoring** via background service
- **Binary criticality logic** (core vs infrastructure vs external)
- **Single API endpoint** for all status data
- **Optimized API key validation** (startup/change/manual only)

## Architecture

```
┌─────────────────────────────────────────┐
│         HealthMonitorService            │
│  (Background monitoring every 180s)     │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         SystemHealthStatus              │
│  (Database cache, 300s TTL)             │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│    /api/system/system-health            │
│  (Unified status for all consumers)     │
└─────────────────────────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| HealthMonitorService | `backend/services/health_monitor.py` | Background health checks |
| SystemHealthStatus | `backend/models/system_health.py` | Cached status model |
| System Endpoints | `backend/api/system_endpoints.py` | Status API |

## Service Categorization

### Core Services (any down = critical)
- Chat Agent (`localhost:8000/health`)
- Core Agent (`localhost:8001/health`)

### Essential Infrastructure (any down = critical)
- Database (connection pool check)
- Redis (pub/sub check)
- llama.cpp (`localhost:8080/health`)
- LiteLLM (`localhost:4000/health/readiness`)
- Neo4j (graph query check)

### External Services (any down = degraded)
- MCP servers (dynamic from config)
- API keys (Google)
- Observability (Phoenix)

## Status Calculation

```
if (any core service down) → "critical"
if (any essential infrastructure down) → "critical"
if (any external service down) → "degraded"
else → "operational"
```

## API Response

```json
{
  "overall_status": "operational|degraded|critical",
  "overall_health_percentage": 95,
  "last_updated": "2025-12-31T10:00:00Z",
  "cached": true,
  "core_services": [...],
  "infrastructure_services": [...],
  "external_services": [...],
  "summary": {
    "total_services": 10,
    "healthy_services": 9,
    "top_issues": ["mcp_gmail: connection timeout"]
  }
}
```

## API Key Refresh Strategy

API keys are NOT checked on every request. Refresh triggers:
- **Startup**: Check if never validated
- **API key change**: Immediate validation
- **Manual refresh**: User-triggered button

This saves API tokens and reduces latency.

## Consequences

### Positive

- Accurate navbar status (no more false greens)
- 95% fewer external API calls
- Consistent 200ms response times
- Single source of truth for all status displays
- Historical data for troubleshooting

### Negative

- Database migration required for health status table
- Cached status may briefly show stale data during transitions
- Background service adds slight system overhead

### Risks

- **Background monitoring impact**: Tuned intervals (180s) minimize overhead
- **Cache staleness**: 300s TTL balances freshness vs performance

## Related ADRs

- **ADR-004**: Configuration management (health check settings)
- **ADR-005**: Real-time infrastructure (WebSocket for status updates)

---
*Last reviewed: 2025-12-31*
