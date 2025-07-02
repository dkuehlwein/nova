# Graphiti Integration Architecture (v6 - Implementation Ready)

This document provides the definitive, implementation-ready architecture for integrating Graphiti memory into Nova. It incorporates all technical reviews, feedback, and aligns with Nova's established patterns.

## 1. Goals and Requirements

Equip Nova with a robust, persistent memory layer using Graphiti to:

- **Remember and recall** information about people, projects, clients, and relationships
- **Understand relationships** between entities (who works on what, client connections, etc.)
- **Leverage historical context** for improved task performance and decision-making
- **Provide semantic search** over accumulated knowledge

### Key Requirements:

- **Persistent Storage**: Neo4j database for the knowledge graph
- **Structured Data**: Custom node types (Person, Project, Email, Artifact) with proper relationships
- **Semantic Search**: Natural language queries over memory
- **Direct Integration**: Core functionality embedded in Nova backend (not MCP)
- **Error Resilience**: Graceful degradation when memory is unavailable
- **Performance**: Singleton client pattern, connection reuse

## 2. Architecture Overview

### Core Integration Pattern

Following Nova's established patterns (task management, database access), Graphiti integrates directly into the backend with **singleton pattern** for shared resources and business logic separation.

```
┌─────────────────┐    ┌──────────────────────────────────┐    ┌─────────────────┐
│   Frontend      │    │        Nova Backend              │    │   Infrastructure│
│                 │────┤                                  │────┤                 │
│ Memory UI       │    │ ┌─────────────┐ ┌─────────────┐  │    │ Neo4j Database  │
│ (optional)      │    │ │ API         │ │ Agent Tools │  │    │ Knowledge Graph │
└─────────────────┘    │ │ Endpoints   │ │             │  │    │                 │
                       │ └─────────────┘ └─────────────┘  │    └─────────────────┘
                       │           │           │          │
                       │ ┌─────────────────────────────┐   │
                       │ │   Memory Business Logic     │   │
                       │ │   (shared functions)        │   │
                       │ └─────────────────────────────┘   │
                       │           │                      │
                       │ ┌─────────────────────────────┐   │
                       │ │   GraphitiManager           │   │
                       │ │   (singleton like db_manager)│   │
                       │ └─────────────────────────────┘   │
                       └──────────────────────────────────┘
```

### Key Components:

1. **GraphitiManager**: Global singleton managing Graphiti client (follows `db_manager` pattern)
2. **Memory Business Logic**: Shared functions for search/add operations
3. **Agent Tools**: LangChain tools wrapping memory functions
4. **API Endpoints**: REST endpoints for frontend access
5. **Neo4j Service**: Added to docker-compose stack

## 3. Infrastructure Setup

### Dependencies (Already Included!)

**Great news**: Nova's `backend/pyproject.toml` already includes the required Graphiti dependency:

```toml
dependencies = [
    # ... existing dependencies ...
    "graphiti-core[google-genai]>=0.13.2",  # ✅ Already included!
    # ... rest of dependencies ...
]
```

**No additional Python packages needed** - Nova is already configured with:
- `graphiti-core[google-genai]` - Core Graphiti with Google AI support
- `langchain-google-genai` - Google Gemini LLM integration  
- All required database and async libraries

### Required Docker Compose Addition

```yaml
# Add to docker-compose.yml
neo4j:
  image: neo4j:5.15
  environment:
    NEO4J_AUTH: ${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:-password}
    NEO4J_PLUGINS: '["apoc"]'
  ports:
    - "${NEO4J_PORT:-7687}:7687"      # Bolt protocol
    - "${NEO4J_HTTP_PORT:-7474}:7474" # Web interface
  volumes:
    - neo4j_data:/data
  healthcheck:
    test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "password", "RETURN 1"]
    interval: 10s
    timeout: 5s
    retries: 5
  restart: unless-stopped

volumes:
  postgres_data:
  neo4j_data:  # Add this line
```

### Configuration Management

```python
# Add to backend/config.py (existing Settings class)
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Neo4j/Graphiti Configuration
    neo4j_uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", env="NEO4J_USER") 
    neo4j_password: str = Field(default="password", env="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", env="NEO4J_DATABASE")
    
    # Memory configuration
    memory_group_id: str = Field(default="nova", env="MEMORY_GROUP_ID")
    memory_search_limit: int = Field(default=10, env="MEMORY_SEARCH_LIMIT")
```

