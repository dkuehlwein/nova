"""
Phoenix integration for Nova observability (ADR-017).

Provides OpenTelemetry-based tracing for LangChain/LangGraph
with self-hosted Arize Phoenix backend.
"""

import os
from contextlib import contextmanager
from typing import Optional

from config import settings
from utils.logging import get_logger

logger = get_logger(__name__)

# Track initialization state
_phoenix_initialized = False
_original_env_state: dict = {}


def is_phoenix_enabled() -> bool:
    """Check if Phoenix tracing is enabled."""
    return settings.PHOENIX_ENABLED


def get_phoenix_endpoint() -> str:
    """Get the Phoenix OTLP gRPC endpoint.

    Handles both local development (localhost) and Docker environments
    (phoenix service name).
    """
    # In Docker, use service name; locally use configured host
    if settings._is_running_in_docker():
        return f"http://phoenix:{settings.PHOENIX_GRPC_PORT}"

    # Parse host to get just the hostname
    host = settings.PHOENIX_HOST.replace("http://", "").replace("https://", "")
    # Remove any port from the host if present
    if ":" in host:
        host = host.split(":")[0]
    return f"http://{host}:{settings.PHOENIX_GRPC_PORT}"


def init_phoenix_tracing(service_name: str = "nova") -> bool:
    """Initialize Phoenix tracing with OpenTelemetry.

    This sets up the OpenInference instrumentation for LangChain
    and configures the OTLP exporter to send traces to Phoenix.

    Args:
        service_name: Name to identify this service in traces

    Returns:
        True if initialization succeeded, False otherwise
    """
    global _phoenix_initialized

    if _phoenix_initialized:
        logger.debug("Phoenix tracing already initialized")
        return True

    if not is_phoenix_enabled():
        logger.info("Phoenix tracing is disabled")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from openinference.instrumentation.langchain import LangChainInstrumentor

        # Create resource with service name
        resource = Resource.create({"service.name": service_name})

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # Configure OTLP exporter to Phoenix
        endpoint = get_phoenix_endpoint()
        otlp_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)

        # Add span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)

        # Set as global tracer provider
        trace.set_tracer_provider(tracer_provider)

        # Instrument LangChain
        LangChainInstrumentor().instrument()

        _phoenix_initialized = True
        logger.info("Phoenix tracing initialized", extra={"data": {"endpoint": endpoint}})
        return True

    except ImportError as e:
        logger.warning("Phoenix dependencies not installed", extra={"data": {"error": str(e)}})
        return False
    except Exception as e:
        logger.warning("Failed to initialize Phoenix tracing", extra={"data": {"error": str(e)}})
        return False


def shutdown_phoenix_tracing():
    """Shutdown Phoenix tracing and flush pending spans."""
    global _phoenix_initialized

    if not _phoenix_initialized:
        return

    try:
        from opentelemetry import trace

        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, 'shutdown'):
            tracer_provider.shutdown()

        _phoenix_initialized = False
        logger.info("Phoenix tracing shut down")
    except Exception as e:
        logger.warning("Error shutting down Phoenix tracing", extra={"data": {"error": str(e)}})


@contextmanager
def disable_phoenix_tracing():
    """Temporarily disable Phoenix tracing.

    Use this context manager for operations that should not be traced
    (e.g., email polling, background tasks that would create noise).

    This works by temporarily setting environment variables that
    disable tracing and restoring them afterwards.
    """
    global _original_env_state

    # Store original values
    env_vars = [
        "PHOENIX_ENABLED",
        "OTEL_SDK_DISABLED",
    ]

    _original_env_state = {
        var: os.environ.get(var) for var in env_vars
    }

    try:
        # Disable tracing
        os.environ["PHOENIX_ENABLED"] = "false"
        os.environ["OTEL_SDK_DISABLED"] = "true"
        yield
    finally:
        # Restore original values
        for var, value in _original_env_state.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value


async def check_phoenix_health() -> dict:
    """Check if Phoenix server is healthy and reachable.

    Returns:
        Dictionary with health status information
    """
    import aiohttp

    if not is_phoenix_enabled():
        return {
            "healthy": False,
            "enabled": False,
            "message": "Phoenix tracing is disabled",
        }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                settings.PHOENIX_HOST,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return {
                    "healthy": response.status == 200,
                    "enabled": True,
                    "host": settings.PHOENIX_HOST,
                    "status_code": response.status,
                }
    except aiohttp.ClientError as e:
        return {
            "healthy": False,
            "enabled": True,
            "host": settings.PHOENIX_HOST,
            "error": str(e),
        }
    except Exception as e:
        return {
            "healthy": False,
            "enabled": True,
            "host": settings.PHOENIX_HOST,
            "error": str(e),
        }


def get_langchain_trace_id() -> Optional[str]:
    """Get the current trace ID from LangChain's OpenInference instrumentation.

    This should be called during or after LangChain LLM operations when the
    instrumentation has created a span context. The trace ID returned will
    match what Phoenix records for the LangChain operations.

    Returns:
        Hex-encoded trace ID string (32 characters), or None if not in a traced context
    """
    if not _phoenix_initialized:
        return None

    try:
        from openinference.instrumentation.langchain import get_current_span

        span = get_current_span()
        if span:
            span_context = span.get_span_context()
            if span_context and span_context.is_valid:
                return format(span_context.trace_id, '032x')
        return None
    except ImportError:
        logger.debug("openinference.instrumentation.langchain not available")
        return None
    except Exception as e:
        logger.debug("Could not get LangChain trace ID", extra={"data": {"error": str(e)}})
        return None


def get_phoenix_trace_url(trace_id: str, project_id: str = "UHJvamVjdDox") -> str:
    """Generate a Phoenix UI URL for a specific trace.

    Args:
        trace_id: Hex-encoded trace ID
        project_id: Phoenix project ID (base64 encoded). Defaults to the "default" project.

    Returns:
        Full URL to view the trace in Phoenix UI
    """
    # Phoenix uses the format: {host}/projects/{project_id}/traces/{trace_id}
    return f"{settings.PHOENIX_HOST}/projects/{project_id}/traces/{trace_id}"
