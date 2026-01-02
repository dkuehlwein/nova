"""
Skill-aware agent state for Nova's dynamic skills system.

Extends the standard agent state to track active skills, enabling
dynamic tool binding per conversation turn.
"""

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from models.skill_models import SkillActivation


class SkillAwareAgentState(TypedDict):
    """
    Extended agent state with skill tracking.

    This state schema enables dynamic tool binding by tracking which skills
    are currently active. The agent node reads this state to determine
    which tools to bind for each turn.
    """

    # Standard message history with LangGraph's reducer
    messages: Annotated[list, add_messages]

    # Active skills: skill_name -> activation metadata
    # Updated by enable_skill/disable_skill tools via the tool node
    active_skills: dict[str, SkillActivation]
