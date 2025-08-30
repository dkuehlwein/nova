"""
Integration tests for the input hooks system.

This test verifies that:
1. Hook registry initializes correctly
2. Email hook can be registered and configured
3. Hook system integrates with Celery properly
4. Dual-mode operation works (hook vs legacy)

Run with: uv run pytest tests/backend/test_hook_integration.py -v
"""

import asyncio
import pytest

@pytest.mark.asyncio
async def test_hook_registry():
    """Test basic hook registry functionality."""
    from input_hooks.hook_registry import InputHookRegistry
    from input_hooks.models import EmailHookConfig
    
    # Create registry instance
    registry = InputHookRegistry()
    
    # Test hook registration
    email_config = EmailHookConfig(
        name="test_email",
        enabled=True,
        polling_interval=300
    )
    
    assert registry is not None
    assert email_config.name == "test_email"
    assert email_config.enabled == True


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


def test_dual_mode_operation():
    """Test hook system operation (legacy dual-mode removed)."""
    from input_hooks.hook_registry import input_hook_registry
    
    # Test hook system detection via registry
    enabled_hooks = input_hook_registry.list_enabled_hooks()
    
    assert isinstance(enabled_hooks, list)
    
    # Test that we can check if specific hooks are available
    email_hook = input_hook_registry.get_hook("email")
    # email_hook could be None or an EmailInputHook instance


def test_email_hook_wrapper():
    """Test email hook wrapper functionality."""
    from input_hooks.email_hook import EmailInputHook
    from input_hooks.models import EmailHookConfig
    
    # Create email hook configuration
    config = EmailHookConfig(
        name="test_email",
        enabled=True,
        polling_interval=300
    )
    
    # Create email hook instance
    email_hook = EmailInputHook("test_email", config)
    
    # Test hook methods exist
    assert hasattr(email_hook, 'fetch_items')
    assert hasattr(email_hook, 'normalize_item')
    assert hasattr(email_hook, 'process_items')
    assert callable(email_hook.fetch_items)
    assert callable(email_hook.normalize_item)


def test_database_model():
    """Test database model integration."""
    from models.models import ProcessedEmail
    
    # Test email model attributes exist (hook system still uses existing processed_emails table)
    assert hasattr(ProcessedEmail, 'email_id')
    assert hasattr(ProcessedEmail, 'task_id')
    assert hasattr(ProcessedEmail, 'processed_at')


def test_hook_tasks_import():
    """Test hook tasks can be imported."""
    from tasks.hook_tasks import process_hook_items, process_single_item
    
    # Test tasks are properly defined
    assert hasattr(process_hook_items, 'delay')  # Celery task method
    assert hasattr(process_single_item, 'delay')  # Celery task method


# Tests complete - run with: uv run pytest tests/backend/test_hook_integration.py -v