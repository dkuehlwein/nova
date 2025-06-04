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
    """Create sync checkpointer based on configuration."""
    if settings.DATABASE_URL:
        try:
            # Try to import sync PostgreSQL checkpointer
            from langgraph.checkpoint.postgres import PostgresSaver
            
            # For long-running services, we need to manage the connection ourselves
            # Following the pattern from LangGraph documentation
            import psycopg  # Using psycopg3, not psycopg2
            
            # Create a connection pool or persistent connection
            connection = psycopg.connect(settings.DATABASE_URL, autocommit=True)
            
            # Create checkpointer with the connection
            checkpointer = PostgresSaver(connection)
            
            # Setup tables for PostgreSQL checkpointers
            if hasattr(checkpointer, 'setup'):
                try:
                    checkpointer.setup()
                    print(f"PostgreSQL checkpointer set up successfully")
                except Exception as setup_error:
                    print(f"Warning: Could not setup PostgreSQL tables: {setup_error}")
                    print("Make sure the database exists and is accessible.")
                    connection.close()
                    return MemorySaver()
            
            return checkpointer
                
        except ImportError as e:
            print(f"Sync PostgreSQL checkpointer not available: {e}")
            print("Install with: pip install langgraph-checkpoint-postgres")
            return MemorySaver()
        except Exception as e:
            print(f"Error creating PostgreSQL checkpointer: {e}")
            return MemorySaver()
    else:
        print("Using in-memory checkpointer. Set DATABASE_URL for persistent conversations.")
        return MemorySaver()


async def create_async_checkpointer():
    """Create async checkpointer based on configuration."""
    if settings.DATABASE_URL:
        print(f"DEBUG: PostgreSQL URL provided but temporarily using MemorySaver for debugging")
        print(f"DEBUG: DATABASE_URL set to: {settings.DATABASE_URL[:20]}...")
        # TODO: Fix PostgreSQL checkpointer setup
        return MemorySaver()
    else:
        print("Using in-memory checkpointer. Set DATABASE_URL for persistent conversations.")
        return MemorySaver()


def _create_graph_builder():
    """Create the base graph builder with nodes and edges.
    
    This shared function eliminates duplication between sync and async graph creation.
    """
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
    
    return graph_builder


def create_graph():
    """Create and compile the LangGraph chat agent with sync checkpointer."""
    graph_builder = _create_graph_builder()
    checkpointer = create_checkpointer()
    
    # Compile the graph with checkpointer
    return graph_builder.compile(checkpointer=checkpointer)


async def create_async_graph():
    """Create and compile the LangGraph chat agent with async checkpointer."""
    graph_builder = _create_graph_builder()
    checkpointer = await create_async_checkpointer()
    
    # Compile the graph with checkpointer
    return graph_builder.compile(checkpointer=checkpointer)


# The main graph instance (uses sync checkpointer)
graph = create_graph() 