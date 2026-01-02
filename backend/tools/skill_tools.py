"""
Skill management tools for Nova's dynamic pluggable skills system.

These tools allow the agent to activate and deactivate specialized skills
on demand, dynamically loading instructions and tools as needed.
"""

from langchain_core.tools import tool

from models.skill_models import SkillNotFoundError
from utils.logging import get_logger
from utils.skill_manager import get_skill_manager

logger = get_logger(__name__)


@tool
async def enable_skill(skill_name: str) -> str:
    """
    Activate a specialized skill to gain domain-specific tools and knowledge.

    Use this when a user request matches one of the available skills listed
    in your system prompt. The skill's instructions and tools will become
    available for subsequent turns.

    Args:
        skill_name: Name of the skill to activate (e.g., "_example_skill")

    Returns:
        Skill instructions and list of newly available tools, or error message
        if the skill is not found.
    """
    skill_manager = get_skill_manager()

    try:
        skill = await skill_manager.load_skill(skill_name)
    except SkillNotFoundError:
        available = skill_manager.list_skills()
        logger.warning(
            f"Attempted to enable unknown skill: {skill_name}",
            extra={"data": {"skill_name": skill_name, "available": available}},
        )
        if available:
            return f"Unknown skill '{skill_name}'. Available skills: {', '.join(available)}"
        else:
            return f"Unknown skill '{skill_name}'. No skills are currently available."
    except Exception as e:
        logger.error(
            f"Failed to load skill: {skill_name}",
            exc_info=True,
            extra={"data": {"skill_name": skill_name, "error": str(e)}},
        )
        return f"Failed to load skill '{skill_name}': {str(e)}"

    # Get namespaced tool names for display
    tool_names = [f"{skill_name}__{t.name}" for t in skill.tools]

    logger.info(
        f"Skill activated: {skill_name}",
        extra={
            "data": {
                "skill_name": skill_name,
                "version": skill.manifest.version,
                "tools": tool_names,
            }
        },
    )

    # Return instructions and tool list as tool output
    # This appears naturally in the conversation context
    return f"""## Skill Activated: {skill.manifest.name} v{skill.manifest.version}

{skill.instructions}

**New tools available:** {', '.join(tool_names) if tool_names else 'None'}

You now have the knowledge and tools to proceed with this workflow.
"""


@tool
async def disable_skill(skill_name: str) -> str:
    """
    Deactivate a skill, removing its tools from availability.

    Use this when you are done with a specialized workflow and no longer
    need the skill's tools. The skill can be re-enabled later if needed.

    Args:
        skill_name: Name of the skill to deactivate

    Returns:
        Confirmation message
    """
    skill_manager = get_skill_manager()

    # Verify the skill exists (even though state management is handled by tool_node)
    if skill_name not in skill_manager.list_skills():
        available = skill_manager.list_skills()
        logger.warning(
            f"Attempted to disable unknown skill: {skill_name}",
            extra={"data": {"skill_name": skill_name, "available": available}},
        )
        if available:
            return f"Unknown skill '{skill_name}'. Available skills: {', '.join(available)}"
        else:
            return f"Unknown skill '{skill_name}'. No skills are currently available."

    logger.info(
        f"Skill deactivated: {skill_name}",
        extra={"data": {"skill_name": skill_name}},
    )

    # State update is handled by the tool_node in the agent graph
    return f"Skill '{skill_name}' deactivated. Its tools are no longer available."


def get_skill_tools():
    """Return all skill management tools."""
    return [enable_skill, disable_skill]
