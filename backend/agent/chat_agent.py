"""
Nova LangGraph Chat Agent

A modern LangGraph chat agent that integrates with Nova's tools following current best practices.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Any

from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from tools import get_all_tools
from config import settings
from .llm import create_llm
from mcp_client import mcp_manager

logger = logging.getLogger(__name__)


# Cache for tools to avoid repeated fetching
_cached_tools: Optional[List[Any]] = None


async def get_all_tools_with_mcp() -> List[Any]:
    """Get all tools including both local Nova tools and external MCP tools.
    
    Uses caching to avoid repeated tool fetching.
    """
    global _cached_tools
    
    if _cached_tools is not None:
        return _cached_tools
    
    # Get local Nova tools
    local_tools = get_all_tools()
    
    # Get MCP tools from external servers
    try:
        _, mcp_tools = await mcp_manager.get_client_and_tools()
        logger.info(f"Loaded {len(mcp_tools)} MCP tools")
    except Exception as e:
        logger.warning(f"Could not fetch MCP tools: {e}")
        mcp_tools = []
    
    # Combine and cache tools
    _cached_tools = local_tools + mcp_tools
    logger.info(f"Total tools available: {len(local_tools)} local + {len(mcp_tools)} MCP = {len(_cached_tools)} total")
    
    return _cached_tools


async def create_checkpointer():
    """Create checkpointer based on configuration.
    
    Returns checkpointer based on configuration:
    - If FORCE_MEMORY_CHECKPOINTER is True, always returns MemorySaver
    - Otherwise, returns PostgreSQL checkpointer if configured
    - Falls back to MemorySaver if PostgreSQL is not available
    """
    # Check if we should force memory checkpointer for development/debugging
    if settings.FORCE_MEMORY_CHECKPOINTER:
        logger.info("Forcing MemorySaver checkpointer (FORCE_MEMORY_CHECKPOINTER=True)")
        return MemorySaver()
    
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
            logger.info("Falling back to MemorySaver")
            return MemorySaver()
    else:
        logger.info("No DATABASE_URL configured, using in-memory checkpointer")
        return MemorySaver()


async def create_chat_agent(checkpointer=None):
    """Create a LangGraph chat agent using modern patterns.
    
    Uses create_react_agent prebuilt which is the current best practice.
    """
    # Create LLM
    llm = create_llm()
    
    # Get all tools
    tools = await get_all_tools_with_mcp()
    
    # Create checkpointer if not provided
    if checkpointer is None:
        checkpointer = await create_checkpointer()
    
    # Import system prompt
    from agent.prompts import NOVA_SYSTEM_PROMPT
    system_prompt = NOVA_SYSTEM_PROMPT

    # Create agent using modern create_react_agent pattern
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
        checkpointer=checkpointer
    )
    
    logger.info(f"Created chat agent with {len(tools)} tools")
    return agent


def clear_tools_cache():
    """Clear the tools cache to force reload on next access."""
    global _cached_tools
    _cached_tools = None
    logger.info("Tools cache cleared") 