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
    
    Returns PostgreSQL checkpointer if configured, otherwise MemorySaver.
    """
    if settings.DATABASE_URL:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool
            
            logger.info("Attempting to create PostgreSQL checkpointer")
            
            # For now, return MemorySaver as PostgreSQL requires proper connection pool setup
            # TODO: Implement proper PostgreSQL checkpointer with FastAPI lifespan management
            logger.warning("PostgreSQL checkpointer requires connection pool management - using MemorySaver")
            return MemorySaver()
                
        except ImportError:
            logger.warning("PostgreSQL checkpointer not available - install langgraph-checkpoint-postgres")
            return MemorySaver()
        except Exception as e:
            logger.error(f"Error creating PostgreSQL checkpointer: {e}")
            return MemorySaver()
    else:
        logger.info("Using in-memory checkpointer")
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
    
    # System prompt for Nova
    system_prompt = """You are Nova, an AI assistant for managers. You help with:

1. **Task Management**: Creating, updating, organizing tasks in the kanban board
2. **People Management**: Managing team members and contact information  
3. **Project Management**: Organizing and tracking projects
4. **Email Management**: Reading, sending, and managing emails via Gmail

You have access to tools that let you:
- Create and manage tasks with proper relationships
- Track people and their roles
- Organize projects
- Add comments and updates to tasks
- Send and read emails through Gmail
- Manage your inbox and email threads

Be helpful, professional, and action-oriented. When users ask you to do something, use the appropriate tools to accomplish their requests. Always confirm actions you've taken and provide clear summaries of what you've accomplished."""

    # Create agent using modern create_react_agent pattern
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
        checkpointer=checkpointer
    )
    
    logger.info(f"Created chat agent with {len(tools)} tools")
    return agent


# Legacy functions for backward compatibility
async def create_async_graph():
    """Create and compile the LangGraph chat agent.
    
    Legacy function - use create_chat_agent instead.
    """
    logger.warning("create_async_graph is deprecated - use create_chat_agent instead")
    return await create_chat_agent()


async def create_async_graph_with_checkpointer(checkpointer):
    """Create async graph with specific checkpointer.
    
    Legacy function - use create_chat_agent instead.
    """
    logger.warning("create_async_graph_with_checkpointer is deprecated - use create_chat_agent instead")
    return await create_chat_agent(checkpointer=checkpointer)


def clear_tools_cache():
    """Clear the tools cache to force reload on next access."""
    global _cached_tools
    _cached_tools = None
    logger.info("Tools cache cleared") 