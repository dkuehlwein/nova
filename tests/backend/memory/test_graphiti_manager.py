"""
GraphitiManager Unit Tests

Tests the singleton GraphitiManager lifecycle, connection management,
and error handling following Nova's testing patterns.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os


class TestGraphitiManager:
    """Test GraphitiManager singleton and lifecycle management."""

    @pytest.fixture
    def mock_graphiti_client(self):
        """Mock Graphiti client for testing."""
        mock_client = AsyncMock()
        mock_client.build_indices_and_constraints = AsyncMock()
        mock_client.close = AsyncMock()
        return mock_client

    @pytest.fixture
    def mock_gemini_client(self):
        """Mock GeminiClient for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_gemini_embedder(self):
        """Mock GeminiEmbedder for testing."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        """Test that GraphitiManager follows singleton pattern."""
        from memory.graphiti_manager import GraphitiManager
        
        manager1 = GraphitiManager()
        manager2 = GraphitiManager()
        
        # Different instances but should manage same client
        assert manager1 is not manager2
        assert manager1._client is None
        assert manager2._client is None

    @pytest.mark.asyncio
    async def test_get_client_initializes_properly(self, mock_graphiti_client):
        """Test client initialization with proper configuration."""
        with patch('memory.graphiti_manager.Graphiti', return_value=mock_graphiti_client), \
             patch('memory.graphiti_manager.create_graphiti_llm') as mock_llm, \
             patch('memory.graphiti_manager.create_graphiti_embedder') as mock_embedder, \
             patch('memory.graphiti_manager.settings') as mock_settings:
            
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_user = "test_user"
            mock_settings.neo4j_password = "test_password"
            
            from memory.graphiti_manager import GraphitiManager
            
            manager = GraphitiManager()
            client = await manager.get_client()
            
            assert client is mock_graphiti_client
            assert manager._client is mock_graphiti_client
            assert manager._initialized is True
            
            # Verify indices were built
            mock_graphiti_client.build_indices_and_constraints.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing(self, mock_graphiti_client):
        """Test that subsequent calls reuse existing client."""
        with patch('memory.graphiti_manager.Graphiti', return_value=mock_graphiti_client), \
             patch('memory.graphiti_manager.create_graphiti_llm'), \
             patch('memory.graphiti_manager.create_graphiti_embedder'), \
             patch('memory.graphiti_manager.settings') as mock_settings:
            
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_user = "test_user"
            mock_settings.neo4j_password = "test_password"
            
            from memory.graphiti_manager import GraphitiManager
            
            manager = GraphitiManager()
            client1 = await manager.get_client()
            client2 = await manager.get_client()
            
            assert client1 is client2
            # Indices should only be built once
            assert mock_graphiti_client.build_indices_and_constraints.call_count == 1

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test proper error handling when Neo4j connection fails."""
        with patch('memory.graphiti_manager.Graphiti', side_effect=Exception("Connection failed")), \
             patch('memory.graphiti_manager.create_graphiti_llm'), \
             patch('memory.graphiti_manager.create_graphiti_embedder'), \
             patch('memory.graphiti_manager.settings') as mock_settings:
            
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_user = "test_user"
            mock_settings.neo4j_password = "test_password"
            
            from memory.graphiti_manager import GraphitiManager, MemoryConnectionError
            
            manager = GraphitiManager()
            
            with pytest.raises(MemoryConnectionError) as exc_info:
                await manager.get_client()
            
            assert "Cannot connect to Neo4j" in str(exc_info.value)
            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close_cleanup(self, mock_graphiti_client):
        """Test proper cleanup during close."""
        with patch('memory.graphiti_manager.Graphiti', return_value=mock_graphiti_client), \
             patch('memory.graphiti_manager.create_graphiti_llm'), \
             patch('memory.graphiti_manager.create_graphiti_embedder'), \
             patch('memory.graphiti_manager.settings') as mock_settings:
            
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_user = "test_user"
            mock_settings.neo4j_password = "test_password"
            
            from memory.graphiti_manager import GraphitiManager
            
            manager = GraphitiManager()
            await manager.get_client()  # Initialize client
            
            await manager.close()
            
            mock_graphiti_client.close.assert_called_once()
            assert manager._client is None
            assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_close_with_no_client(self):
        """Test close works safely when no client exists."""
        from memory.graphiti_manager import GraphitiManager
        
        manager = GraphitiManager()
        # Should not raise exception
        await manager.close()

    @pytest.mark.asyncio
    async def test_close_with_exception(self, mock_graphiti_client):
        """Test close handles exceptions gracefully."""
        mock_graphiti_client.close.side_effect = Exception("Close failed")
        
        with patch('memory.graphiti_manager.Graphiti', return_value=mock_graphiti_client), \
             patch('memory.graphiti_manager.create_graphiti_llm'), \
             patch('memory.graphiti_manager.create_graphiti_embedder'), \
             patch('memory.graphiti_manager.settings') as mock_settings:
            
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_user = "test_user"
            mock_settings.neo4j_password = "test_password"
            
            from memory.graphiti_manager import GraphitiManager
            
            manager = GraphitiManager()
            await manager.get_client()
            
            # Should not raise exception, just log warning
            await manager.close()
            
            assert manager._client is None
            assert manager._initialized is False


