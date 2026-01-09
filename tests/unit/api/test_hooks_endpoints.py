"""
Tests for hooks API endpoints.
Tests listing, updating, and triggering input hooks.

These tests verify the API endpoint logic by testing the internal functions
and response models directly, avoiding complex mocking of the real hook registry
which gets initialized through Celery imports.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.api.hooks_endpoints import (
    _get_hook_status,
    _calculate_next_run,
    HookResponse,
    HooksListResponse,
    HookConfigUpdate,
    TriggerResponse,
    HookStatsResponse,
)


class MockHookConfig:
    """Mock hook config for testing."""
    def __init__(self, enabled=True, hook_type="email", polling_interval=60):
        self.enabled = enabled
        self.hook_type = hook_type
        self.polling_interval = polling_interval


class MockHook:
    """Mock hook for testing."""
    def __init__(self, enabled=True):
        self.config = MockHookConfig(enabled=enabled)


class TestGetHookStatus:
    """Test _get_hook_status helper function."""

    def test_disabled_hook_returns_disabled(self):
        """Test that disabled hooks return 'disabled' status."""
        hook = MockHook(enabled=False)
        stats = {"total_runs": 10, "last_error": None}

        status = _get_hook_status(hook, stats)

        assert status == "disabled"

    def test_hook_with_error_returns_error(self):
        """Test that hooks with last_error return 'error' status."""
        hook = MockHook(enabled=True)
        stats = {"total_runs": 10, "last_error": "Connection timeout"}

        status = _get_hook_status(hook, stats)

        assert status == "error"

    def test_enabled_hook_no_error_returns_idle(self):
        """Test that enabled hooks without errors return 'idle' status."""
        hook = MockHook(enabled=True)
        stats = {"total_runs": 10, "last_error": None}

        status = _get_hook_status(hook, stats)

        assert status == "idle"

    def test_enabled_hook_empty_stats_returns_idle(self):
        """Test that enabled hooks with empty stats return 'idle' status."""
        hook = MockHook(enabled=True)
        stats = {}

        status = _get_hook_status(hook, stats)

        assert status == "idle"


class TestCalculateNextRun:
    """Test _calculate_next_run helper function."""

    def test_disabled_hook_returns_none(self):
        """Test that disabled hooks return None for next run."""
        last_run = datetime(2026, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        result = _calculate_next_run(last_run, 60, enabled=False)

        assert result is None

    def test_no_last_run_returns_now(self):
        """Test that hooks without last_run return current time."""
        result = _calculate_next_run(None, 60, enabled=True)

        assert result is not None
        # Parse and verify it's close to now
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        assert abs((parsed - now).total_seconds()) < 5

    def test_calculates_next_run_from_last_run(self):
        """Test that next run is calculated correctly from last run + interval."""
        last_run = datetime(2026, 1, 9, 10, 0, 0, tzinfo=timezone.utc)

        result = _calculate_next_run(last_run, 60, enabled=True)

        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        expected = datetime(2026, 1, 9, 10, 1, 0, tzinfo=timezone.utc)
        assert abs((parsed - expected).total_seconds()) < 1


class TestHookResponseModel:
    """Test HookResponse Pydantic model."""

    def test_valid_hook_response(self):
        """Test creating a valid HookResponse."""
        response = HookResponse(
            name="email",
            hook_type="email",
            display_name="Gmail",
            enabled=True,
            polling_interval=60,
            status="idle",
            last_run="2026-01-09T10:00:00Z",
            next_run="2026-01-09T10:01:00Z",
            stats=HookStatsResponse(total_runs=100, successful_runs=98),
            last_error=None,
            hook_settings={"max_per_fetch": 50},
        )

        assert response.name == "email"
        assert response.display_name == "Gmail"
        assert response.enabled is True
        assert response.stats.total_runs == 100

    def test_default_values(self):
        """Test HookResponse with default values."""
        response = HookResponse(
            name="email",
            hook_type="email",
            display_name="Gmail",
            enabled=True,
            polling_interval=60,
        )

        assert response.status == "idle"
        assert response.last_run is None
        assert response.stats.total_runs == 0


class TestHookConfigUpdateModel:
    """Test HookConfigUpdate Pydantic model."""

    def test_valid_enable_update(self):
        """Test updating enabled field."""
        update = HookConfigUpdate(enabled=True)

        assert update.enabled is True
        assert update.polling_interval is None

    def test_valid_interval_update(self):
        """Test updating polling_interval field."""
        update = HookConfigUpdate(polling_interval=120)

        assert update.polling_interval == 120
        assert update.enabled is None

    def test_invalid_interval_zero(self):
        """Test that zero polling_interval is rejected."""
        with pytest.raises(ValidationError):
            HookConfigUpdate(polling_interval=0)

    def test_invalid_interval_negative(self):
        """Test that negative polling_interval is rejected."""
        with pytest.raises(ValidationError):
            HookConfigUpdate(polling_interval=-10)


class TestTriggerResponseModel:
    """Test TriggerResponse Pydantic model."""

    def test_valid_trigger_response(self):
        """Test creating a valid TriggerResponse."""
        response = TriggerResponse(
            task_id="abc123",
            hook_name="email",
            status="queued",
            queued_at="2026-01-09T10:00:00Z",
        )

        assert response.task_id == "abc123"
        assert response.hook_name == "email"
        assert response.status == "queued"


class TestHooksListResponseModel:
    """Test HooksListResponse Pydantic model."""

    def test_empty_hooks_list(self):
        """Test response with empty hooks list."""
        response = HooksListResponse(hooks=[])

        assert response.hooks == []

    def test_hooks_list_with_items(self):
        """Test response with hook items."""
        hook = HookResponse(
            name="email",
            hook_type="email",
            display_name="Gmail",
            enabled=True,
            polling_interval=60,
        )
        response = HooksListResponse(hooks=[hook])

        assert len(response.hooks) == 1
        assert response.hooks[0].name == "email"
        assert response.hooks[0].display_name == "Gmail"
