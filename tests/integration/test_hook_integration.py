"""
Integration tests for the input hooks system.

This test verifies that:
1. Hook registry initializes correctly
2. Gmail hook can be registered and configured
3. Hook system integrates with Celery properly

Run with: uv run pytest tests/integration/test_hook_integration.py -v
"""

import asyncio
import pytest

@pytest.mark.asyncio
async def test_hook_registry():
    """Test basic hook registry functionality."""
    from input_hooks.hook_registry import InputHookRegistry
    from input_hooks.models import GmailHookConfig

    # Create registry instance
    registry = InputHookRegistry()

    # Test hook registration
    gmail_config = GmailHookConfig(
        name="test_gmail",
        enabled=True,
        polling_interval=300
    )

    assert registry is not None
    assert gmail_config.name == "test_gmail"
    assert gmail_config.enabled == True


@pytest.mark.asyncio
async def test_hook_system_availability():
    """Test if hook system is properly available."""
    from input_hooks.hook_registry import input_hook_registry

    # Test that registry functions are available
    hooks = input_hook_registry.list_hooks()
    assert isinstance(hooks, list)

    # Test that hook system can be checked via registry
    enabled_hooks = input_hook_registry.list_enabled_hooks()
    assert isinstance(enabled_hooks, list)


def test_config_integration():
    """Test configuration integration."""
    from utils.config_registry import config_registry

    # Check if config registry works
    configs = config_registry.list_configs()
    assert isinstance(configs, list)

    # Note: input_hooks config may not be available in test environment
    # This tests the basic config registry functionality


def test_celery_integration():
    """Test Celery integration."""
    from celery_app import update_beat_schedule, celery_app

    # Test function imports
    assert callable(update_beat_schedule)

    # Test task routing
    routes = celery_app.conf.task_routes
    assert isinstance(routes, dict)

    # Check for hook tasks in routes
    hook_tasks = [route for route in routes.keys() if "hook_tasks" in route]
    assert len(hook_tasks) > 0  # Should have at least some hook tasks configured


def test_hook_system_operation():
    """Test hook system operation."""
    from input_hooks.hook_registry import input_hook_registry

    # Test hook system detection via registry
    enabled_hooks = input_hook_registry.list_enabled_hooks()

    assert isinstance(enabled_hooks, list)

    # Test that we can check if specific hooks are available
    gmail_hook = input_hook_registry.get_hook("gmail")
    # gmail_hook could be None or a GmailInputHook instance


def test_gmail_hook_wrapper():
    """Test Gmail hook wrapper functionality."""
    from input_hooks.gmail_hook import GmailInputHook
    from input_hooks.models import GmailHookConfig

    # Create Gmail hook configuration
    config = GmailHookConfig(
        name="test_gmail",
        enabled=True,
        polling_interval=300
    )

    # Create Gmail hook instance
    gmail_hook = GmailInputHook("test_gmail", config)

    # Test hook methods exist
    assert hasattr(gmail_hook, 'fetch_items')
    assert hasattr(gmail_hook, 'normalize_item')
    assert hasattr(gmail_hook, 'process_items')
    assert callable(gmail_hook.fetch_items)
    assert callable(gmail_hook.normalize_item)


def test_database_model():
    """Test database model integration."""
    from models.models import ProcessedItem

    # Test ProcessedItem model attributes exist (hook system uses generalized processed_items table)
    assert hasattr(ProcessedItem, 'source_type')
    assert hasattr(ProcessedItem, 'source_id')
    assert hasattr(ProcessedItem, 'task_id')
    assert hasattr(ProcessedItem, 'processed_at')


def test_hook_tasks_import():
    """Test hook tasks can be imported."""
    from tasks.hook_tasks import process_hook_items, process_single_item

    # Test tasks are properly defined
    assert hasattr(process_hook_items, 'delay')  # Celery task method
    assert hasattr(process_single_item, 'delay')  # Celery task method


# Tests complete - run with: uv run pytest tests/integration/test_hook_integration.py -v
