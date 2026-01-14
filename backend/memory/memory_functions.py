"""
Nova Memory Business Logic

Core functions for memory operations - search, add, and retrieval.
These functions provide the business logic for Nova's knowledge graph operations.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from memory import graphiti_manager
from memory.graphiti_manager import MemorySearchError, MemoryAddError
from memory.entity_types import (
    NOVA_ENTITY_TYPES,
    NOVA_EDGE_TYPE_MAP,
    NOVA_EXTRACTION_INSTRUCTIONS,
)
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
            entity_types=NOVA_ENTITY_TYPES,
            edge_type_map=NOVA_EDGE_TYPE_MAP,
            custom_extraction_instructions=NOVA_EXTRACTION_INSTRUCTIONS,
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


async def get_recent_facts(limit: int = 5, group_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the most recent facts/edges from the knowledge graph.

    Unlike search, this returns facts ordered by creation time (newest first)
    regardless of semantic relevance.

    Args:
        limit: Maximum number of facts to return (default 5)
        group_id: Memory partition (default from settings)

    Returns:
        Dict with success status and list of recent facts

    Raises:
        MemorySearchError: When retrieval fails
    """
    try:
        client = await graphiti_manager.get_graphiti_client()
        driver = client.driver
        search_group_id = group_id or settings.MEMORY_GROUP_ID

        async with driver.session() as session:
            # Query edges ordered by created_at descending
            # Use directed pattern (-[r]->)  to avoid returning each edge twice
            result = await session.run(
                """
                MATCH ()-[r:RELATES_TO]->()
                WHERE r.group_id = $group_id
                RETURN r.uuid as uuid, r.fact as fact,
                       r.source_node_uuid as source_node,
                       r.target_node_uuid as target_node,
                       r.created_at as created_at
                ORDER BY r.created_at DESC
                LIMIT $limit
                """,
                group_id=search_group_id,
                limit=limit
            )
            records = await result.data()

        formatted_results = [
            {
                "fact": record["fact"],
                "uuid": record["uuid"],
                "source_node": record["source_node"],
                "target_node": record["target_node"],
                "created_at": record["created_at"].isoformat() if record["created_at"] else None
            }
            for record in records
        ]

        logger.debug(f"Retrieved {len(formatted_results)} recent facts")

        return {
            "success": True,
            "results": formatted_results,
            "count": len(formatted_results),
            "limit": limit
        }

    except Exception as e:
        logger.warning(f"Failed to retrieve recent facts: {str(e)}")
        raise MemorySearchError(f"Failed to retrieve recent facts: {str(e)}")


class MemoryDeleteError(Exception):
    """Raised when memory deletion fails."""
    pass


async def delete_episode(episode_uuid: str) -> Dict[str, Any]:
    """
    Delete a memory episode and its associated nodes/edges.

    Args:
        episode_uuid: UUID of the episode to delete

    Returns:
        Dict with success status

    Raises:
        MemoryDeleteError: When delete operation fails
    """
    try:
        client = await graphiti_manager.get_graphiti_client()

        await client.remove_episode(episode_uuid)

        logger.info(f"Deleted memory episode: {episode_uuid}")

        return {
            "success": True,
            "deleted_uuid": episode_uuid
        }

    except Exception as e:
        logger.error(f"Failed to delete episode {episode_uuid}: {str(e)}")
        raise MemoryDeleteError(f"Failed to delete episode: {str(e)}")


async def delete_fact(fact_uuid: str) -> Dict[str, Any]:
    """
    Delete a specific fact/edge from the knowledge graph.

    This directly removes the edge from Neo4j without affecting episodes.
    Use this to clean up corrupted or incorrect facts.

    Args:
        fact_uuid: UUID of the fact/edge to delete

    Returns:
        Dict with success status

    Raises:
        MemoryDeleteError: When delete operation fails
    """
    try:
        client = await graphiti_manager.get_graphiti_client()
        driver = client.driver

        async with driver.session() as session:
            # Delete the edge by UUID
            # Use directed pattern to match the edge once
            result = await session.run(
                """
                MATCH ()-[r:RELATES_TO {uuid: $uuid}]->()
                DELETE r
                RETURN count(r) as deleted
                """,
                uuid=fact_uuid
            )
            record = await result.single()
            deleted_count = record["deleted"] if record else 0

        if deleted_count > 0:
            logger.info(f"Deleted fact/edge: {fact_uuid}")
            return {
                "success": True,
                "deleted_uuid": fact_uuid,
                "deleted_count": deleted_count
            }
        else:
            logger.warning(f"No fact found with UUID: {fact_uuid}")
            return {
                "success": False,
                "error": "not_found",
                "message": f"No fact found with UUID: {fact_uuid}"
            }

    except Exception as e:
        logger.error(f"Failed to delete fact {fact_uuid}: {str(e)}")
        raise MemoryDeleteError(f"Failed to delete fact: {str(e)}") 