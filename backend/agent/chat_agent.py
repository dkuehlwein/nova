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
from mcp_client import mcp_manager


class Configuration(TypedDict):
    """Configurable parameters for the agent.
    
    This allows the agent-chat-ui to pass configuration parameters.
    """
    model_name: str
    temperature: float


class State(TypedDict):
    """Agent state with message history."""
    messages: Annotated[list, add_messages]


async def get_all_tools_with_mcp():
    """Get all tools including both local Nova tools and external MCP tools."""
    # Get local Nova tools
    local_tools = get_all_tools()
    
    # Get MCP tools from external servers
    try:
        _, mcp_tools = await mcp_manager.get_client_and_tools()
    except Exception as e:
        print(f"Warning: Could not fetch MCP tools: {e}")
        mcp_tools = []
    
    # Combine all tools
    all_tools = local_tools + mcp_tools
    
    print(f"📋 Available tools: {len(local_tools)} local + {len(mcp_tools)} MCP = {len(all_tools)} total")
    
    return all_tools


async def chatbot(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Generate a response using Google Gemini with Nova tools.
    
    Takes the conversation history and generates an AI response, potentially using tools.
    """
    # Create model with tools
    llm = create_llm(config)
    tools = await get_all_tools_with_mcp()
    llm_with_tools = llm.bind_tools(tools)
    
    # Add system message with Nova's personality and capabilities
    messages = state["messages"]
    if not messages or not any(isinstance(msg, HumanMessage) and "You are Nova" in str(msg.content) for msg in messages):
        system_message = HumanMessage(content="""You are Nova, an AI assistant for managers. You help with:

1. **Task Management**: Creating, updating, organizing tasks in the kanban board
2. **People Management**: Managing team members and contact information  
3. **Project Management**: Organizing and tracking projects
4. **Email Management**: Reading, sending, and managing emails via Gmail

You have access to tools that let you:
- Create and manage tasks with proper relationships
- Track people and their roles
- Organize projects
- Add comments and updates to tasks
- Send and read emails through Gmail
- Manage your inbox and email threads

Be helpful, professional, and action-oriented. When users ask you to do something, use the appropriate tools to accomplish their requests. Always confirm actions you've taken and provide clear summaries of what you've accomplished.

Available tools:
""" + "\n".join([f"- {tool.name}: {tool.description}" for tool in tools]))
        messages = [system_message] + messages
    
    # Generate response
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}


async def create_async_checkpointer():
    """Create async checkpointer based on configuration."""
    if settings.DATABASE_URL:
        try:
            # Try to import async PostgreSQL checkpointer from the correct module
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            
            print(f"DEBUG: Using PostgreSQL URL: {settings.DATABASE_URL[:30]}...")
            
            # Use the connection pool approach based on LangGraph community patterns
            # This is the proper way to handle PostgreSQL connections in long-running applications
            from psycopg_pool import AsyncConnectionPool
            
            # Create async connection pool
            print("DEBUG: Creating AsyncConnectionPool...")
            
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }
            
            # Create the connection pool - this will be managed by FastAPI lifespan
            # For now, we'll return MemorySaver and implement proper pool management later
            print("PostgreSQL checkpointer requires connection pool management via FastAPI lifespan")
            print("Using MemorySaver for now - PostgreSQL implementation needs proper lifespan setup")
            return MemorySaver()
                
        except ImportError as e:
            print(f"Async PostgreSQL checkpointer not available: {e}")
            print("Install with: pip install langgraph-checkpoint-postgres")
            print("Falling back to MemorySaver...")
            return MemorySaver()
        except Exception as e:
            print(f"Error creating async PostgreSQL checkpointer: {e}")
            import traceback
            traceback.print_exc()
            print("Falling back to MemorySaver...")
            return MemorySaver()
    else:
        print("No DATABASE_URL provided. Using in-memory checkpointer.")
        return MemorySaver()


async def _create_graph_builder():
    """Create the base graph builder with nodes and edges.
    
    This shared function eliminates duplication between sync and async graph creation.
    """
    # Get Nova tools for the tool node (including MCP tools)
    tools = await get_all_tools_with_mcp()
    
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


async def create_async_graph():
    """Create and compile the LangGraph chat agent with async checkpointer."""
    graph_builder = await _create_graph_builder()
    checkpointer = await create_async_checkpointer()
    
    # Compile the graph with checkpointer
    return graph_builder.compile(checkpointer=checkpointer)


async def create_async_graph_with_checkpointer(checkpointer):
    """Create async graph with specific checkpointer."""
    print(f"DEBUG: Creating async graph with checkpointer: {type(checkpointer)}")
    
    # Create the graph builder and compile with the provided checkpointer
    graph_builder = await _create_graph_builder()
    async_graph = graph_builder.compile(checkpointer=checkpointer)
    
    print(f"DEBUG: Async graph created successfully with checkpointer: {type(checkpointer)}")
    return async_graph 