class TestGraphitiClients:
    """Test Graphiti LLM and embedder client creation."""

    @pytest.mark.asyncio
    async def test_create_graphiti_llm_with_api_key(self):
        """Test LLM client creation with API key."""
        with patch('memory.graphiti_manager.settings') as mock_settings, \
             patch('memory.graphiti_manager.GeminiClient') as mock_client_cls, \
             patch('database.database.UserSettingsService') as mock_settings_service:
            
            mock_settings.GOOGLE_API_KEY.get_secret_value.return_value = "test_api_key"
            mock_settings_service.get_llm_settings_sync.return_value = {"llm_model": "gemini-2.0-flash-exp"}
            mock_settings_service.get_memory_settings_sync.return_value = {"memory_token_limit": 2048}
            
            from memory.graphiti_manager import create_graphiti_llm
            
            client = create_graphiti_llm()
            
            mock_client_cls.assert_called_once()
            config = mock_client_cls.call_args[1]["config"]
            assert config.api_key == "test_api_key"
            assert config.model == "gemini-2.0-flash-exp"
            assert config.temperature == 0.1
            assert config.max_tokens == 2048

    @pytest.mark.asyncio
    async def test_create_graphiti_llm_missing_api_key(self):
        """Test LLM client creation fails without API key."""
        with patch('memory.graphiti_manager.settings') as mock_settings, \
             patch.dict(os.environ, {}, clear=True):
            
            mock_settings.GOOGLE_API_KEY = None
            
            from memory.graphiti_manager import create_graphiti_llm
            
            with pytest.raises(ValueError) as exc_info:
                create_graphiti_llm()
            
            assert "GOOGLE_API_KEY environment variable is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_graphiti_embedder_with_api_key(self):
        """Test embedder creation with API key."""
        with patch('memory.graphiti_manager.settings') as mock_settings, \
             patch('memory.graphiti_manager.GeminiEmbedder') as mock_embedder_cls:
            
            mock_settings.GOOGLE_API_KEY.get_secret_value.return_value = "test_api_key"
            
            from memory.graphiti_manager import create_graphiti_embedder
            
            embedder = create_graphiti_embedder()
            
            mock_embedder_cls.assert_called_once()
            config = mock_embedder_cls.call_args[1]["config"]
            assert config.api_key == "test_api_key"
            assert config.embedding_model == "models/text-embedding-004"

    @pytest.mark.asyncio
    async def test_create_graphiti_embedder_missing_api_key(self):
        """Test embedder creation fails without API key."""
        with patch('memory.graphiti_manager.settings') as mock_settings, \
             patch.dict(os.environ, {}, clear=True):
            
            mock_settings.GOOGLE_API_KEY = None
            
            from memory.graphiti_manager import create_graphiti_embedder
            
            with pytest.raises(ValueError) as exc_info:
                create_graphiti_embedder()
            
            assert "GOOGLE_API_KEY environment variable is required" in str(exc_info.value)


class TestNullCrossEncoder:
    """Test NullCrossEncoder implementation."""

    @pytest.mark.asyncio
    async def test_rank_returns_descending_scores(self):
        """Test that rank returns passages with descending scores."""
        from memory.graphiti_manager import NullCrossEncoder
        
        encoder = NullCrossEncoder()
        passages = ["passage1", "passage2", "passage3"]
        
        result = await encoder.rank("test query", passages)
        
        assert len(result) == 3
        assert result[0] == ("passage1", 1.0)
        assert result[1] == ("passage2", 0.99)
        assert result[2] == ("passage3", 0.98)

    @pytest.mark.asyncio
    async def test_rank_empty_passages(self):
        """Test rank with empty passages list."""
        from memory.graphiti_manager import NullCrossEncoder
        
        encoder = NullCrossEncoder()
        result = await encoder.rank("test query", [])
        
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 