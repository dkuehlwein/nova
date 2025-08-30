"""
Nova Input Hooks System

Registry-based architecture for processing multiple input sources (email, calendar, etc.)
and converting them into Nova tasks with configurable polling and task management.
"""

from .base_hook import BaseInputHook, ProcessingResult, NormalizedItem
from .hook_registry import InputHookRegistry, input_hook_registry
from .models import HookConfig, EmailHookConfig, CalendarHookConfig

__all__ = [
    "BaseInputHook",
    "ProcessingResult", 
    "NormalizedItem",
    "InputHookRegistry",
    "input_hook_registry",
    "HookConfig",
    "EmailHookConfig",
    "CalendarHookConfig",
]