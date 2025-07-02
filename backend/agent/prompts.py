"""
Agent Prompts

Centralized location for all Nova agent prompts.
"""

from pathlib import Path
from utils.prompt_loader import load_nova_system_prompt

# System Prompt - Universal guidelines and capabilities (same for chat and core agent)
# Now loaded from markdown file with hot-reload support
NOVA_SYSTEM_PROMPT = load_nova_system_prompt()

# Task Context Template - Metadata about the task (only for core agent)
TASK_CONTEXT_TEMPLATE = """**Task Context:**

**Task ID:** {task_id}
**Status:** {status}
**Priority:** {priority}
**Created:** {created_at}
**Updated:** {updated_at}

**Memory Context:**
{memory_context}

**Recent Comments:**
{recent_comments}"""

# Current Task Template - The actual task info (only for core agent)
CURRENT_TASK_TEMPLATE = """**Current Task:**

**{title}**

{description}"""

# Function to get the current system prompt (for dynamic reloading)
def get_nova_system_prompt() -> str:
    """Get the current Nova system prompt with live reload support."""
    return load_nova_system_prompt()
