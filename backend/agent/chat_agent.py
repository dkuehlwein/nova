"""
Nova LangGraph Chat Agent

A modern LangGraph chat agent with dynamic skill loading support (ADR-014).
Uses a custom StateGraph instead of create_react_agent to enable per-turn
dynamic tool binding based on active skills.
"""

from __future__ import annotations

import time
from typing import Any, List, Literal, Optional

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from mcp_client import mcp_manager
from tools import get_local_tools
from tools.tool_approval_helper import wrap_tools_for_approval
from utils.logging import get_logger, log_timing
from utils.skill_manager import get_skill_manager

from .chat_llm import create_chat_llm
from .prompts import get_nova_system_prompt
from .skill_aware_state import SkillAwareAgentState

logger = get_logger(__name__)


# Cache for tools to avoid repeated fetching
_cached_tools: Optional[List[Any]] = None

# Cache for agent components (separate from checkpointer)
_cached_llm = None


async def get_all_tools(use_cache=True, include_escalation=False) -> List[Any]:
    """Get all tools (local Nova tools + MCP tools), wrapped for approval.

    Args:
        use_cache: If True, use cached tools; if False, reload tools
        include_escalation: If True, include ask_user tool (for task contexts)
    """
    global _cached_tools
    t0 = time.time()

    if not use_cache or (include_escalation and _cached_tools is not None):
        _cached_tools = None
        logger.info("Tools cache cleared for reload")

    if _cached_tools is not None:
        return _cached_tools

    # Get local Nova tools
    t1 = time.time()
    local_tools = get_local_tools(include_escalation=include_escalation)
    log_timing("get_local_tools", t1, {"count": len(local_tools)})

    # Get MCP tools from external servers
    try:
        t1 = time.time()
        mcp_tools = await mcp_manager.get_tools()
        log_timing("get_mcp_tools", t1, {"count": len(mcp_tools)})
    except Exception as e:
        logger.warning("Could not fetch MCP tools", extra={"data": {"error": str(e)}})
        mcp_tools = []

    # Combine all tools and wrap for approval
    all_tools = local_tools + mcp_tools
    t1 = time.time()
    _cached_tools = wrap_tools_for_approval(all_tools)
    log_timing("wrap_tools_for_approval", t1, {"count": len(_cached_tools)})

    logger.info("Tools: local + MCP = total", extra={"data": {"local_tools_count": len(local_tools), "mcp_tools_count": len(mcp_tools), "_cached_tools_count": len(_cached_tools)}})
    return _cached_tools


async def get_llm(use_cache=True):
    """Get cached LLM or create new one if not cached.
    
    Args:
        use_cache: If True, use cached LLM; if False, reload LLM
    """
    global _cached_llm
    
    if not use_cache:
        _cached_llm = None
        logger.info("LLM cache cleared for reload")
    
    if _cached_llm is None:
        _cached_llm = create_chat_llm()
        logger.debug("LLM created and cached for reuse")
    
    return _cached_llm


