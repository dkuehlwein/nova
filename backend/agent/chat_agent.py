"""
Nova LangGraph Chat Agent

A LangGraph chat agent that integrates with Nova's tools and follows the agent-chat-ui patterns.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Dict, List, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from tools import get_all_tools
from config import settings
from .llm import create_llm


class Configuration(TypedDict):
    """Configurable parameters for the agent.
    
    This allows the agent-chat-ui to pass configuration parameters.
    """
    model_name: str
    temperature: float


class State(TypedDict):
    """Agent state with message history."""
    messages: Annotated[list, add_messages]


def chatbot(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Generate a response using Google Gemini with Nova tools.
    
    Takes the conversation history and generates an AI response, potentially using tools.
    """
    # Create model with tools
    llm = create_llm(config)
    tools = get_all_tools()
    llm_with_tools = llm.bind_tools(tools)
    
    # Add system message with Nova's personality and capabilities
    messages = state["messages"]
    if not messages or not any(isinstance(msg, HumanMessage) and "You are Nova" in str(msg.content) for msg in messages):
        system_message = HumanMessage(content="""You are Nova, an AI assistant for managers. You help with:

1. **Task Management**: Creating, updating, organizing tasks in the kanban board
2. **People Management**: Managing team members and contact information  
3. **Project Management**: Organizing and tracking projects

You have access to tools that let you:
- Create and manage tasks with proper relationships
- Track people and their roles
- Organize projects
- Add comments and updates to tasks

Be helpful, professional, and action-oriented. When users ask you to do something, use the appropriate tools to accomplish their requests. Always confirm actions you've taken and provide clear summaries of what you've accomplished.

Available tools:
""" + "\n".join([f"- {tool.name}: {tool.description}" for tool in tools]))
        messages = [system_message] + messages
    
    # Generate response
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}


def create_checkpointer():
    """Create checkpointer based on configuration.
    
    Returns PostgreSQL checkpointer if DATABASE_URL is set, 
    otherwise returns in-memory checkpointer.
    """
    if settings.DATABASE_URL:
        try:
            # Try to import PostgreSQL checkpointer
            from langgraph.checkpoint.postgres import PostgresSaver
            checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URL)
            
            # Setup tables on first use
            try:
                checkpointer.setup()
            except Exception as setup_error:
                print(f"Warning: Could not setup PostgreSQL tables: {setup_error}")
                print("Make sure the database exists and is accessible.")
                return MemorySaver()
            
            return checkpointer
        except ImportError:
            print("PostgreSQL checkpointer not available. Install with: pip install langgraph-checkpoint-postgres")
            return MemorySaver()
    else:
        print("Using in-memory checkpointer. Set DATABASE_URL for persistent conversations.")
        return MemorySaver()


async def create_async_checkpointer():
    """Create async checkpointer based on configuration.
    
    Returns async PostgreSQL checkpointer if DATABASE_URL is set, 
    otherwise returns in-memory checkpointer.
    """
    if settings.DATABASE_URL:
        try:
            # Try to import async PostgreSQL checkpointer
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
            
            # Setup tables on first use
            try:
                await checkpointer.setup()
            except Exception as setup_error:
                print(f"Warning: Could not setup PostgreSQL tables: {setup_error}")
                print("Make sure the database exists and is accessible.")
                return MemorySaver()
            
            return checkpointer
        except ImportError:
            print("Async PostgreSQL checkpointer not available. Install with: pip install langgraph-checkpoint-postgres")
            return MemorySaver()
    else:
        print("Using in-memory checkpointer. Set DATABASE_URL for persistent conversations.")
        return MemorySaver()


def create_graph():
    """Create and compile the LangGraph chat agent."""
    # Get Nova tools for the tool node
    tools = get_all_tools()
    
    # Create the graph with message state and configuration schema
    graph_builder = StateGraph(State, config_schema=Configuration)
    
    # Add nodes
    graph_builder.add_node("chatbot", chatbot)
    
    # Create tool node
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    
    # Set entry point
    graph_builder.add_edge(START, "chatbot")
    
    # Add conditional edges using tools_condition
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    
    # After tools, go back to chatbot
    graph_builder.add_edge("tools", "chatbot")
    
    # Create checkpointer
    checkpointer = create_checkpointer()
    
    # Compile the graph with checkpointer
    return graph_builder.compile(checkpointer=checkpointer)


async def create_async_graph():
    """Create and compile the LangGraph chat agent with async checkpointer."""
    # Get Nova tools for the tool node
    tools = get_all_tools()
    
    # Create the graph with message state and configuration schema
    graph_builder = StateGraph(State, config_schema=Configuration)
    
    # Add nodes
    graph_builder.add_node("chatbot", chatbot)
    
    # Create tool node
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    
    # Set entry point
    graph_builder.add_edge(START, "chatbot")
    
    # Add conditional edges using tools_condition
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    
    # After tools, go back to chatbot
    graph_builder.add_edge("tools", "chatbot")
    
    # Create async checkpointer
    checkpointer = await create_async_checkpointer()
    
    # Compile the graph with checkpointer
    return graph_builder.compile(checkpointer=checkpointer)


# The main graph instance
graph = create_graph()


# Test function for development
async def test_graph():
    """Test the LangGraph agent."""
    from langchain_core.messages import HumanMessage
    
    print("\n🧪 Testing Nova LangGraph Agent...")
    
    # Use async graph for testing
    test_graph = await create_async_graph()
    
    # Configuration for testing
    config = {
        "configurable": {
            "thread_id": "test-thread-1",
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
    asyncio.run(test_graph()) 