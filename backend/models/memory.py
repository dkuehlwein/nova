"""
Memory Domain Models

Pydantic models for memory/knowledge graph operations in Nova.
These models define the API contracts for memory endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class MemorySearchRequest(BaseModel):
    """Request model for memory search operations."""
    query: str = Field(..., description="Natural language search query")
    limit: Optional[int] = Field(10, ge=1, le=50, description="Maximum results to return")
    group_id: Optional[str] = Field(None, description="Memory partition identifier")


class MemoryResult(BaseModel):
    """Individual memory search result."""
    fact: str = Field(..., description="Human-readable relationship fact")
    uuid: str = Field(..., description="Unique identifier")
    source_node: str = Field(..., description="Source node UUID")
    target_node: str = Field(..., description="Target node UUID")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class MemorySearchResponse(BaseModel):
    """Response model for memory search operations."""
    results: List[MemoryResult]
    count: int
    query: str
    success: bool = True


class MemoryAddRequest(BaseModel):
    """Request model for adding memory."""
    content: str = Field(..., description="Text content to analyze and store")
    source_description: str = Field(..., description="Description of information source")
    group_id: Optional[str] = Field(None, description="Memory partition identifier")


class MemoryEntity(BaseModel):
    """Entity created in memory."""
    name: str
    labels: List[str]
    uuid: str


class MemoryAddResponse(BaseModel):
    """Response model for memory add operations."""
    episode_uuid: str
    nodes_created: int
    edges_created: int
    entities: List[MemoryEntity]
    success: bool = True


class MemoryEpisode(BaseModel):
    """Memory episode summary."""
    uuid: str
    name: str
    source_description: str
    created_at: str
    content_preview: str


class MemoryEpisodesResponse(BaseModel):
    """Response model for episodes list."""
    episodes: List[MemoryEpisode]
    count: int
    success: bool = True


class MemoryHealthResponse(BaseModel):
    """Response model for memory health check."""
    status: str = Field(..., description="Overall health status")
    neo4j_connected: bool = Field(..., description="Neo4j connection status")
    search_functional: Optional[bool] = Field(None, description="Search functionality status")
    error: Optional[str] = Field(None, description="Error message if unhealthy") 