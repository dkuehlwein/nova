"""
Memory Functions Tests

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
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client, \
             patch('memory.memory_functions.settings') as mock_settings:
            
            mock_settings.MEMORY_SEARCH_LIMIT = 10
            mock_settings.MEMORY_GROUP_ID = "test_group"
            
            mock_client = AsyncMock()
            mock_client.search.return_value = [mock_edge_result]
            mock_get_client.return_value = mock_client
            
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
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client:
            
            mock_get_client.side_effect = Exception("Connection failed")
            
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
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client, \
             patch('memory.memory_functions.settings') as mock_settings, \
             patch('memory.memory_functions.NOVA_ENTITY_TYPES') as mock_types:
            
            mock_settings.MEMORY_GROUP_ID = "test_group"
            
            mock_client = AsyncMock()
            mock_client.add_episode.return_value = mock_add_result
            mock_get_client.return_value = mock_client
            
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
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client:
            
            mock_get_client.side_effect = Exception("Connection failed")
            
            from memory.memory_functions import add_memory, MemoryAddError
            
            with pytest.raises(MemoryAddError) as exc_info:
                await add_memory("content", "source")
            
            assert "Failed to add memory" in str(exc_info.value)
            assert "Connection failed" in str(exc_info.value)


class TestDeleteEpisode:
    """Test delete_episode function."""

    @pytest.mark.asyncio
    async def test_delete_episode_success(self):
        """Test successful episode deletion."""
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client:

            mock_client = AsyncMock()
            mock_client.remove_episode = AsyncMock()
            mock_get_client.return_value = mock_client

            from memory.memory_functions import delete_episode

            episode_uuid = str(uuid4())
            result = await delete_episode(episode_uuid)

            assert result["success"] is True
            assert result["deleted_uuid"] == episode_uuid
            mock_client.remove_episode.assert_called_once_with(episode_uuid)

    @pytest.mark.asyncio
    async def test_delete_episode_error_handling(self):
        """Test delete episode error handling."""
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client:

            mock_client = AsyncMock()
            mock_client.remove_episode.side_effect = Exception("Episode not found")
            mock_get_client.return_value = mock_client

            from memory.memory_functions import delete_episode, MemoryDeleteError

            with pytest.raises(MemoryDeleteError) as exc_info:
                await delete_episode("invalid-uuid")

            assert "Failed to delete episode" in str(exc_info.value)
            assert "Episode not found" in str(exc_info.value)


class TestDeleteFact:
    """Test delete_fact function."""

    @pytest.mark.asyncio
    async def test_delete_fact_success(self):
        """Test successful fact deletion."""
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client:

            # Mock Neo4j session and result
            mock_record = MagicMock()
            mock_record.__getitem__ = MagicMock(return_value=1)

            mock_result = AsyncMock()
            mock_result.single = AsyncMock(return_value=mock_record)

            mock_session = AsyncMock()
            mock_session.run = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_driver = MagicMock()
            mock_driver.session = MagicMock(return_value=mock_session)

            mock_client = AsyncMock()
            mock_client.driver = mock_driver
            mock_get_client.return_value = mock_client

            from memory.memory_functions import delete_fact

            fact_uuid = str(uuid4())
            result = await delete_fact(fact_uuid)

            assert result["success"] is True
            assert result["deleted_uuid"] == fact_uuid
            assert result["deleted_count"] == 1

    @pytest.mark.asyncio
    async def test_delete_fact_not_found(self):
        """Test delete fact when fact doesn't exist."""
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client:

            # Mock Neo4j session returning 0 deleted
            mock_record = MagicMock()
            mock_record.__getitem__ = MagicMock(return_value=0)

            mock_result = AsyncMock()
            mock_result.single = AsyncMock(return_value=mock_record)

            mock_session = AsyncMock()
            mock_session.run = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_driver = MagicMock()
            mock_driver.session = MagicMock(return_value=mock_session)

            mock_client = AsyncMock()
            mock_client.driver = mock_driver
            mock_get_client.return_value = mock_client

            from memory.memory_functions import delete_fact

            fact_uuid = str(uuid4())
            result = await delete_fact(fact_uuid)

            assert result["success"] is False
            assert result["error"] == "not_found"
            assert "No fact found" in result["message"]

    @pytest.mark.asyncio
    async def test_delete_fact_error_handling(self):
        """Test delete fact error handling."""
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client:

            mock_client = AsyncMock()
            mock_client.driver.session.side_effect = Exception("Database error")
            mock_get_client.return_value = mock_client

            from memory.memory_functions import delete_fact, MemoryDeleteError

            with pytest.raises(MemoryDeleteError) as exc_info:
                await delete_fact("some-uuid")

            assert "Failed to delete fact" in str(exc_info.value)


class TestGetRecentFacts:
    """Test get_recent_facts function."""

    @pytest.mark.asyncio
    async def test_get_recent_facts_success(self):
        """Test successful retrieval of recent facts."""
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client, \
             patch('memory.memory_functions.settings') as mock_settings:

            mock_settings.MEMORY_GROUP_ID = "test_group"

            # Mock Neo4j session and result
            mock_records = [
                {
                    "uuid": str(uuid4()),
                    "fact": "Recent fact 1",
                    "source_node": str(uuid4()),
                    "target_node": str(uuid4()),
                    "created_at": datetime.now(timezone.utc)
                },
                {
                    "uuid": str(uuid4()),
                    "fact": "Recent fact 2",
                    "source_node": str(uuid4()),
                    "target_node": str(uuid4()),
                    "created_at": datetime.now(timezone.utc)
                }
            ]

            mock_result = AsyncMock()
            mock_result.data = AsyncMock(return_value=mock_records)

            mock_session = AsyncMock()
            mock_session.run = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_driver = MagicMock()
            mock_driver.session = MagicMock(return_value=mock_session)

            mock_client = AsyncMock()
            mock_client.driver = mock_driver
            mock_get_client.return_value = mock_client

            from memory.memory_functions import get_recent_facts

            result = await get_recent_facts(limit=5)

            assert result["success"] is True
            assert result["count"] == 2
            assert len(result["results"]) == 2
            assert result["results"][0]["fact"] == "Recent fact 1"

    @pytest.mark.asyncio
    async def test_get_recent_facts_error_handling(self):
        """Test get_recent_facts error handling."""
        with patch('memory.memory_functions.graphiti_manager.get_graphiti_client') as mock_get_client:

            mock_client = AsyncMock()
            mock_client.driver.session.side_effect = Exception("Database error")
            mock_get_client.return_value = mock_client

            from memory.memory_functions import get_recent_facts, MemorySearchError

            with pytest.raises(MemorySearchError) as exc_info:
                await get_recent_facts(limit=5)

            assert "Failed to retrieve recent facts" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 