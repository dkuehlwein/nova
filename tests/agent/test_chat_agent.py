"""
Tests for Nova LangGraph Chat Agent
"""

import pytest
from langchain_core.messages import HumanMessage

from agent.chat_agent import create_async_graph


class TestChatAgent:
    """Test cases for the Nova chat agent."""
    
    @pytest.mark.asyncio
    async def test_basic_conversation(self):
        """Test basic conversation functionality."""
        # Create test graph
        test_graph = await create_async_graph()
        
        # Configuration for testing
        config = {
            "configurable": {
                "thread_id": "test-thread-basic",
                "model_name": "gemini-2.5-flash-preview-04-17",
                "temperature": 0.7
            }
        }
        
        # Test basic conversation
        result = await test_graph.ainvoke({
            "messages": [HumanMessage(content="Hello! What can you help me with?")]
        }, config=config)
        
        # Verify response
        assert result is not None
        assert "messages" in result
        assert len(result["messages"]) > 0
        
        # Check that we got an AI response
        last_message = result["messages"][-1]
        assert hasattr(last_message, 'content')
        assert isinstance(last_message.content, str)
        assert len(last_message.content) > 0
    
    @pytest.mark.asyncio
    async def test_tool_usage(self):
        """Test that the agent can use tools."""
        # Create test graph
        test_graph = await create_async_graph()
        
        # Configuration for testing
        config = {
            "configurable": {
                "thread_id": "test-thread-tools",
                "model_name": "gemini-2.5-flash-preview-04-17",
                "temperature": 0.7
            }
        }
        
        # Test tool usage
        result = await test_graph.ainvoke({
            "messages": [HumanMessage(content="Create a new task called 'Test LangGraph integration'")]
        }, config=config)
        
        # Verify response
        assert result is not None
        assert "messages" in result
        assert len(result["messages"]) > 0
    
    @pytest.mark.asyncio
    async def test_conversation_continuity(self):
        """Test conversation continuity across multiple messages."""
        # Create test graph
        test_graph = await create_async_graph()
        
        # Configuration for testing
        config = {
            "configurable": {
                "thread_id": "test-thread-continuity",
                "model_name": "gemini-2.5-flash-preview-04-17",
                "temperature": 0.7
            }
        }
        
        # First message
        result1 = await test_graph.ainvoke({
            "messages": [HumanMessage(content="Create a new task called 'Test continuity'")]
        }, config=config)
        
        # Second message referring to the first
        result2 = await test_graph.ainvoke({
            "messages": [HumanMessage(content="What was the task I just created?")]
        }, config=config)
        
        # Verify both responses
        assert result1 is not None
        assert result2 is not None
        assert "messages" in result1
        assert "messages" in result2


# Standalone test function for manual testing (can be run directly)
async def manual_test_graph():
    """Manual test function for development testing."""
    print("\n🧪 Testing Nova LangGraph Agent...")
    
    # Use async graph for testing
    test_graph = await create_async_graph()
    
    # Configuration for testing
    config = {
        "configurable": {
            "thread_id": "test-thread-manual",
            "model_name": "gemini-2.5-flash-preview-04-17",
            "temperature": 0.7
        }
    }
    
    # Test basic conversation
    result = await test_graph.ainvoke({
        "messages": [HumanMessage(content="Hello! What can you help me with?")]
    }, config=config)
    
    print(f"Response: {result['messages'][-1].content}")
    
    # Test tool usage
    result = await test_graph.ainvoke({
        "messages": [HumanMessage(content="Create a new task called 'Test LangGraph integration'")]
    }, config=config)
    
    print(f"Tool response: {result['messages'][-1].content}")
    
    # Test conversation continuity
    result = await test_graph.ainvoke({
        "messages": [HumanMessage(content="What was the task I just created?")]
    }, config=config)
    
    print(f"Continuity test: {result['messages'][-1].content}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(manual_test_graph()) 