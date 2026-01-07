"""
Graphiti Manager Tests

Tests the module-level graphiti client lifecycle, connection management,
and error handling following Nova's testing patterns.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os


class TestGraphitiClient:
    """Test graphiti client singleton and lifecycle management."""

    @pytest.fixture
    def mock_graphiti_client(self):
        """Mock Graphiti client for testing."""
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        return mock_client

    @pytest.fixture(autouse=True)
    async def cleanup_global_client(self):
        """Reset global client before and after each test."""
        import memory.graphiti_manager as gm
        gm._graphiti_client = None
        yield
        gm._graphiti_client = None

    @pytest.mark.asyncio
    async def test_get_client_initializes_properly(self, mock_graphiti_client):
        """Test client initialization with proper configuration."""
        with patch('memory.graphiti_manager.create_graphiti_client', return_value=mock_graphiti_client):
            from memory.graphiti_manager import get_graphiti_client
            
            client = await get_graphiti_client()
            
            assert client is mock_graphiti_client

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing(self, mock_graphiti_client):
        """Test that subsequent calls reuse existing client."""
        with patch('memory.graphiti_manager.create_graphiti_client', return_value=mock_graphiti_client) as mock_create:
            from memory.graphiti_manager import get_graphiti_client
            
            client1 = await get_graphiti_client()
            client2 = await get_graphiti_client()
            
            assert client1 is client2
            # create_graphiti_client should only be called once
            assert mock_create.call_count == 1

    @pytest.mark.asyncio
    async def test_close_cleanup(self, mock_graphiti_client):
        """Test proper cleanup during close."""
        with patch('memory.graphiti_manager.create_graphiti_client', return_value=mock_graphiti_client):
            from memory.graphiti_manager import get_graphiti_client, close_graphiti_client
            import memory.graphiti_manager as gm
            
            await get_graphiti_client()  # Initialize client
            assert gm._graphiti_client is not None
            
            await close_graphiti_client()
            
            mock_graphiti_client.close.assert_called_once()
            assert gm._graphiti_client is None

    @pytest.mark.asyncio
    async def test_close_with_no_client(self):
        """Test close works safely when no client exists."""
        from memory.graphiti_manager import close_graphiti_client
        
        # Should not raise exception
        await close_graphiti_client()


class TestGraphitiClients:
    """Test Graphiti LLM and embedder client creation."""

    @pytest.mark.asyncio
    async def test_create_graphiti_llm(self):
        """Test LLM client creation with mocked config."""
        with patch('utils.llm_factory.get_memory_llm_config') as mock_config, \
             patch('memory.graphiti_manager.MarkdownStrippingOpenAIClient') as mock_client_cls:
            
            mock_config.return_value = {
                "model": "gpt-4",
                "small_model": "gpt-3.5-turbo",
                "api_key": "test_api_key",
                "base_url": "http://localhost:4000",
                "temperature": 0.7,
                "max_tokens": 2048
            }
            
            from memory.graphiti_manager import create_graphiti_llm
            
            client = create_graphiti_llm()
            
            mock_client_cls.assert_called_once()
            # Verify config was passed
            assert mock_config.called

    @pytest.mark.asyncio
    async def test_create_graphiti_embedder(self):
        """Test embedder creation with mocked config."""
        with patch('utils.llm_factory.get_embedding_config') as mock_config, \
             patch('memory.graphiti_manager.OpenAIEmbedder') as mock_embedder_cls:
            
            mock_config.return_value = {
                "embedding_model": "text-embedding-3-large",
                "api_key": "test_api_key",
                "base_url": "http://localhost:4000",
                "embedding_dim": 3072
            }
            
            from memory.graphiti_manager import create_graphiti_embedder
            
            embedder = create_graphiti_embedder()
            
            mock_embedder_cls.assert_called_once()
            # Verify config was passed
            assert mock_config.called


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


class TestStripMarkdownJson:
    """Test the strip_markdown_json utility function."""

    def test_strips_json_code_block(self):
        """Test stripping ```json ... ``` wrapper."""
        from memory.llm_client import strip_markdown_json

        input_text = '```json\n{"key": "value"}\n```'
        result = strip_markdown_json(input_text)

        assert result == '{"key": "value"}'

    def test_strips_plain_code_block(self):
        """Test stripping ``` ... ``` wrapper without language specifier."""
        from memory.llm_client import strip_markdown_json

        input_text = '```\n{"key": "value"}\n```'
        result = strip_markdown_json(input_text)

        assert result == '{"key": "value"}'

    def test_preserves_raw_json(self):
        """Test that raw JSON without markdown is preserved."""
        from memory.llm_client import strip_markdown_json

        input_text = '{"key": "value"}'
        result = strip_markdown_json(input_text)

        assert result == '{"key": "value"}'

    def test_handles_whitespace(self):
        """Test handling of extra whitespace around code blocks."""
        from memory.llm_client import strip_markdown_json

        input_text = '  ```json\n{"key": "value"}\n```  '
        result = strip_markdown_json(input_text)

        assert result == '{"key": "value"}'

    def test_handles_empty_string(self):
        """Test handling of empty string."""
        from memory.llm_client import strip_markdown_json

        assert strip_markdown_json('') == ''
        assert strip_markdown_json(None) is None

    def test_handles_array_json(self):
        """Test stripping markdown from JSON array (like ExtractedEntities)."""
        from memory.llm_client import strip_markdown_json

        input_text = '```json\n[\n  {\n    "name": "daniel",\n    "entity_type_id": 0\n  }\n]\n```'
        result = strip_markdown_json(input_text)

        assert result == '[\n  {\n    "name": "daniel",\n    "entity_type_id": 0\n  }\n]'


class TestMarkdownStrippingOpenAIClient:
    """Test the MarkdownStrippingOpenAIClient class."""

    @pytest.mark.asyncio
    async def test_handle_structured_response_strips_markdown(self):
        """Test that _handle_structured_response strips markdown wrappers."""
        from memory.llm_client import MarkdownStrippingOpenAIClient

        client = MarkdownStrippingOpenAIClient.__new__(MarkdownStrippingOpenAIClient)

        # Mock response with markdown-wrapped JSON
        class MockResponse:
            output_text = '```json\n{"extracted_entities": [{"name": "Daniel", "entity_type_id": 0}]}\n```'

        result = client._handle_structured_response(MockResponse())

        assert result == {"extracted_entities": [{"name": "Daniel", "entity_type_id": 0}]}

    @pytest.mark.asyncio
    async def test_handle_structured_response_wraps_list_in_object(self):
        """Test that lists are wrapped in expected object structure for ExtractedEntities."""
        from memory.llm_client import MarkdownStrippingOpenAIClient

        client = MarkdownStrippingOpenAIClient.__new__(MarkdownStrippingOpenAIClient)

        # Mock response where LLM returns a list instead of object
        class MockResponse:
            output_text = '[{"name": "Daniel", "entity_type_id": 0}]'

        result = client._handle_structured_response(MockResponse())

        # Should wrap list in expected object structure
        assert result == {"extracted_entities": [{"name": "Daniel", "entity_type_id": 0}]}

    @pytest.mark.asyncio
    async def test_handle_structured_response_markdown_and_list(self):
        """Test handling both markdown wrapping AND list schema mismatch."""
        from memory.llm_client import MarkdownStrippingOpenAIClient

        client = MarkdownStrippingOpenAIClient.__new__(MarkdownStrippingOpenAIClient)

        # Mock response with both issues: markdown + list instead of object
        class MockResponse:
            output_text = '```json\n[\n  {"name": "Daniel", "entity_type_id": 0},\n  {"name": "Pizza", "entity_type_id": 0}\n]\n```'

        result = client._handle_structured_response(MockResponse())

        assert result == {
            "extracted_entities": [
                {"name": "Daniel", "entity_type_id": 0},
                {"name": "Pizza", "entity_type_id": 0}
            ]
        }

    @pytest.mark.asyncio
    async def test_handle_structured_response_preserves_object(self):
        """Test that properly formatted object responses are preserved."""
        from memory.llm_client import MarkdownStrippingOpenAIClient

        client = MarkdownStrippingOpenAIClient.__new__(MarkdownStrippingOpenAIClient)

        # Mock properly formatted response
        class MockResponse:
            output_text = '{"extracted_entities": [{"name": "Daniel", "entity_type_id": 0}]}'

        result = client._handle_structured_response(MockResponse())

        assert result == {"extracted_entities": [{"name": "Daniel", "entity_type_id": 0}]}

    @pytest.mark.asyncio
    async def test_handle_json_response_strips_markdown(self):
        """Test that _handle_json_response strips markdown wrappers."""
        from memory.llm_client import MarkdownStrippingOpenAIClient

        client = MarkdownStrippingOpenAIClient.__new__(MarkdownStrippingOpenAIClient)

        # Mock response with markdown-wrapped JSON
        class MockChoice:
            class message:
                content = '```json\n{"key": "value"}\n```'

        class MockResponse:
            choices = [MockChoice()]

        result = client._handle_json_response(MockResponse())

        assert result == {"key": "value"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 