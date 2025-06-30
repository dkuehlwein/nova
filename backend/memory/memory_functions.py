"""
Nova Memory Business Logic

Core functions for memory operations - search, add, and retrieval.
These functions provide the business logic for Nova's knowledge graph operations.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

from memory.graphiti_manager import graphiti_manager, MemorySearchError, MemoryAddError
from memory.entity_types import NOVA_ENTITY_TYPES
from config import settings

logger = logging.getLogger(__name__)


async def search_memory(query: str, limit: int = None, group_id: str = None) -> Dict[str, Any]:
    """
    Search the knowledge graph for relevant information.
    
    Args:
        query: Natural language search query
        limit: Maximum results to return (default from settings)
        group_id: Memory partition (default from settings)
        
    Returns:
        Dict with success status, results, and metadata
        
    Raises:
        MemorySearchError: When search operation fails
    """
    try:
        client = await graphiti_manager.get_client()
        
        search_limit = limit or settings.MEMORY_SEARCH_LIMIT
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
        client = await graphiti_manager.get_client()
        
        add_group_id = group_id or settings.MEMORY_GROUP_ID
        add_reference_time = reference_time or datetime.now(timezone.utc)
        
        result = await client.add_episode(
            name=f"Memory: {source_description}",
            episode_body=content,
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
        logger.error(f"Failed to add memory content '{content[:100]}...': {str(e)}")
        raise MemoryAddError(f"Failed to add memory: {str(e)}")


async def get_recent_episodes(limit: int = 10, group_id: str = None) -> Dict[str, Any]:
    """Get recent memory episodes for debugging/management."""
    try:
        client = await graphiti_manager.get_client()
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