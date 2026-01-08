"""
Nova Memory Tools

LangChain tools for agent memory operations. These tools wrap the memory business logic
functions and provide structured interfaces for the agent.
"""

import logging
from typing import List
from langchain_core.tools import StructuredTool

from memory.memory_functions import search_memory, add_memory, MemorySearchError, MemoryAddError

logger = logging.getLogger(__name__)


async def search_memory_tool(query: str) -> str:
    """
    Search stored information about people, projects, or past conversations to find relevant context.

    Use this tool when you need background information about people or projects.

    NOTE: Memory is automatically searched on the first message of each conversation.
    """
    try:
        result = await search_memory(query)
        
        if result["success"] and result["results"]:
            facts = "\n".join([f"- {r['fact']}" for r in result["results"]])
            return f"Found {result['count']} relevant memories:\n{facts}"
        else:
            return "No relevant memories found for your query."
            
    except MemorySearchError as e:
        logger.warning(f"Memory search failed: {e}")
        return "Memory search is currently unavailable. Proceeding without historical context."


async def add_memory_tool(content: str, source_description: str = "Agent Memory") -> str:
    """
    Add new information to your memory for future reference.
    
    Use this tool to store important facts about people, projects, relationships, and outcomes.
    """
    try:
        result = await add_memory(content, source_description)
        
        if result["success"]:
            entities_str = ", ".join([
                f"{e['name']} ({', '.join(e['labels'])})" 
                for e in result["entities"]
            ])
            return (f"Memory stored successfully. Created {result['nodes_created']} entities "
                   f"and {result['edges_created']} relationships. "
                   f"Entities: {entities_str}")
        else:
            return "Failed to store memory."
            
    except MemoryAddError as e:
        logger.error(f"Memory add failed with MemoryAddError: {e}")
        return "Memory storage is currently unavailable. Information not persisted."
    except Exception as e:
        logger.error(f"Memory add failed with unexpected error: {type(e).__name__}: {e}")
        return "Memory storage is currently unavailable. Information not persisted."


def get_memory_tools() -> List[StructuredTool]:
    """Get memory tools for the agent."""
    return [
        StructuredTool.from_function(
            func=search_memory_tool,
            name="search_memory",
            coroutine=search_memory_tool
        ),
        StructuredTool.from_function(
            func=add_memory_tool,
            name="add_memory",
            coroutine=add_memory_tool
        )
    ] 