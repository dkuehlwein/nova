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


def get_local_tools(include_escalation=False):
    """Get local Nova tools (task, memory, skill management).

    Does NOT include MCP tools - use chat_agent.get_all_tools() for complete tool set.
    """
    tools = []
    tools.extend(get_task_tools())
    tools.extend(get_memory_tools())
    tools.extend(get_skill_tools())

    if include_escalation:
        tools.append(ask_user)

    return tools 