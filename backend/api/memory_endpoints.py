"""
Memory API Endpoints

FastAPI endpoints for memory/knowledge graph operations.
Provides REST API access to Nova's memory functionality.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Optional

from memory.memory_functions import (
    search_memory, add_memory, get_recent_episodes, get_recent_facts,
    delete_episode, delete_fact,
    MemorySearchError, MemoryAddError, MemoryDeleteError
)
from models.memory import (
    MemorySearchRequest, MemorySearchResponse,
    MemoryAddRequest, MemoryAddResponse,
    MemoryEpisodesResponse, MemoryDeleteResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/memory/search", response_model=MemorySearchResponse)
async def search_memory_api(request: MemorySearchRequest):
    """Search the knowledge graph for relevant information."""
    try:
        result = await search_memory(
            query=request.query,
            limit=request.limit,
            group_id=request.group_id
        )
        
        return MemorySearchResponse(
            results=result["results"],
            count=result["count"],
            query=result["query"],
            success=True
        )
        
    except MemorySearchError as e:
        logger.warning(f"API memory search failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in memory search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/memory/add", response_model=MemoryAddResponse)
async def add_memory_api(request: MemoryAddRequest):
    """Add new information to the knowledge graph."""
    try:
        result = await add_memory(
            content=request.content,
            source_description=request.source_description,
            group_id=request.group_id
        )
        
        return MemoryAddResponse(
            episode_uuid=result["episode_uuid"],
            nodes_created=result["nodes_created"],
            edges_created=result["edges_created"],
            entities=result["entities"],
            success=True
        )
        
    except MemoryAddError as e:
        logger.warning(f"API memory add failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in memory add: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/memory/episodes", response_model=MemoryEpisodesResponse)
async def get_episodes_api(limit: int = 10, group_id: Optional[str] = None):
    """Get recent memory episodes for management/debugging."""
    try:
        result = await get_recent_episodes(limit=limit, group_id=group_id)
        
        return MemoryEpisodesResponse(
            episodes=result["episodes"],
            count=result["count"],
            success=True
        )
        
    except MemorySearchError as e:
        logger.warning(f"API episodes retrieval failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in episodes retrieval: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/memory/recent", response_model=MemorySearchResponse)
async def get_recent_facts_api(limit: int = 5, group_id: Optional[str] = None):
    """Get the most recent facts from the knowledge graph."""
    try:
        result = await get_recent_facts(limit=limit, group_id=group_id)

        return MemorySearchResponse(
            results=result["results"],
            count=result["count"],
            query="",  # No query for recent facts
            success=True
        )

    except MemorySearchError as e:
        logger.warning(f"API recent facts retrieval failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in recent facts retrieval: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/memory/episodes/{episode_uuid}", response_model=MemoryDeleteResponse)
async def delete_episode_api(episode_uuid: str):
    """Delete a memory episode and its associated data."""
    try:
        result = await delete_episode(episode_uuid)
        return MemoryDeleteResponse(**result)
    except MemoryDeleteError as e:
        logger.warning(f"API memory episode delete failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in memory episode delete: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/memory/facts/{fact_uuid}", response_model=MemoryDeleteResponse)
async def delete_fact_api(fact_uuid: str):
    """Delete a specific fact/edge from the knowledge graph."""
    try:
        result = await delete_fact(fact_uuid)
        return MemoryDeleteResponse(**result)
    except MemoryDeleteError as e:
        logger.warning(f"API memory fact delete failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in memory fact delete: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 