"""
Nova Graphiti Manager

Global singleton manager for Graphiti client lifecycle (follows db_manager pattern).
Provides centralized Neo4j connection management and error handling.
"""

import logging
import os
from typing import Optional
from graphiti_core import Graphiti
from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.cross_encoder.client import CrossEncoderClient

from config import settings

logger = logging.getLogger(__name__)

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
    model_name = settings.GOOGLE_MODEL_NAME or "gemini-2.0-flash-exp"
    
    # Get user settings for memory token limit
    max_tokens = 32000  # Default fallback
    try:
        import asyncio
        from database.database import db_manager
        from models.user_settings import UserSettings
        from sqlalchemy import select
        
        async def get_token_limit():
            try:
                async with db_manager.get_session() as session:
                    result = await session.execute(select(UserSettings).limit(1))
                    user_settings = result.scalar_one_or_none()
                    return user_settings.memory_token_limit if user_settings else 32000
            except Exception:
                return 32000
        
        # If we're in an async context, try to get the user setting
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context but can't await, use default
                max_tokens = 32000
            else:
                max_tokens = asyncio.run(get_token_limit())
        except RuntimeError:
            # No event loop, use default
            max_tokens = 32000
    except Exception:
        max_tokens = 32000
    
    config = LLMConfig(
        model=model_name,
        api_key=api_key,
        temperature=0.1,  # Lower temperature for factual memory vs Nova's 0.7 default
        max_tokens=max_tokens   # User-configurable token limit
    )
    return GeminiClient(config=config)

def create_graphiti_embedder() -> GeminiEmbedder:
    """
    Create Graphiti-compatible Gemini embedder for semantic search.
    
    This is REQUIRED for Graphiti's search functionality - it creates vector embeddings
    of the knowledge graph content for semantic matching.
    """
    # Reuse Nova's API key configuration
    api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    config = GeminiEmbedderConfig(
        embedding_model="models/text-embedding-004",  # Google's latest embedding model
        api_key=api_key
    )
    return GeminiEmbedder(config=config)

class NullCrossEncoder(CrossEncoderClient):
    """Null cross encoder for MVP - no reranking needed."""
    
    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        """Return passages with simple decreasing scores."""
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
                    uri=settings.NEO4J_URI,
                    user=settings.NEO4J_USER,
                    password=settings.NEO4J_PASSWORD,
                    llm_client=create_graphiti_llm(),
                    embedder=create_graphiti_embedder(),
                    cross_encoder=NullCrossEncoder(),
                    store_raw_episode_content=True,
                )
                
                # Build indices only once per manager instance
                # Note: Graphiti uses IF NOT EXISTS, so Neo4j will handle duplicates gracefully
                if not self._initialized:
                    logger.info("Building Graphiti indices and constraints...")
                    await self._client.build_indices_and_constraints()
                    logger.info("Graphiti client initialized with Neo4j indices")
                    self._initialized = True
                
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