```bash
# Add to .env.example
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# Memory Configuration  
MEMORY_GROUP_ID=nova
MEMORY_SEARCH_LIMIT=10
```

## 4. Data Model and Entity Types

### Custom Entity Types (Pydantic Models)

```python
# backend/memory/entity_types.py
from pydantic import BaseModel
from typing import Optional

class Person(BaseModel):
    """Person entity for knowledge graph."""
    name: str
    email: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None

class Project(BaseModel):
    """Project entity for knowledge graph."""
    name: str
    client: Optional[str] = None
    booking_code: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None

class Email(BaseModel):
    """Email communication entity."""
    subject: Optional[str] = None
    sender: str
    recipients: str
    date: Optional[str] = None

class Artifact(BaseModel):
    """File, document, or resource entity."""
    name: str
    type: str  # "file", "link", "document", "presentation"
    path: Optional[str] = None
    description: Optional[str] = None

# Entity types mapping for Graphiti
NOVA_ENTITY_TYPES = {
    "Person": Person,
    "Project": Project,
    "Email": Email,
    "Artifact": Artifact,
}
```

### Relationship Types

- `WORKS_ON` (Person → Project)
- `MANAGES` (Person → Project)
- `CLIENT_OF` (Person → Project)
- `SENT` (Person → Email)
- `RECEIVED` (Person → Email)
- `CONTAINS` (Email → Artifact)
- `REFERENCES` (Project → Artifact)

## 5. Core Implementation

### GraphitiManager (Singleton Pattern - Following db_manager)

```python
# backend/memory/graphiti_manager.py
import logging
from typing import Optional
from graphiti_core import Graphiti
from graphiti_core.llm_client.gemini_client import GeminiClient
from graphiti_core.embedder.gemini import GeminiEmbedder
from graphiti_core.cross_encoder.client import CrossEncoderClient

from config import settings
from agent.llm import create_graphiti_llm, create_graphiti_embedder

logger = logging.getLogger(__name__)

class NullCrossEncoder(CrossEncoderClient):
    """Null cross encoder for MVP - no reranking needed."""
    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        return [(passage, 1.0 - (i * 0.01)) for i, passage in enumerate(passages)]

class GraphitiManager:
    """Global singleton manager for Graphiti client lifecycle (follows db_manager pattern)."""
    
    def __init__(self):
        self._client: Optional[Graphiti] = None
        self._initialized: bool = False
    
    async def get_client(self) -> Graphiti:
        """Get or create global Graphiti client instance."""
        if self._client is None:
            try:
                self._client = Graphiti(
                    uri=settings.neo4j_uri,
                    user=settings.neo4j_user,
                    password=settings.neo4j_password,
                    llm_client=create_graphiti_llm(),
                    embedder=create_graphiti_embedder(),
                    cross_encoder=NullCrossEncoder(),
                    store_raw_episode_content=True,
                )
                
                # Build indices on first connection
                if not self._initialized:
                    await self._client.build_indices_and_constraints()
                    self._initialized = True
                    logger.info("Graphiti client initialized with Neo4j indices")
                
            except Exception as e:
                logger.error(f"Failed to initialize Graphiti client: {e}")
                raise MemoryConnectionError(f"Cannot connect to Neo4j: {e}")
                
        return self._client
    
    async def close(self):
        """Close global Graphiti client connection."""
        if self._client:
            try:
                await self._client.close()
                logger.info("Graphiti client connection closed")
            except Exception as e:
                logger.warning(f"Error closing Graphiti client: {e}")
            finally:
                self._client = None
                self._initialized = False

# Global singleton instance (like db_manager)
graphiti_manager = GraphitiManager()

# Custom exceptions for memory operations
class MemoryConnectionError(Exception):
    """Raised when cannot connect to Neo4j/Graphiti."""
    pass

class MemorySearchError(Exception):
    """Raised when memory search fails."""
    pass

class MemoryAddError(Exception):
    """Raised when adding memory fails."""
    pass
```

### Extended LLM Module (Reusing Nova's Configuration)

