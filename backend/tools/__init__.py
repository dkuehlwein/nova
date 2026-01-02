"""
Nova LangChain Tools

Native LangChain tools for Nova agent to manage tasks and memory.
"""

from .task_tools import get_task_tools
from .human_escalation_tool import ask_user
from .memory_tools import get_memory_tools
from .skill_tools import get_skill_tools
from .tool_approval_helper import wrap_tools_for_approval
from utils.logging import get_logger

logger = get_logger(__name__)


def get_all_tools(include_escalation=False, enable_tool_approval=True):
    """Get all LangChain tools for Nova agent.

    Args:
        include_escalation: If True, include escalate_to_human tool (for task contexts only)
        enable_tool_approval: If True, wrap tools with approval system (default: True)
    """
    tools = []
    tools.extend(get_task_tools())
    tools.extend(get_memory_tools())  # Memory tools replace person/project CRUD
    tools.extend(get_skill_tools())  # Skill management tools (ADR-014)

    # Add user question tool only for task contexts (core agent)
    if include_escalation:
        tools.append(ask_user)
    
    # Wrap tools with approval system using our LangGraph interrupt-based implementation
    if enable_tool_approval:
        try:
            logger.info(f"Applying tool approval wrappers to {len(tools)} tools")
            wrapped_tools = wrap_tools_for_approval(tools)
            logger.info(f"Tool approval system enabled with LangGraph interrupt pattern")
            return wrapped_tools
        except Exception as e:
            logger.error(f"Error applying tool approval wrappers: {e}, using tools without approval")
    
    return tools 