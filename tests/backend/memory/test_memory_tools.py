"""
Memory Tools Unit Tests

Tests the LangChain memory tools for agent integration,
including proper response formatting and error handling.
"""

import pytest
from unittest.mock import AsyncMock, patch


class TestMemoryTools:
    """Test memory tools for agent integration."""

    @pytest.mark.asyncio
    async def test_search_memory_tool_success(self):
        """Test search_memory_tool with successful results."""
        mock_result = {
            "success": True,
            "count": 2,
            "results": [
                {"fact": "John works on Nova project"},
                {"fact": "Nova is a kanban task management system"}
            ]
        }
        
        with patch('tools.memory_tools.search_memory', return_value=mock_result):
            from tools.memory_tools import search_memory_tool
            
            response = await search_memory_tool("Nova project")
            
            assert isinstance(response, str)
            assert "Found 2 relevant memories" in response
            assert "John works on Nova project" in response
            assert "Nova is a kanban task management system" in response

    @pytest.mark.asyncio
    async def test_search_memory_tool_no_results(self):
        """Test search_memory_tool with no results."""
        mock_result = {
            "success": True,
            "count": 0,
            "results": []
        }
        
        with patch('tools.memory_tools.search_memory', return_value=mock_result):
            from tools.memory_tools import search_memory_tool
            
            response = await search_memory_tool("unknown query")
            
            assert isinstance(response, str)
            assert "No relevant memories found" in response

    @pytest.mark.asyncio
    async def test_search_memory_tool_error_handling(self):
        """Test search_memory_tool error handling."""
        from tools.memory_tools import MemorySearchError
        
        with patch('tools.memory_tools.search_memory', side_effect=MemorySearchError("Connection failed")):
            from tools.memory_tools import search_memory_tool
            
            response = await search_memory_tool("test query")
            
            assert isinstance(response, str)
            assert "Memory search is currently unavailable" in response

    @pytest.mark.asyncio
    async def test_add_memory_tool_success(self):
        """Test add_memory_tool with successful addition."""
        mock_result = {
            "success": True,
            "nodes_created": 2,
            "edges_created": 1,
            "entities": [
                {"name": "Alice", "labels": ["Person"]},
                {"name": "Nova", "labels": ["Project"]}
            ]
        }
        
        with patch('tools.memory_tools.add_memory', return_value=mock_result):
            from tools.memory_tools import add_memory_tool
            
            response = await add_memory_tool(
                "Alice is working on Nova project",
                "Test data"
            )
            
            assert isinstance(response, str)
            assert "Memory stored successfully" in response
            assert "Created 2 entities and 1 relationships" in response
            assert "Alice (Person), Nova (Project)" in response

    @pytest.mark.asyncio
    async def test_add_memory_tool_error_handling(self):
        """Test add_memory_tool error handling."""
        from tools.memory_tools import MemoryAddError
        
        with patch('tools.memory_tools.add_memory', side_effect=MemoryAddError("Storage failed")):
            from tools.memory_tools import add_memory_tool
            
            response = await add_memory_tool("test content", "test source")
            
            assert isinstance(response, str)
            assert "Memory storage is currently unavailable" in response

    @pytest.mark.asyncio
    async def test_get_memory_tools_returns_correct_tools(self):
        """Test that get_memory_tools returns properly configured tools."""
        from tools.memory_tools import get_memory_tools
        
        tools = get_memory_tools()
        
        assert len(tools) == 2
        
        # Check search tool
        search_tool = next(tool for tool in tools if tool.name == "search_memory")
        assert "Search your memory" in search_tool.description
        
        # Check add tool
        add_tool = next(tool for tool in tools if tool.name == "add_memory")
        assert "store important facts" in add_tool.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 