"""
Tool approval helper implementing LangGraph's add_human_in_the_loop pattern.
Based on official LangGraph documentation: https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/add-human-in-the-loop/
"""
from typing import Callable, Dict, Any, TypedDict
from langchain_core.tools import BaseTool, tool as create_tool
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from utils.logging import get_logger

logger = get_logger(__name__)


class HumanInterruptConfig(TypedDict, total=False):
    """Configuration for human interrupt behavior."""
    allow_accept: bool
    allow_edit: bool  
    allow_respond: bool


def add_human_in_the_loop(
    tool: Callable | BaseTool,
    *,
    interrupt_config: HumanInterruptConfig = None,
) -> BaseTool:
    """
    Wrap a tool to support human-in-the-loop review using LangGraph's interrupt pattern.
    
    This function creates a wrapper around existing tools that pauses execution
    and requests human approval before proceeding with tool calls.
    
    Args:
        tool: The tool to wrap (either a Callable or BaseTool)
        interrupt_config: Configuration for interrupt behavior
        
    Returns:
        BaseTool: Wrapped tool that requires human approval
    """
    if not isinstance(tool, BaseTool):
        tool = create_tool(tool)

    if interrupt_config is None:
        interrupt_config = {
            "allow_accept": True,
            "allow_edit": True,
            "allow_respond": True,
        }

    @create_tool(
        tool.name,
        description=f"[REQUIRES APPROVAL] {tool.description}",
        args_schema=tool.args_schema
    )
    async def call_tool_with_interrupt(config: RunnableConfig = None, **tool_input):
        """Wrapped tool function that requests human approval via interrupt."""
        logger.info("Tool approval requested", extra={"data": {
            "tool_name": tool.name,
            "tool_args": tool_input
        }})
        
        # Create approval question similar to ask_user pattern
        approval_question = f"Nova wants to use the tool: {tool.name}\n\nParameters: {tool_input}\n\nDo you approve this action?"
        
        # Call interrupt to pause execution and request human input - using same pattern as ask_user
        logger.info("Calling interrupt for tool", extra={"data": {"name": tool.name}})
        user_response = interrupt({
            "type": "tool_approval_request",
            "tool_name": tool.name,
            "tool_args": tool_input,
            "question": approval_question,
            "instructions": "Please approve or deny this tool action to continue."
        })
            
        logger.info("Received interrupt response", extra={"data": {"name": tool.name, "user_response": user_response}})
        
        # Handle LangGraph interrupt response format (could be direct value or list)
        response_data = user_response
        if isinstance(user_response, list) and len(user_response) > 0:
            response_data = user_response[0]
        
        # Handle the three possible responses: approve, always_allow, deny
        if isinstance(response_data, dict):
            response_value = response_data.get("type", "deny")
        else:
            response_value = str(response_data).lower().strip()
        
        if response_value == "approve":
            logger.info("Tool approved - executing with original args", extra={"data": {"name": tool.name}})
            tool_response = await tool.ainvoke(tool_input, config)
        elif response_value == "always_allow":
            logger.info("Tool approved with always allow - adding to config", extra={"data": {"name": tool.name}})
            # Add permission to config for future auto-approval
            from utils.tool_permissions_manager import permission_config
            try:
                await permission_config.add_permission(tool.name, tool_input)
                logger.info("Added always allow permission", extra={"data": {"name": tool.name}})
                # Clear the chat agent cache so the permission takes effect immediately
                # Without this, the current chat would still use the old cached wrapped tools
                from agent.chat_agent import clear_chat_agent_cache
                clear_chat_agent_cache()
                logger.info("Cleared chat agent cache for immediate permission effect")
            except Exception as e:
                logger.error("Failed to add permission", extra={"data": {"name": tool.name, "error": str(e)}})
            # Still execute the tool this time
            tool_response = await tool.ainvoke(tool_input, config)
        else:
            # Default to deny for any other response (including explicit "deny")
            logger.info("Tool denied - response", extra={"data": {"name": tool.name, "response_value": response_value}})
            tool_response = f"Tool {tool.name} was denied by user. Response: {response_data}"

        logger.info("Tool execution completed", extra={"data": {"tool_name": tool.name, "response_preview": str(tool_response)[:100]}})
        return tool_response

    return call_tool_with_interrupt


def request_tool_approval(tool_name: str, tool_args: Dict[str, Any]) -> str:
    logger.info("Requesting tool approval", extra={"data": {"tool_name": tool_name}})
    logger.info("About to call interrupt() for tool approval")

    # Use LangGraph interrupt with tool approval type
    user_response = interrupt({
        "type": "tool_approval_request",
        "tool_name": tool_name,
        "tool_args": tool_args
    })

    logger.info("interrupt returned: (type", extra={"data": {"user_response": user_response, "type": type(user_response)}})

    # Process the user response
    if isinstance(user_response, str):
        response = user_response
    elif isinstance(user_response, dict):
        response = user_response.get("response", "deny")
    else:
        response = str(user_response)

    return response


def wrap_tools_for_approval(tools: list[BaseTool]) -> list[BaseTool]:
    """
    Wrap tools that require approval with the human-in-the-loop pattern.

    Checks each tool against the permission config (allow/deny lists, default_secure).
    Tools explicitly denied are removed entirely (the agent never sees them).
    Tools not explicitly allowed will be wrapped with approval requirement.
    """
    from utils.tool_permissions_manager import permission_config

    wrapped_tools = []
    wrapped_count = 0
    denied_count = 0

    for tool in tools:
        if permission_config.is_tool_denied(tool.name):
            logger.info("Excluding denied tool", extra={"data": {"name": tool.name}})
            denied_count += 1
        elif not permission_config.is_tool_allowed(tool.name):
            logger.info("Wrapping tool for approval", extra={"data": {"name": tool.name}})
            wrapped_tools.append(add_human_in_the_loop(tool))
            wrapped_count += 1
        else:
            wrapped_tools.append(tool)

    logger.info("Tool approval wrapping complete", extra={"data": {"available_count": len(wrapped_tools), "wrapped_count": wrapped_count, "denied_count": denied_count}})
    return wrapped_tools