async def create_chat_agent(checkpointer=None, pg_pool=None, use_cache=True, include_escalation=False):
    """Create LangGraph chat agent with dynamic skill loading support.

    This creates a custom StateGraph that supports per-turn dynamic tool binding
    based on active skills. When a skill is enabled, its tools become available
    on the next turn.

    Args:
        checkpointer: Optional checkpointer to use for conversation state
        pg_pool: PostgreSQL connection pool (required if no checkpointer provided)
        use_cache: If True, use cached components; if False, reload everything
        include_escalation: If True, include ask_user tool (for task contexts)

    Returns:
        LangGraph chat agent with current tools/prompt and PostgreSQL checkpointer

    Raises:
        ValueError: If neither checkpointer nor pg_pool is provided

    Notes:
        - Always creates fresh agent instance (no agent instance caching)
        - Caches components (tools, LLM) separately from checkpointer
        - Every conversation gets latest tools/prompt when cache is cleared
        - Each conversation can have its own checkpointer for state management
        - PostgreSQL checkpointer is required - no MemorySaver fallback
        - Supports dynamic skill activation/deactivation (ADR-014)
    """
    # Clear component caches if requested
    if not use_cache:
        clear_chat_agent_cache()

    # Create checkpointer if none provided
    if checkpointer is None:
        if pg_pool is None:
            raise ValueError("PostgreSQL connection pool is required when no checkpointer provided")
        # Use provided pool for checkpointer
        from utils.service_manager import create_postgres_checkpointer

        checkpointer = create_postgres_checkpointer(pg_pool)

    agent_start = time.time()
    logger.info(
        "Creating chat agent",
        extra={
            "data": {
                "has_custom_checkpointer": checkpointer is not None,
                "has_pg_pool": pg_pool is not None,
                "use_cache": use_cache,
                "checkpointer_type": type(checkpointer).__name__,
            }
        },
    )

    # Get cached or fresh components
    t0 = time.time()
    llm = await get_llm(use_cache=use_cache)
    log_timing("get_llm", t0)

    t0 = time.time()
    base_tools = await get_all_tools(
        use_cache=use_cache, include_escalation=include_escalation
    )
    log_timing("get_all_tools", t0, {"count": len(base_tools)})

    t0 = time.time()
    system_prompt = await get_nova_system_prompt(use_cache=use_cache)
    log_timing("get_nova_system_prompt", t0)

    # Get skill manager for dynamic tool loading
    skill_manager = get_skill_manager()

    # Cache for skill tools (loaded on demand)
    skill_tools_cache: dict[str, list] = {}

    async def get_tools_for_state(state: SkillAwareAgentState) -> list:
        """Get all tools including dynamically loaded skill tools."""
        all_tools = list(base_tools)

        active_skills = state.get("active_skills", {})
        for skill_name in active_skills:
            if skill_name not in skill_tools_cache:
                try:
                    skill_tools_cache[skill_name] = await skill_manager.get_skill_tools(
                        skill_name
                    )
                    logger.info(
                        "Loaded tools for skill",
                        extra={
                            "data": {
                                "skill": skill_name,
                                "tools": [t.name for t in skill_tools_cache[skill_name]],
                            }
                        },
                    )
                except Exception as e:
                    logger.error(
                        "Failed to load tools for skill",
                        extra={"data": {"skill": skill_name, "error": str(e)}},
                    )
                    continue
            all_tools.extend(skill_tools_cache[skill_name])

        return all_tools

    async def agent_node(state: SkillAwareAgentState) -> dict:
        """LLM node with per-turn dynamic tool binding."""
        node_start = time.time()

        # Get tools for current state (including active skill tools)
        t0 = time.time()
        current_tools = await get_tools_for_state(state)
        log_timing("agent_node.get_tools_for_state", t0, {"count": len(current_tools)})

        # Bind tools for this turn
        t0 = time.time()
        llm_with_tools = llm.bind_tools(current_tools)
        log_timing("agent_node.bind_tools", t0, {"count": len(current_tools)})

        # Prepend system prompt to messages if not already present
        messages = list(state["messages"])
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages

        # Calculate approximate prompt size for logging
        prompt_chars = sum(len(str(m.content)) for m in messages)
        logger.info("Invoking LLM", extra={"data": {"messages_count": len(messages), "prompt_chars": prompt_chars}})

        # Invoke LLM
        t0 = time.time()
        response = await llm_with_tools.ainvoke(messages)
        log_timing("agent_node.llm_invoke", t0, {"messages": len(messages), "prompt_chars": prompt_chars})

        # Capture trace ID from LangChain instrumentation and attach to response metadata
        from utils.phoenix_integration import get_langchain_trace_id, get_phoenix_trace_url, is_phoenix_enabled
        trace_id = get_langchain_trace_id()
        if trace_id and is_phoenix_enabled():
            phoenix_url = get_phoenix_trace_url(trace_id)
            # Inject into response's additional_kwargs for persistence
            if not response.additional_kwargs:
                response.additional_kwargs = {}
            response.additional_kwargs["metadata"] = {
                **response.additional_kwargs.get("metadata", {}),
                "trace_id": trace_id,
                "phoenix_url": phoenix_url,
            }
            logger.debug("Attached Phoenix trace to response", extra={"data": {"trace_id": str(trace_id)}})

        log_timing("agent_node.total", node_start)
        return {"messages": [response]}

    def should_continue(state: SkillAwareAgentState) -> Literal["tools", "__end__"]:
        """Determine whether to continue to tools or end."""
        messages = state["messages"]
        last_message = messages[-1]

        # If the last message has tool calls, continue to tools node
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        return END

    async def tool_node_with_skill_state(
        state: SkillAwareAgentState,
    ) -> dict:
        """Execute tool calls and handle skill state updates."""
        messages = state["messages"]
        last_message = messages[-1]

        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {}

        # Get current tools (including skill tools)
        current_tools = await get_tools_for_state(state)

        # Create tool node with current tools
        tool_node = ToolNode(current_tools)

        # Execute tools
        result = await tool_node.ainvoke(state)

        # Check for skill activation/deactivation in tool calls
        # and update active_skills state accordingly
        active_skills = dict(state.get("active_skills", {}))
        skills_changed = False

        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")

            if tool_name == "enable_skill":
                skill_name = tool_call.get("args", {}).get("skill_name", "")
                if skill_name and skill_name in skill_manager.list_skills():
                    # Calculate turn number (count of AI messages)
                    turn_number = sum(
                        1 for m in messages if isinstance(m, AIMessage)
                    )

                    # Get skill tools for activation metadata
                    try:
                        skill_def = await skill_manager.load_skill(skill_name)
                        tool_names = [
                            f"{skill_name}__{t.name}" for t in skill_def.tools
                        ]
                    except Exception:
                        tool_names = []

                    active_skills[skill_name] = {
                        "activated_at_turn": turn_number,
                        "tools": tool_names,
                    }
                    skills_changed = True
                    logger.info(
                        "Skill activated in state",
                        extra={"data": {"skill": skill_name, "turn": turn_number}},
                    )

            elif tool_name == "disable_skill":
                skill_name = tool_call.get("args", {}).get("skill_name", "")
                if skill_name and skill_name in active_skills:
                    del active_skills[skill_name]
                    # Also remove from cache to free memory
                    if skill_name in skill_tools_cache:
                        del skill_tools_cache[skill_name]
                    skills_changed = True
                    logger.info(
                        "Skill deactivated in state",
                        extra={"data": {"skill": skill_name}},
                    )

        # Return result with updated active_skills if changed
        if skills_changed:
            result["active_skills"] = active_skills

        return result

    # Build the graph
    graph = StateGraph(SkillAwareAgentState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node_with_skill_state)

    # Add edges
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    # Compile with checkpointer
    t0 = time.time()
    agent = graph.compile(checkpointer=checkpointer)
    log_timing("graph_compile", t0)

    log_timing("create_chat_agent_total", agent_start, {"tools": len(base_tools)})
    logger.info(
        "Created skill-aware chat agent",
        extra={"data": {"base_tools_count": len(base_tools), "checkpointer_type": type(checkpointer).__name__}},
    )
    return agent


def clear_chat_agent_cache():
    """Clear all component caches to force reload with updated tools/prompts."""
    global _cached_tools, _cached_llm
    _cached_tools = None
    _cached_llm = None
    
    # Also clear the system prompt cache
    from .prompts import clear_system_prompt_cache
    clear_system_prompt_cache()
    
    # Clear tool permissions cache
    from utils.tool_permissions_manager import permission_config
    permission_config.clear_permissions_cache()
    
    logger.info("All component caches cleared - next agent creation will reload everything (tools, prompts, and permissions)")