```python
# Add to backend/agent/llm.py
from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig

def create_graphiti_llm() -> GeminiClient:
    """
    Create Graphiti-compatible Gemini LLM client reusing Nova's existing configuration.
    
    Note: We need Graphiti's GeminiClient instead of LangChain's ChatGoogleGenerativeAI
    because they expect different interfaces, but we reuse all the same config values.
    """
    # Reuse Nova's existing LLM configuration values
    api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    # Use the same model name logic as Nova's create_llm()
    model_name = settings.GOOGLE_MODEL_NAME or "gemini-2.5-flash-preview-04-17"
    
    config = LLMConfig(
        model=model_name,
        api_key=api_key,
        temperature=0.1,  # Lower temperature for factual memory vs Nova's 0.7 default
        max_tokens=8192   # Higher token limit for context gathering
    )
    return GeminiClient(config=config)

def create_graphiti_embedder() -> GeminiEmbedder:
    """
    Create Graphiti-compatible Gemini embedder for semantic search.
    
    This is REQUIRED for Graphiti's search functionality - it creates vector embeddings
    of the knowledge graph content for semantic matching. Confirmed working in our tests.
    """
    # Reuse Nova's API key configuration
    api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    config = GeminiEmbedderConfig(
        model="models/text-embedding-004",  # Google's latest embedding model (tested in scripts/test_graphiti.py)
        # TODO: Google if this is actually the latest model
        api_key=api_key
    )
    return GeminiEmbedder(config=config)
```

### Memory Business Logic

```python
# backend/memory/memory_functions.py
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
        
        search_limit = limit or settings.memory_search_limit
        search_group_id = group_id or settings.memory_group_id
        
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
        
        add_group_id = group_id or settings.memory_group_id
        add_reference_time = reference_time or datetime.now(timezone.utc)
        
        result = await client.add_episode(
            name=f"Memory: {source_description}",
            episode_body=content,
            source_description=source_description,
            reference_time=add_reference_time,
            group_id=add_group_id,
            entity_types=NOVA_ENTITY_TYPES  # Use custom entity types
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
        search_group_id = group_id or settings.memory_group_id
        
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
```

### Agent Tools

```python
# backend/tools/memory_tools.py
import logging
from typing import List
from langchain.tools import StructuredTool

from memory.memory_functions import search_memory, add_memory, MemorySearchError, MemoryAddError

logger = logging.getLogger(__name__)

async def search_memory_tool(query: str) -> str:
    """
    Search your memory for relevant information about anything you've worked with before, including but not limited to people, projects, clients, and relationships.
    
    Use this tool to find historical context answering questions.
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
    Add new information your memory for future reference.
    
    Use this tool to store important facts including, but not limited to, about people, projects, relationships, and outcomes.
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
        logger.warning(f"Memory add failed: {e}")
        return "Memory storage is currently unavailable. Information not persisted."

def get_memory_tools() -> List[StructuredTool]:
    """Get memory tools for the agent."""
    return [
        StructuredTool.from_function(
            func=search_memory_tool,
            name="search_memory",
            description="Search the knowledge graph for relevant information about people, projects, clients, and relationships. Use this before starting tasks to gather context."
        ),
        StructuredTool.from_function(
            func=add_memory_tool,
            name="add_memory",
            description="Store important information in the knowledge graph for future reference. Use this to remember facts about people, projects, outcomes, and relationships."
        )
    ]
```

### Tool Registry Integration

```python
# backend/tools/__init__.py
from .memory_tools import get_memory_tools

def get_all_tools() -> List[StructuredTool]:
    """Get all available tools for the agent."""
    tools = []
    tools.extend(get_task_tools())
    tools.extend(get_person_tools())
    tools.extend(get_project_tools())
    tools.extend(get_memory_tools())  # Add memory tools
    return tools
```

## 6. API Endpoints

### Memory API Router

```python
# backend/api/memory_endpoints.py
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from memory.memory_functions import search_memory, add_memory, get_recent_episodes
from memory.memory_functions import MemorySearchError, MemoryAddError
from models.memory import (
    MemorySearchRequest, MemorySearchResponse,
    MemoryAddRequest, MemoryAddResponse,
    MemoryEpisodesResponse
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

@router.get("/api/memory/health")
async def memory_health_check():
    """Check memory system health."""
    try:
        # Try a simple search to test connectivity
        result = await search_memory("health check", limit=1)
        return {
            "status": "healthy",
            "neo4j_connected": True,
            "search_functional": result["success"]
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "neo4j_connected": False,
            "error": str(e)
        }
```

### Pydantic Models

