"""
Tests for structured logging configuration.
"""

import json
import logging
from io import StringIO
from unittest.mock import patch
import sys

import pytest
import structlog

from backend.utils.logging import (
    configure_logging,
    get_logger,
    log_config_change,
)


class CapturingHandler(logging.Handler):
    """A logging handler that captures log records."""
    
    def __init__(self):
        super().__init__()
        self.records = []
        
    def emit(self, record):
        self.records.append(self.format(record))


@pytest.fixture
def capturing_handler():
    """Provide a capturing handler for tests."""
    return CapturingHandler()


def test_logger_context_variables(capturing_handler):
    """Test that context variables are properly bound."""
    configure_logging(service_name="test-service", enable_json=True)
    
    # Add our capturing handler to the root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(capturing_handler)
    
    # Bind context
    structlog.contextvars.bind_contextvars(request_id="test-123")
    
    logger = get_logger("test")
    logger.info("Test message")
    
    # Check captured output
    assert len(capturing_handler.records) > 0
    output = capturing_handler.records[-1]
    assert "test-123" in output
    
    # Clean up
    root_logger.removeHandler(capturing_handler)


def test_log_config_change(capturing_handler):
    """Test the log_config_change helper function."""
    configure_logging(service_name="test-service", enable_json=True)
    
    # Add our capturing handler
    root_logger = logging.getLogger()
    root_logger.addHandler(capturing_handler)
    
    log_config_change(
        operation="update",
        config_type="mcp_server",
        details={"server_name": "gmail", "enabled": True}
    )
    
    # Check captured output
    assert len(capturing_handler.records) > 0
    output = capturing_handler.records[-1]
    assert "Configuration changed" in output
    assert "gmail" in output
    
    # Clean up
    root_logger.removeHandler(capturing_handler)
