"""
Nova LangChain Tools

Native LangChain tools for Nova agent to manage tasks and memory.
"""

from .task_tools import get_task_tools
from .human_escalation_tool import ask_user
from .memory_tools import get_memory_tools


def get_all_tools(include_escalation=False):
    """Get all LangChain tools for Nova agent.
    
    Args:
        include_escalation: If True, include escalate_to_human tool (for task contexts only)
    """
    tools = []
    tools.extend(get_task_tools())
    tools.extend(get_memory_tools())  # Memory tools replace person/project CRUD
    
    # Add user question tool only for task contexts (core agent)
    if include_escalation:
        tools.append(ask_user)
    
    return tools 