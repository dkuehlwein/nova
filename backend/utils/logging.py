"""
Structured logging configuration for Nova backend.
Implements consistent JSON logging with request correlation and optional file rotation.
"""

import logging
import logging.handlers
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import orjson
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


# Module-level logger for timing (initialized lazily)
_timing_logger = None


def log_timing(operation: str, start_time: float, extra_data: dict = None, logger=None):
    """Log timing information for performance analysis.

    Args:
        operation: Name of the operation being timed
        start_time: Start time from time.time()
        extra_data: Optional additional data to include in the log
        logger: Optional logger to use. If None, uses module-level timing logger.
    """
    global _timing_logger
    elapsed_ms = (time.time() - start_time) * 1000
    data = {"operation": operation, "elapsed_ms": round(elapsed_ms, 2)}
    if extra_data:
        data.update(extra_data)

    if logger is None:
        if _timing_logger is None:
            _timing_logger = get_logger("timing")
        logger = _timing_logger

    logger.info("TIMING completed", extra={"data": data})


def configure_logging(
    service_name: str = "nova-backend",
    log_level: str = "INFO",
    enable_json: bool = True,
    enable_file_logging: bool = False,
    log_file_path: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB default
    backup_count: int = 5
) -> None:
    """
    Configure structured logging for the Nova backend.
    
    Args:
        service_name: Name of the service for log identification
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_json: Whether to use JSON output (True) or console output (False)
        enable_file_logging: Whether to enable file logging with rotation
        log_file_path: Path to log file (defaults to ./logs/{service_name}.log)
        max_file_size: Maximum size in bytes before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create logs directory if file logging is enabled
    if enable_file_logging:
        if log_file_path is None:
            logs_dir = Path("./logs")
            logs_dir.mkdir(exist_ok=True)
            log_file_path = logs_dir / f"{service_name}.log"
        else:
            log_file_path = Path(log_file_path)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure standard library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)
    
    # Add rotating file handler if enabled
    file_handler = None
    if enable_file_logging:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(file_handler)
    
    # Shared processors for both structured and standard logging
    shared_processors = [
        # Filter by log level early to improve performance
        structlog.stdlib.filter_by_level,
        # Add service name to all logs
        structlog.processors.add_log_level,
        # Add timestamps in ISO format
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Merge context variables (request ID, etc.)
        structlog.contextvars.merge_contextvars,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Handle positional arguments
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Render stack info if requested
        structlog.processors.StackInfoRenderer(),
        # Format exception info
        structlog.processors.format_exc_info,
        # Handle Unicode
        structlog.processors.UnicodeDecoder(),
    ]
    
    if enable_json:
        # JSON output for production
        final_processor = structlog.processors.JSONRenderer()
    else:
        # Pretty console output for development
        final_processor = structlog.dev.ConsoleRenderer(colors=True)
    
    # Configure structlog
    structlog.configure(
        processors=shared_processors + [final_processor],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Bind service name globally
    structlog.contextvars.bind_contextvars(service=service_name)
    
    # Log configuration info
    logger = structlog.get_logger("logging")
    logger.info(
        "Logging configured",
        extra={
            "data": {
                "service_name": service_name,
                "log_level": log_level,
                "json_output": enable_json,
                "file_logging": enable_file_logging,
                "log_file": str(log_file_path) if enable_file_logging else None,
                "max_file_size_mb": max_file_size / (1024 * 1024) if enable_file_logging else None,
                "backup_count": backup_count if enable_file_logging else None,
            }
        }
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.
    
    Args:
        name: Optional logger name. If None, uses the calling module's name.
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that adds request correlation IDs and logs HTTP requests.
    """
    
    def __init__(self, app, service_name: str = "nova-backend"):
        super().__init__(app)
        self.service_name = service_name
        self.logger = get_logger("request")
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Clear any existing context and bind request details
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            service=self.service_name,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", "unknown"),
        )
        
        # Log request start
        self.logger.info(
            "Request started",
            extra={
                "data": {
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                }
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Log successful response
            self.logger.info(
                "Request completed",
                extra={
                    "data": {
                        "status_code": response.status_code,
                        "response_time_ms": "calculated_by_middleware"  # Could add timing
                    }
                }
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as exc:
            # Log error
            self.logger.error(
                "Request failed",
                exc_info=True,
                extra={
                    "data": {
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                    }
                }
            )
            raise


# Standard log methods for different services
def log_config_change(
    operation: str,
    config_type: str,
    details: Dict[str, Any],
    logger: Optional[structlog.stdlib.BoundLogger] = None
) -> None:
    """Log configuration changes with consistent format."""
    if logger is None:
        logger = get_logger("config")
    
    logger.info(
        "Configuration changed",
        extra={
            "data": {
                "config_type": config_type,
                "operation": operation,
                **details
            }
        }
    )


def log_external_api_call(
    service: str,
    endpoint: str,
    method: str = "GET",
    status_code: Optional[int] = None,
    duration_ms: Optional[float] = None,
    logger: Optional[structlog.stdlib.BoundLogger] = None
) -> None:
    """Log external API calls with consistent format."""
    if logger is None:
        logger = get_logger("external_api")
    
    logger.debug(
        "External API call",
        extra={
            "data": {
                "service": service,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "duration_ms": duration_ms,
            }
        }
    )


def log_system_state_change(
    component: str,
    state: str,
    details: Dict[str, Any],
    logger: Optional[structlog.stdlib.BoundLogger] = None
) -> None:
    """Log system state changes with consistent format."""
    if logger is None:
        logger = get_logger("system")
    
    logger.info(
        "System state changed",
        extra={
            "data": {
                "component": component,
                "new_state": state,
                **details
            }
        }
    ) 