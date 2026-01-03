"""
Nova Memory Business Logic

Core functions for memory operations - search, add, and retrieval.
These functions provide the business logic for Nova's knowledge graph operations.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

from memory import graphiti_manager
from memory.graphiti_manager import MemorySearchError, MemoryAddError
from memory.entity_types import NOVA_ENTITY_TYPES
from config import settings

logger = logging.getLogger(__name__)


async def search_memory(query: str, limit: int = None, group_id: str = None) -> Dict[str, Any]:
    """
    Search the knowledge graph for relevant information.
    
    Args:
        query: Natural language search query
        limit: Maximum results to return (default from user settings)
        group_id: Memory partition (default from settings)
        
    Returns:
        Dict with success status, results, and metadata
        
    Raises:
        MemorySearchError: When search operation fails
    """
    try:
        client = await graphiti_manager.get_graphiti_client()
        
        # Get user settings for memory search limit
        if limit is None:
            from database.database import db_manager
            from database.database import UserSettingsService
            
            try:
                memory_settings = await UserSettingsService.get_memory_settings()
                limit = memory_settings.get("memory_search_limit", 10)  # Default from database schema
            except Exception:
                limit = 10  # Default from database schema
        
        search_limit = limit
        search_group_id = group_id or settings.MEMORY_GROUP_ID
        
        results = await client.search(
            query=query,
            group_ids=[search_group_id],
            num_results=search_limit
        )
        
        # Format results for consumption
        formatted_results = [
            {
                "fact": edge.fact,
                "uuid": edge.uuid,
                "source_node": edge.source_node_uuid,
                "target_node": edge.target_node_uuid,
                "created_at": edge.created_at.isoformat() if edge.created_at else None
            }
            for edge in results
        ]
        
        logger.debug(f"Memory search for '{query}' returned {len(formatted_results)} results")
        
        return {
            "success": True,
            "results": formatted_results,
            "count": len(formatted_results),
            "query": query,
            "limit": search_limit
        }
        
    except Exception as e:
        logger.warning(f"Memory search failed for query '{query}': {str(e)}")
        raise MemorySearchError(f"Failed to search memory: {str(e)}")


async def add_memory(
    content: str, 
    source_description: str, 
    group_id: str = None,
    reference_time: datetime = None
) -> Dict[str, Any]:
    """
    Add new information to the knowledge graph.
    
    Args:
        content: Text content to analyze and store
        source_description: Description of the information source
        group_id: Memory partition (default from settings)
        reference_time: When the information was created (default: now)
        
    Returns:
        Dict with success status and created entities/relationships
        
    Raises:
        MemoryAddError: When add operation fails
    """
    try:
        client = await graphiti_manager.get_graphiti_client()
        
        add_group_id = group_id or settings.MEMORY_GROUP_ID
        add_reference_time = reference_time or datetime.now(timezone.utc)
        
        # Sanitize content to prevent API issues
        sanitized_content = content.strip()
        if len(sanitized_content) > 100000:  # Limit content length
            sanitized_content = sanitized_content[:100000] + "... [truncated]"
        
        result = await client.add_episode(
            name=f"Memory: {source_description}",
            episode_body=sanitized_content,
            source_description=source_description,
            reference_time=add_reference_time,
            group_id=add_group_id,
            entity_types=NOVA_ENTITY_TYPES  # Suggested types - Graphiti can create new ones dynamically
        )
        
        # Format response
        entities = [
            {
                "name": node.name,
                "labels": node.labels,
                "uuid": node.uuid
            }
            for node in result.nodes
        ]
        
        logger.info(f"Added memory episode: {result.episode.uuid}, "
                   f"created {len(result.nodes)} entities, {len(result.edges)} relationships")
        
        return {
            "success": True,
            "episode_uuid": result.episode.uuid,
            "nodes_created": len(result.nodes),
            "edges_created": len(result.edges),
            "entities": entities
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle specific Gemini API errors more gracefully
        if "Failed to parse structured response" in error_msg:
            logger.warning(f"Gemini API structured response failed for content: '{content[:100]}...'. "
                          f"This might be due to content filtering or API limits. Error: {error_msg}")
            
            # Return a partial success response rather than failing completely
            return {
                "success": False,
                "error": "memory_api_failure",
                "message": "Memory addition failed due to API parsing error",
                "episode_uuid": None,
                "nodes_created": 0,
                "edges_created": 0,
                "entities": []
            }
        
        logger.error(f"Failed to add memory content '{content[:100]}...': {error_msg}")
        raise MemoryAddError(f"Failed to add memory: {error_msg}")


async def get_recent_episodes(limit: int = 10, group_id: str = None) -> Dict[str, Any]:
    """Get recent memory episodes for debugging/management."""
    try:
        client = await graphiti_manager.get_graphiti_client()
        search_group_id = group_id or settings.MEMORY_GROUP_ID
        
        episodes = await client.retrieve_episodes(
            reference_time=datetime.now(timezone.utc),
            last_n=limit,
            group_ids=[search_group_id]
        )
        
        formatted_episodes = [
            {
                "uuid": ep.uuid,
                "name": ep.name,
                "source_description": ep.source_description,
                "created_at": ep.created_at.isoformat(),
                "content_preview": ep.content[:100] + "..." if len(ep.content) > 100 else ep.content
            }
            for ep in episodes
        ]
        
        return {
            "success": True,
            "episodes": formatted_episodes,
            "count": len(formatted_episodes)
        }
        
    except Exception as e:
        logger.warning(f"Failed to retrieve recent episodes: {str(e)}")
        raise MemorySearchError(f"Failed to retrieve episodes: {str(e)}") 