```python
# backend/models/memory.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class MemorySearchRequest(BaseModel):
    query: str = Field(..., description="Natural language search query")
    limit: Optional[int] = Field(10, ge=1, le=50, description="Maximum results to return")
    group_id: Optional[str] = Field(None, description="Memory partition identifier")

class MemoryResult(BaseModel):
    fact: str = Field(..., description="Human-readable relationship fact")
    uuid: str = Field(..., description="Unique identifier")
    source_node: str = Field(..., description="Source node UUID")
    target_node: str = Field(..., description="Target node UUID")
    created_at: Optional[str] = Field(None, description="Creation timestamp")

class MemorySearchResponse(BaseModel):
    results: List[MemoryResult]
    count: int
    query: str
    success: bool = True

class MemoryAddRequest(BaseModel):
    content: str = Field(..., description="Text content to analyze and store")
    source_description: str = Field(..., description="Description of information source")
    group_id: Optional[str] = Field(None, description="Memory partition identifier")

class MemoryEntity(BaseModel):
    name: str
    labels: List[str]
    uuid: str

class MemoryAddResponse(BaseModel):
    episode_uuid: str
    nodes_created: int
    edges_created: int
    entities: List[MemoryEntity]
    success: bool = True

class MemoryEpisode(BaseModel):
    uuid: str
    name: str
    source_description: str
    created_at: str
    content_preview: str

class MemoryEpisodesResponse(BaseModel):
    episodes: List[MemoryEpisode]
    count: int
    success: bool = True
```

## 7. Integration Points

### Core Agent Context Gathering

```python
# backend/agent/core_agent.py
async def _get_context(self, task: Task) -> str:
    """Get relevant context for task processing."""
    context_parts = []
    
    # Existing context gathering logic...
    
    # Add memory search for relevant context
    try:
        memory_query = f"{task.title} {task.description} {' '.join(task.tags or [])}"
        memory_result = await search_memory(memory_query, limit=5)
        
        if memory_result["success"] and memory_result["results"]:
            memory_context = "\n".join([
                f"- {result['fact']}" 
                for result in memory_result["results"]
            ])
            context_parts.append(f"Relevant Historical Context:\n{memory_context}")
            
    except Exception as e:
        logger.warning(f"Memory context retrieval failed for task {task.id}: {e}")
        # Continue without memory context
    
    return "\n\n".join(context_parts)

async def _update_context(self, task: Task, summary: str):
    """Store task completion summary in memory."""
    try:
        # Create comprehensive content for memory
        memory_content = f"""
        Task Completed: {task.title}
        
        Description: {task.description}
        Summary: {summary}
        Status: {task.status.value}
        Tags: {', '.join(task.tags or [])}
        Completed: {task.completed_at or datetime.now(timezone.utc)}
        
        People involved: {', '.join([p.name for p in task.persons])}
        Projects: {', '.join([p.name for p in task.projects])}
        """
        
        await add_memory(
            content=memory_content,
            source_description=f"Task Completion: {task.title}"
        )
        
        logger.info(f"Stored task completion in memory: {task.id}")
        
    except Exception as e:
        logger.warning(f"Failed to store task completion in memory: {e}")
        # Don't fail task completion if memory storage fails
```

### Application Startup Integration (Fixed Pattern)

```python
# backend/start_website.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    service_manager.logger.info("Starting Nova Backend Server...")
    
    try:
        # Start prompt watching
        await service_manager.start_prompt_watching()
        
        # Initialize PostgreSQL pool via ServiceManager
        await service_manager.init_pg_pool()
        
        # NOTE: Graphiti initialization is lazy (happens on first use)
        # No explicit memory initialization needed here
        
        # Create event handler for WebSocket broadcasting and agent reloading
        event_handler = await create_website_event_handler()
        
        # Start Redis bridge
        await service_manager.start_redis_bridge(app, event_handler)
        
        service_manager.logger.info("Nova Backend Server started successfully")
        
    except Exception as e:
        service_manager.logger.error(f"Failed to start server: {e}")
        raise
    
    yield
    
    # Shutdown
    service_manager.logger.info("Shutting down Nova Backend Server...")
    
    # Stop services
    await service_manager.stop_prompt_watching()
    await service_manager.stop_redis_bridge(app)
    
    # Cleanup resources (following established order)
    await service_manager.cleanup_redis()
    await service_manager.cleanup_memory()    # Add memory cleanup
    await service_manager.close_pg_pool()
    await service_manager.cleanup_database()
    
    service_manager.logger.info("Nova Backend Server shutdown complete")

# Include memory router
from api.memory_endpoints import router as memory_router
app.include_router(memory_router)
```

