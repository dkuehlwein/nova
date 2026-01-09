# ADR-017: Phoenix Observability Migration

## Status
Accepted

## Context

Nova previously used Langsmith (cloud-based) for LLM observability and tracing. However, Nova aims to be fully on-premises, and Langsmith requires external API calls to `api.smith.langchain.com`.

We needed a self-hosted alternative that provides:
- LLM trace visualization
- Token usage and latency metrics
- Agent execution graphs
- No external API calls

### Options Considered

| Solution | Containers | RAM Required | Database | License |
|----------|------------|--------------|----------|---------|
| Langfuse v3 | 4 (web, worker, clickhouse, minio) | ~16GB | PostgreSQL + ClickHouse | MIT |
| Arize Phoenix | 1 | ~2GB | PostgreSQL (existing) | Elastic 2.0 |
| Helicone | 4 | ~8GB | PostgreSQL + ClickHouse | Open Source |

## Decision

We chose **Arize Phoenix** for the following reasons:

1. **Lightweight**: Single container, ~2GB RAM vs 16GB for Langfuse v3
2. **Reuses existing infrastructure**: Uses Nova's existing PostgreSQL database
3. **No additional databases**: No ClickHouse or MinIO required
4. **Excellent LangChain support**: First-class OpenInference instrumentation
5. **OpenTelemetry native**: Standard OTLP protocol, no vendor lock-in
6. **No API keys needed**: Self-hosted, simpler configuration

The main trade-off is the Elastic License 2.0 (vs MIT for Langfuse), which restricts offering Phoenix as a hosted service. This is acceptable for Nova's internal use.

## Implementation

### Infrastructure
- Phoenix Docker container added to `docker-compose.yml`
- Phoenix database created in existing PostgreSQL instance
- Phoenix UI accessible at `http://localhost:6006`
- OTLP gRPC endpoint at port `4317`

### Backend Integration
- New module: `backend/utils/phoenix_integration.py`
- OpenInference instrumentation for LangChain/LangGraph
- Context manager for disabling tracing (email fetching, etc.)
- Health check endpoint at `/api/user-settings/phoenix-status`

### Configuration
```python
# config.py
PHOENIX_ENABLED: bool = True
PHOENIX_HOST: str = "http://localhost:6006"
PHOENIX_GRPC_PORT: int = 4317
```

### Removed
- All Langsmith configuration (`LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, etc.)
- Langsmith validation endpoints
- Langsmith UI components in frontend

## Consequences

### Positive
- Fully on-premises LLM observability
- Lower resource requirements (~2GB vs ~16GB RAM)
- Simpler infrastructure (1 container vs 4)
- No external API dependencies
- No API key management for observability

### Negative
- Elastic License 2.0 restrictions (cannot offer as hosted service)
- Less feature-rich than Langfuse (no prompt management, less evaluation)
- Smaller community compared to Langfuse

## Related ADRs
- **ADR-010**: Unified System Health Monitoring (Phoenix status integrated)

## References
- [Phoenix Documentation](https://arize.com/docs/phoenix)
- [Phoenix GitHub](https://github.com/Arize-ai/phoenix)
- [OpenInference LangChain Integration](https://github.com/Arize-ai/openinference)

---
*Last reviewed: 2026-01-09*
