"""
Memory Functions Unit Tests

Tests the memory business logic functions including search_memory, add_memory,
and get_recent_episodes with proper mocking and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4


class TestSearchMemory:
    """Test search_memory function."""

    @pytest.fixture
    def mock_edge_result(self):
        """Mock GraphQL edge result."""
        edge = MagicMock()
        edge.fact = "John works on Nova project"
        edge.uuid = str(uuid4())
        edge.source_node_uuid = str(uuid4())
        edge.target_node_uuid = str(uuid4())
        edge.created_at = datetime.now(timezone.utc)
        return edge

    @pytest.mark.asyncio
    async def test_search_memory_success(self, mock_edge_result):
        """Test successful memory search."""
        with patch('memory.memory_functions.graphiti_manager') as mock_manager, \
             patch('memory.memory_functions.settings') as mock_settings:
            
            mock_settings.memory_search_limit = 10
            mock_settings.memory_group_id = "test_group"
            
            mock_client = AsyncMock()
            mock_client.search.return_value = [mock_edge_result]
            mock_manager.get_client.return_value = mock_client
            
            from memory.memory_functions import search_memory
            
            result = await search_memory("test query")
            
            assert result["success"] is True
            assert result["count"] == 1
            assert result["query"] == "test query"
            assert result["limit"] == 10
            assert len(result["results"]) == 1
            
            # Verify search was called with correct parameters
            mock_client.search.assert_called_once_with(
                query="test query",
                group_ids=["test_group"],
                num_results=10
            )

    @pytest.mark.asyncio
    async def test_search_memory_error_handling(self):
        """Test search memory error handling."""
        with patch('memory.memory_functions.graphiti_manager') as mock_manager:
            
            mock_manager.get_client.side_effect = Exception("Connection failed")
            
            from memory.memory_functions import search_memory, MemorySearchError
            
            with pytest.raises(MemorySearchError) as exc_info:
                await search_memory("test query")
            
            assert "Failed to search memory" in str(exc_info.value)
            assert "Connection failed" in str(exc_info.value)


class TestAddMemory:
    """Test add_memory function."""

    @pytest.fixture
    def mock_add_result(self):
        """Mock add episode result."""
        result = MagicMock()
        result.episode.uuid = str(uuid4())
        
        # Mock nodes
        node1 = MagicMock()
        node1.name = "John"
        node1.labels = ["Person"]
        node1.uuid = str(uuid4())
        
        result.nodes = [node1]
        result.edges = [MagicMock()]
        
        return result

    @pytest.mark.asyncio
    async def test_add_memory_success(self, mock_add_result):
        """Test successful memory addition."""
        with patch('memory.memory_functions.graphiti_manager') as mock_manager, \
             patch('memory.memory_functions.settings') as mock_settings, \
             patch('memory.memory_functions.NOVA_ENTITY_TYPES') as mock_types:
            
            mock_settings.memory_group_id = "test_group"
            
            mock_client = AsyncMock()
            mock_client.add_episode.return_value = mock_add_result
            mock_manager.get_client.return_value = mock_client
            
            from memory.memory_functions import add_memory
            
            result = await add_memory(
                content="John is working on Nova project", 
                source_description="Test data"
            )
            
            assert result["success"] is True
            assert result["episode_uuid"] == mock_add_result.episode.uuid
            assert result["nodes_created"] == 1
            assert result["edges_created"] == 1
            assert len(result["entities"]) == 1

    @pytest.mark.asyncio
    async def test_add_memory_error_handling(self):
        """Test add memory error handling."""
        with patch('memory.memory_functions.graphiti_manager') as mock_manager:
            
            mock_manager.get_client.side_effect = Exception("Connection failed")
            
            from memory.memory_functions import add_memory, MemoryAddError
            
            with pytest.raises(MemoryAddError) as exc_info:
                await add_memory("content", "source")
            
            assert "Failed to add memory" in str(exc_info.value)
            assert "Connection failed" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 