"""
Nova LangChain Tools

Native LangChain tools for Nova agent to manage tasks and memory.
"""

from .task_tools import get_task_tools
from .human_escalation_tool import escalate_to_human
from .memory_tools import get_memory_tools


def get_all_tools():
    """Get all LangChain tools for Nova agent."""
    tools = []
    tools.extend(get_task_tools())
    tools.extend(get_memory_tools())  # Memory tools replace person/project CRUD
    
    # Add human escalation tool
    tools.append(escalate_to_human)
    
    return tools 