"""
Tests for Nova LangGraph Chat Agent
"""

import pytest
from unittest.mock import patch
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agent.chat_agent import create_chat_agent, create_checkpointer


class TestChatAgent:
    """Test cases for the Nova chat agent."""
    
    def teardown_method(self):
        """Clean up after each test."""
        # Clear tools cache to ensure clean state
        from agent.chat_agent import clear_tools_cache
        clear_tools_cache()
    
    @pytest.mark.asyncio
    async def test_basic_conversation(self):
        """Test basic conversation functionality."""
        # Create test agent
        test_agent = await create_chat_agent()
        
        # Configuration for testing
        config = {
            "configurable": {
                "thread_id": "test-thread-basic"
            }
        }
        
        # Test basic conversation
        result = await test_agent.ainvoke({
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
        # Create test agent
        test_agent = await create_chat_agent()
        
        # Configuration for testing
        config = {
            "configurable": {
                "thread_id": "test-thread-tools"
            }
        }
        
        # Test tool usage
        result = await test_agent.ainvoke({
            "messages": [HumanMessage(content="Create a new task called 'Test LangGraph integration'")]
        }, config=config)
        
        # Verify response
        assert result is not None
        assert "messages" in result
        assert len(result["messages"]) > 0
    
    @pytest.mark.asyncio
    async def test_conversation_continuity(self):
        """Test conversation continuity across multiple messages."""
        # Create test agent
        test_agent = await create_chat_agent()
        
        # Configuration for testing
        config = {
            "configurable": {
                "thread_id": "test-thread-continuity"
            }
        }
        
        # First message
        result1 = await test_agent.ainvoke({
            "messages": [HumanMessage(content="Create a new task called 'Test continuity'")]
        }, config=config)
        
        # Second message referring to the first
        result2 = await test_agent.ainvoke({
            "messages": [HumanMessage(content="What was the task I just created?")]
        }, config=config)
        
        # Verify both responses
        assert result1 is not None
        assert result2 is not None
        assert "messages" in result1
        assert "messages" in result2

    @pytest.mark.asyncio 
    async def test_force_memory_checkpointer(self):
        """Test that FORCE_MEMORY_CHECKPOINTER setting works."""
        # Test with FORCE_MEMORY_CHECKPOINTER=True
        with patch('config.settings.FORCE_MEMORY_CHECKPOINTER', True):
            checkpointer = await create_checkpointer()
            assert isinstance(checkpointer, MemorySaver)
        
        # Test with FORCE_MEMORY_CHECKPOINTER=False and no DATABASE_URL
        with patch('config.settings.FORCE_MEMORY_CHECKPOINTER', False), \
             patch('config.settings.DATABASE_URL', None):
            checkpointer = await create_checkpointer()
            assert isinstance(checkpointer, MemorySaver)


# Standalone test function for manual testing (can be run directly)
async def manual_test_agent():
    """Manual test function for development testing."""
    print("\n🧪 Testing Nova LangGraph Agent...")
    
    # Use new chat agent for testing
    test_agent = await create_chat_agent()
    
    # Configuration for testing
    config = {
        "configurable": {
            "thread_id": "test-thread-manual"
        }
    }
    
    # Test basic conversation
    result = await test_agent.ainvoke({
        "messages": [HumanMessage(content="Hello! What can you help me with?")]
    }, config=config)
    
    print(f"Response: {result['messages'][-1].content}")
    
    # Test tool usage
    result = await test_agent.ainvoke({
        "messages": [HumanMessage(content="Create a new task called 'Test LangGraph integration'")]
    }, config=config)
    
    print(f"Tool response: {result['messages'][-1].content}")
    
    # Test conversation continuity
    result = await test_agent.ainvoke({
        "messages": [HumanMessage(content="What was the task I just created?")]
    }, config=config)
    
    print(f"Continuity test: {result['messages'][-1].content}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(manual_test_agent()) 