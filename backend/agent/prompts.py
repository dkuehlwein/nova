"""
Agent Prompts

Centralized location for all Nova agent prompts.
"""

from utils.prompt_loader import load_nova_system_prompt

# System Prompt - Universal guidelines and capabilities (same for chat and core agent)
# Now loaded from markdown file with hot-reload support (lazy-loaded)
NOVA_SYSTEM_PROMPT = None  # Will be loaded on first access

# Task Context Template - Clean content without header (metadata provides title)
TASK_CONTEXT_TEMPLATE = """**Task ID:** {task_id}
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
async def get_nova_system_prompt(use_cache: bool = True) -> str:
    """Get the current Nova system prompt with live reload support.
    
    Args:
        use_cache: If True, use cached prompt; if False, reload from file
    """
    global NOVA_SYSTEM_PROMPT
    
    if not use_cache:
        NOVA_SYSTEM_PROMPT = None
    
    if NOVA_SYSTEM_PROMPT is None:
        NOVA_SYSTEM_PROMPT = await load_nova_system_prompt()
    return NOVA_SYSTEM_PROMPT

def clear_system_prompt_cache():
    """Clear the cached system prompt to force reload on next access."""
    global NOVA_SYSTEM_PROMPT
    NOVA_SYSTEM_PROMPT = None
