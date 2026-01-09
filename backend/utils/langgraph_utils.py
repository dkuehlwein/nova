"""
LangGraph Utilities.

Shared utilities for LangGraph operations including config creation
and common constants.
"""

from datetime import datetime
from typing import Any, Dict, Optional


# Thread ID prefix for task-related conversations
TASK_THREAD_PREFIX = "core_agent_task_"

# Tool placeholder template for message reconstruction
TOOL_PLACEHOLDER_TEMPLATE = "[[TOOL:{index}]]"


def create_langgraph_config(thread_id: Optional[str] = None) -> Dict[str, Any]:
    """Create configuration for LangGraph with thread ID.

    Args:
        thread_id: Optional thread ID. If None, generates a new one with timestamp.

    Returns:
        LangGraph configuration dict with thread_id in configurable.
    """
    if thread_id is None:
        thread_id = f"chat-{datetime.now().isoformat()}"

    return {"configurable": {"thread_id": thread_id}}


def get_task_id_from_thread(thread_id: str) -> Optional[str]:
    """Extract task ID from a task thread ID.

    Args:
        thread_id: The thread ID to parse

    Returns:
        Task ID if thread is a task thread, None otherwise
    """
    if thread_id.startswith(TASK_THREAD_PREFIX):
        return thread_id[len(TASK_THREAD_PREFIX):]
    return None


def create_task_thread_id(task_id: str) -> str:
    """Create a thread ID for a task.

    Args:
        task_id: The task ID

    Returns:
        Thread ID for the task
    """
    return f"{TASK_THREAD_PREFIX}{task_id}"