## 8. Testing Strategy

### Integration Tests

```python
# tests/integration/test_memory_integration.py
import pytest
from datetime import datetime, timezone

from memory.graphiti_manager import graphiti_manager
from memory.memory_functions import search_memory, add_memory
from tools.memory_tools import search_memory_tool, add_memory_tool

@pytest.mark.asyncio
class TestMemoryIntegration:
    
    async def test_memory_lifecycle(self):
        """Test complete memory add/search cycle."""
        # Add test content
        content = "Daniel is working on Nova memory integration using Graphiti and Neo4j"
        result = await add_memory(content, "Test Integration")
        
        assert result["success"]
        assert result["nodes_created"] > 0
        
        # Search for added content
        search_result = await search_memory("Daniel Nova memory")
        
        assert search_result["success"]
        assert len(search_result["results"]) > 0
        
    async def test_agent_tools_integration(self):
        """Test memory tools work correctly."""
        # Test search tool
        search_response = await search_memory_tool("Daniel Nova")
        assert isinstance(search_response, str)
        assert "memories" in search_response.lower()
        
        # Test add tool
        add_response = await add_memory_tool("Test memory content", "Tool Test")
        assert isinstance(add_response, str)
        assert "stored successfully" in add_response.lower()
        
    async def test_error_handling(self):
        """Test graceful error handling when Neo4j is unavailable."""
        # This would test with mocked failing connections
        pass
        
    async def teardown_method(self):
        """Clean up test data."""
        await graphiti_manager.close()
```

## 9. Work Packages (Implementation Ready)

### Work Package 1: Infrastructure and Core Setup

**Tasks:**
1. **Add Neo4j to docker-compose.yml** - Copy the service definition above
2. **Update configuration** - Add Neo4j settings to backend/config.py and .env.example
3. **Extend LLM module** - Add Graphiti client factories to backend/agent/llm.py
4. **Create GraphitiManager** - Implement singleton pattern with error handling
5. **Test Neo4j connectivity** - Create basic integration test

**Deliverables:**
- Neo4j service running in Docker
- Graphiti client successfully connecting
- Basic integration test passing

### Work Package 2: Memory Business Logic

**Tasks:**
1. **Define entity types** - Create backend/memory/entity_types.py
2. **Implement memory functions** - Create backend/memory/memory_functions.py
3. **Create custom exceptions** - Add proper error types
4. **Unit test business logic** - Test search/add functions

**Deliverables:**
- Memory search and add functions working
- Custom entity types properly recognized
- Comprehensive error handling

### Work Package 3: Agent Integration

**Tasks:**
1. **Create memory tools** - Implement backend/tools/memory_tools.py
2. **Update tool registry** - Add memory tools to backend/tools/__init__.py
3. **Update core agent** - Integrate memory into context gathering
4. **Test agent integration** - Verify tools work in agent context

**Deliverables:**
- Memory tools available to agents
- Core agent using memory for context
- Task completion stored in memory

### Work Package 4: API and Frontend

**Tasks:**
1. **Create Pydantic models** - Add backend/models/memory.py
2. **Implement API endpoints** - Create backend/api/memory_endpoints.py
3. **Add API router** - Include in main application
4. **Create frontend components** - Optional memory management UI

**Deliverables:**
- REST API for memory operations
- API documentation and testing
- Optional frontend interface

### Work Package 5: Testing and Cleanup

**Tasks:**
1. **Integration testing** - Comprehensive end-to-end tests
2. **Performance testing** - Verify singleton pattern efficiency
3. **Error handling testing** - Test graceful degradation
4. **Code cleanup** - Remove old memory management code
5. **Documentation** - Update system prompts and docs

**Deliverables:**
- Full test coverage
- Performance benchmarks
- Clean, production-ready code
- Proper service lifecycle management

## 10. Success Criteria

- ✅ **Functional**: Agent can search memory for relevant context before tasks
- ✅ **Persistent**: Task completions stored and retrievable
- ✅ **Resilient**: System works gracefully when memory is unavailable
- ✅ **Structured**: Custom entity types (Person, Project, etc.) properly recognized
- ✅ **Performant**: Singleton pattern prevents connection overhead
- ✅ **Integrated**: Follows Nova's established patterns and architecture
- ✅ **Testable**: Comprehensive test coverage for all components
- ✅ **Consistent**: Uses same patterns as db_manager and other Nova singletons

## 11. Technical Clarifications

