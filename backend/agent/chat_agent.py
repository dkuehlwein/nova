"""
Nova LangGraph Chat Agent

A modern LangGraph chat agent that integrates with Nova's tools following current best practices.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Any

from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

from tools import get_all_tools
from config import settings
from .llm import create_llm
from .prompts import get_nova_system_prompt
from mcp_client import mcp_manager

logger = logging.getLogger(__name__)


# Cache for tools to avoid repeated fetching
_cached_tools: Optional[List[Any]] = None

# Cache for agent components (separate from checkpointer)
_cached_llm = None
_cached_prompt = None


async def get_all_tools_with_mcp(use_cache=True) -> List[Any]:
    """Get all tools including both local Nova tools and external MCP tools.
    
    Args:
        use_cache: If True, use cached tools; if False, reload tools
        
    Returns:
        List of all available tools (cached or fresh)
    """
    global _cached_tools
    
    if not use_cache:
        _cached_tools = None
        logger.info("Tools cache cleared for reload")
    
    if _cached_tools is not None:
        return _cached_tools
    
    # Get local Nova tools
    local_tools = get_all_tools()
    
    # Get MCP tools from external servers (respects enabled/disabled state)
    try:
        mcp_tools = await mcp_manager.get_tools()
        logger.info(f"Loaded {len(mcp_tools)} MCP tools from enabled servers")
    except Exception as e:
        logger.warning(f"Could not fetch MCP tools: {e}")
        mcp_tools = []
    
    # Combine and cache tools
    _cached_tools = local_tools + mcp_tools
    logger.info(f"Total tools available: {len(local_tools)} local + {len(mcp_tools)} MCP = {len(_cached_tools)} total")
    
    return _cached_tools


async def get_llm():
    """Get cached LLM or create new one if not cached."""
    global _cached_llm
    
    if _cached_llm is None:
        _cached_llm = create_llm()
        logger.debug("LLM created and cached for reuse")
    
    return _cached_llm

async def create_checkpointer():
    """Create checkpointer based on configuration.
    
    Returns checkpointer based on configuration:
    - If FORCE_MEMORY_CHECKPOINTER is True, always returns MemorySaver
    - Otherwise, returns PostgreSQL checkpointer if configured
    - Falls back to MemorySaver if PostgreSQL is not available
    """
    # Check if we should force memory checkpointer for development/debugging
    if settings.FORCE_MEMORY_CHECKPOINTER:
        logger.info("Forcing InMemorySaver checkpointer (FORCE_MEMORY_CHECKPOINTER=True)")
        return InMemorySaver()
    
    # Try PostgreSQL if DATABASE_URL is configured
    if settings.DATABASE_URL:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool
            
            logger.info("Creating PostgreSQL checkpointer")
            
            # Create connection pool with open=False to avoid deprecated constructor warning
            pool = AsyncConnectionPool(settings.DATABASE_URL, open=False)
            await pool.open()
            
            checkpointer = AsyncPostgresSaver(pool)
            
            # Setup tables if needed
            await checkpointer.setup()
            
            logger.info("PostgreSQL checkpointer created successfully")
            return checkpointer
                
        except Exception as e:
            logger.error(f"Error creating PostgreSQL checkpointer: {e}")
            logger.info("Falling back to InMemorySaver")
            return InMemorySaver()
    else:
        logger.info("No DATABASE_URL configured, using in-memory checkpointer")
        return InMemorySaver()


async def create_chat_agent(checkpointer=None, use_cache=True):
    """Create LangGraph chat agent with cached components.
    
    Args:
        checkpointer: Optional checkpointer to use for conversation state
        use_cache: If True, use cached components; if False, reload everything
    
    Returns:
        LangGraph chat agent with current tools/prompt and specified checkpointer
        
    Notes:
        - Always creates fresh agent instance (no agent instance caching)
        - Caches components (tools, LLM) separately from checkpointer
        - Every conversation gets latest tools/prompt when cache is cleared
        - Each conversation can have its own checkpointer for state management
    """
    # Clear component caches if requested
    if not use_cache:
        global _cached_tools, _cached_llm, _cached_prompt
        _cached_tools = None
        _cached_llm = None
        _cached_prompt = None
        logger.info("All component caches cleared - will reload everything")
    
    # Use default checkpointer if none provided
    if checkpointer is None:
        checkpointer = await create_checkpointer()
    
    logger.info("Creating chat agent", extra={
        "data": {
            "has_custom_checkpointer": checkpointer is not None,
            "use_cache": use_cache,
            "checkpointer_type": type(checkpointer).__name__
        }
    })
    
    # Get cached or fresh components
    llm = await get_llm()
    tools = await get_all_tools_with_mcp(use_cache=use_cache)
    system_prompt = get_nova_system_prompt()

    # Always create fresh agent instance with current components + checkpointer
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
        checkpointer=checkpointer
    )
    
    logger.info(f"Created chat agent with {len(tools)} tools and {type(checkpointer).__name__} checkpointer")
    return agent


def clear_chat_agent_cache():
    """Clear all component caches to force reload with updated tools/prompts."""
    global _cached_tools, _cached_llm, _cached_prompt
    _cached_tools = None
    _cached_llm = None
    _cached_prompt = None
    logger.info("All component caches cleared - next agent creation will reload everything")

