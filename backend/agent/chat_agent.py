"""
Nova LangGraph Chat Agent

A LangGraph chat agent that integrates with Nova's tools and follows the agent-chat-ui patterns.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Dict, List, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode

from tools import get_all_tools
from config import settings


class Configuration(TypedDict):
    """Configurable parameters for the agent.
    
    This allows the agent-chat-ui to pass configuration parameters.
    """
    model_name: str
    temperature: float


def create_model(config: RunnableConfig) -> ChatGoogleGenerativeAI:
    """Create and configure the Google Gemini model."""
    api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    # Get configuration values with defaults
    configuration = config.get("configurable", {})
    model_name = configuration.get("model_name", settings.GOOGLE_MODEL_NAME or "gemini-2.5-flash-preview-04-17")
    temperature = configuration.get("temperature", 0.7)
    
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=temperature,
        max_tokens=2048,
    )


async def call_model(state: MessagesState, config: RunnableConfig) -> Dict[str, Any]:
    """Generate a response using Google Gemini with Nova tools.
    
    Takes the conversation history and generates an AI response, potentially using tools.
    """
    model = create_model(config)
    
    # Get Nova tools
    tools = get_all_tools()
    
    # Bind tools to the model
    model_with_tools = model.bind_tools(tools)
    
    # Add system message with Nova's personality and capabilities
    messages = state["messages"]
    if not messages or not any(isinstance(msg, type(messages[0])) and hasattr(msg, 'type') and getattr(msg, 'type', None) == 'system' for msg in messages):
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
    response = await model_with_tools.ainvoke(messages)
    
    # Return the new AI message - LangGraph will handle appending to conversation
    return {"messages": [response]}


def should_continue(state: MessagesState) -> str:
    """Determine whether to continue with tool calls or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the last message has tool calls, continue to tools
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    # Otherwise, end the conversation turn
    return END


# Create the graph
def create_graph():
    """Create and compile the LangGraph chat agent."""
    # Get Nova tools for the tool node
    tools = get_all_tools()
    
    # Use MessagesState which automatically handles message history
    workflow = StateGraph(MessagesState, config_schema=Configuration)
    
    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    
    # Set entry point
    workflow.add_edge(START, "agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END,
        }
    )
    
    # After tools, go back to agent
    workflow.add_edge("tools", "agent")
    
    # Compile the graph - LangGraph server handles persistence automatically
    return workflow.compile()


# The main graph instance
graph = create_graph()


# Test function for development
async def test_graph():
    """Test the LangGraph agent."""
    from langchain_core.messages import HumanMessage
    
    print("\n🧪 Testing Nova LangGraph Agent...")
    
    # Test basic conversation
    result = await graph.ainvoke({
        "messages": [HumanMessage(content="Hello! What can you help me with?")]
    })
    
    print(f"Response: {result['messages'][-1].content}")
    
    # Test tool usage
    result = await graph.ainvoke({
        "messages": [HumanMessage(content="Create a new task called 'Test LangGraph integration'")]
    })
    
    print(f"Tool response: {result['messages'][-1].content}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_graph()) 