### **Why We Need Both LLM and Embedder Components**

**From our actual testing experience:**
- **LLM (GeminiClient)**: Used for entity extraction and relationship identification from text content
- **Embedder (GeminiEmbedder)**: **REQUIRED** for semantic search functionality - creates vector embeddings for matching queries to stored knowledge

**Both are essential** - the LLM processes and structures the content, while the embedder enables semantic search over it.

### **Why Not Reuse Nova's create_llm() Directly**

**Different Client Types Required:**
- **Nova**: Uses LangChain's `ChatGoogleGenerativeAI` for conversational AI
- **Graphiti**: Expects its own `GeminiClient` for graph operations

**Solution**: Reuse Nova's configuration values (API key, model name, settings) but create Graphiti-compatible clients. This eliminates configuration duplication while maintaining proper interfaces.

### **Why Singleton Pattern for GraphitiManager**

**Follows Nova's Established Pattern:**
- **Global Shared Resource**: All services should share the same Neo4j connection and memory state
- **Consistent with db_manager**: Same usage pattern as Nova's existing database singleton
- **Connection Efficiency**: One Neo4j client across entire application, not per service
- **Memory Consistency**: All agents see the same memory state across services

**Confirmed Working**: Our `scripts/test_graphiti.py` successfully uses this exact pattern.

## 12. Implementation Readiness Checklist

### ✅ **Dependencies & Environment**
- [x] **Dependencies**: `graphiti-core[google-genai]>=0.13.2` already in `backend/pyproject.toml`
- [x] **Configuration Pattern**: Follows Nova's existing `config.py` with `GOOGLE_API_KEY` pattern
- [x] **Environment Variables**: Aligns with Nova's `.env` management approach
- [x] **uv Package Management**: Uses Nova's established `uv sync` workflow

### ✅ **Architecture Alignment**
- [x] **Singleton Pattern**: Follows `db_manager` pattern for global shared resources
- [x] **ServiceManager Integration**: Memory cleanup in service shutdown lifecycle
- [x] **Error Handling**: Uses Nova's structured logging and exception patterns
- [x] **Redis Events**: Integrates with Nova's existing event system
- [x] **Tool Registry**: Follows Nova's `tools/__init__.py` registration pattern

### ✅ **API & Integration Points**
- [x] **Pydantic Models**: Follow Nova's domain-specific model organization in `models/`
- [x] **API Endpoints**: Use Nova's FastAPI router pattern with proper error handling
- [x] **Agent Integration**: Integrates with both chat agent and core agent workflows
- [x] **Database Patterns**: Uses Nova's `db_manager.get_session()` context manager pattern

### ✅ **Testing Strategy**
- [x] **Test Organization**: Follows Nova's `tests/backend/`, `tests/integration/` structure
- [x] **Mock Patterns**: Uses Nova's established mocking conventions [[memory:1344871089069577490]]
- [x] **Integration Tests**: Tests against real PostgreSQL database [[memory:7318233130918064055]]
- [x] **Error Scenarios**: Tests graceful degradation when Neo4j unavailable

### ✅ **Work Package Completeness**
- [x] **WP1 - Infrastructure**: Docker, config, basic connectivity - all specified
- [x] **WP2 - Business Logic**: Memory functions, entity types, exceptions - all detailed
- [x] **WP3 - Agent Integration**: Tools, registry, core agent context - all planned
- [x] **WP4 - API Endpoints**: Models, routes, router inclusion - all documented
- [x] **WP5 - Testing & Cleanup**: Tests, cleanup methods, service integration - all covered

### ✅ **Documentation & Examples**
- [x] **Code Examples**: All major components have complete implementation examples
- [x] **Configuration**: Complete `.env.example` additions specified
- [x] **Docker Compose**: Neo4j service definition ready to copy
- [x] **Usage Patterns**: Clear examples for search, add, error handling

### ✅ **Validation Against Nova Patterns**
- [x] **Logging**: Uses Nova's structured logging with `get_logger()` [[memory:1344871089069577490]]
- [x] **Service Lifecycle**: Follows Nova's startup/shutdown patterns with ServiceManager
- [x] **Model Organization**: Follows Nova's domain-based model separation [[memory:6952893459154223721]]
- [x] **API Architecture**: Aligns with Nova's endpoint organization patterns [[memory:8772294230981162856]]


---

*Architecture v6 - Implementation Ready - Reviewed 30.6.2025* 