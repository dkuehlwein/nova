"""
Graphiti Memory Manager for Nova

Manages the integration between Nova and Graphiti's graph-based memory system,
providing LLM and embedding services through LiteLLM routing.
"""

from typing import List, Optional

from graphiti_core import Graphiti
from graphiti_core.llm_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder import OpenAIEmbedder
from graphiti_core.embedder.openai import OpenAIEmbedderConfig
from graphiti_core.cross_encoder import CrossEncoderClient


def create_graphiti_llm() -> OpenAIClient:
    """
    Create OpenAI-compatible LLM client that routes through LiteLLM for memory operations.
    
    This enables Nova's memory system to leverage any LLM model available in LiteLLM
    while maintaining the same interface that Graphiti expects.
    """
    from utils.llm_factory import get_memory_llm_config
    
    llm_config = get_memory_llm_config()
    
    config = LLMConfig(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        temperature=llm_config["temperature"],
        max_tokens=llm_config["max_tokens"]
    )
    return OpenAIClient(config=config)


def create_graphiti_embedder() -> OpenAIEmbedder:
    """
    Create OpenAI-compatible embedder that routes through LiteLLM for semantic search.
    
    This enables Nova's memory system to use state-of-the-art open source embedding models
    like Qwen3-Embedding-4B (#1 MTEB multilingual leaderboard) via LiteLLM routing.
    """
    from utils.llm_factory import get_embedding_config
    
    embedding_config = get_embedding_config()
    
    config = OpenAIEmbedderConfig(
        embedding_model=embedding_config["embedding_model"],
        api_key=embedding_config["api_key"],
        base_url=embedding_config["base_url"],
        embedding_dim=embedding_config["embedding_dim"]
    )
    return OpenAIEmbedder(config=config)


class NullCrossEncoder(CrossEncoderClient):
    """
    No-op cross encoder for development.
    
    In production, this could be replaced with a proper cross-encoder service
    for enhanced relevance scoring.
    """
    
    def rank(self, query: str, messages: List[str]) -> List[int]:
        """Return messages in original order (no reranking)."""
        return list(range(len(messages)))


def create_graphiti_cross_encoder() -> CrossEncoderClient:
    """Create cross-encoder for message reranking (currently no-op)."""
    return NullCrossEncoder()


async def create_graphiti_client() -> Graphiti:
    """
    Create and configure Graphiti client for Nova's memory system.
    
    Returns:
        Configured Graphiti client with LiteLLM-routed LLM and embedding services
    """
    # Get Neo4j connection from config settings (Tier 2)
    from config import settings
    neo4j_uri = settings.NEO4J_URI
    neo4j_user = settings.NEO4J_USER  
    neo4j_password = settings.NEO4J_PASSWORD
    
    # Create Graphiti client with our LiteLLM-routed services
    client = Graphiti(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        llm_client=create_graphiti_llm(),
        embedder=create_graphiti_embedder(),
        cross_encoder=create_graphiti_cross_encoder()
    )
    
    return client


# Global Graphiti client instance (lazy-loaded)
_graphiti_client: Optional[Graphiti] = None


async def get_graphiti_client() -> Graphiti:
    """Get or create the global Graphiti client instance."""
    global _graphiti_client
    if _graphiti_client is None:
        _graphiti_client = await create_graphiti_client()
    return _graphiti_client


async def close_graphiti_client():
    """Clean up the global Graphiti client."""
    global _graphiti_client
    if _graphiti_client is not None:
        await _graphiti_client.close()
        _graphiti_client = None


# Exception classes for memory operations
class MemorySearchError(Exception):
    """Raised when memory search operations fail."""
    pass


class MemoryAddError(Exception):
    """Raised when memory add operations fail."""
    pass