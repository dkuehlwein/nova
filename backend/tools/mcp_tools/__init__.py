"""
Nova Kanban MCP Tools Package

Organized MCP tools for the Nova agent integration.
"""

from .task_tools import get_task_tools
from .person_tools import get_person_tools  
from .project_tools import get_project_tools


def get_mcp_tools():
    """Get all MCP tools for registration."""
    tools = []
    tools.extend(get_task_tools())
    tools.extend(get_person_tools())
    tools.extend(get_project_tools())
    return tools 