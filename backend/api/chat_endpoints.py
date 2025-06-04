"""
Nova Chat API Endpoints

FastAPI endpoints for LangGraph agent compatible with agent-chat-ui patterns.
"""

import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage

from agent.chat_agent import graph


router = APIRouter(prefix="/chat", tags=["chat"])


# Pydantic models for request/response
class ChatMessage(BaseModel):
    """Chat message model."""
    role: str = Field(..., description="Message role (user or assistant)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")
    id: Optional[str] = Field(None, description="Message ID")


class ChatRequest(BaseModel):
    """Chat request model."""
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    thread_id: Optional[str] = Field(None, description="Thread identifier for conversation continuity")
    stream: bool = Field(True, description="Whether to stream the response")


class ChatResponse(BaseModel):
    """Non-streaming chat response model."""
    message: ChatMessage = Field(..., description="Assistant response message")
    thread_id: str = Field(..., description="Thread identifier")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Health status")
    agent_ready: bool = Field(..., description="Whether the agent is ready")
    timestamp: str = Field(..., description="Health check timestamp")


def _convert_messages_to_langchain(messages: List[ChatMessage]) -> List:
    """Convert Pydantic ChatMessage models to LangChain messages.
    
    Args:
        messages: List of Pydantic ChatMessage models
        
    Returns:
        List of LangChain message objects
    """
    langchain_messages = []
    for msg in messages:
        if msg.role == "user":
            langchain_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            langchain_messages.append(AIMessage(content=msg.content))
    return langchain_messages


def _create_config(thread_id: Optional[str] = None) -> Dict[str, Any]:
    """Create configuration for LangGraph agent.
    
    Args:
        thread_id: Optional thread identifier for conversation continuity
        
    Returns:
        Configuration dictionary for the agent
    """
    return {
        "configurable": {
            "thread_id": thread_id or f"chat-{datetime.now().isoformat()}"
        }
    }


@router.post("/stream")
async def stream_chat(request: ChatRequest):
    """
    Stream chat responses from the Nova LangGraph agent.
    
    This endpoint provides real-time streaming responses compatible with agent-chat-ui.
    """
    try:
        # Convert Pydantic models to LangChain messages
        messages = _convert_messages_to_langchain(request.messages)
        
        # Create configuration
        config = _create_config(request.thread_id)
        
        async def generate_response():
            """Generate SSE (Server-Sent Events) response stream."""
            try:
                # Stream from the LangGraph agent
                async for chunk in graph.astream(
                    {"messages": messages}, 
                    config=config
                ):
                    # Handle different types of chunks from LangGraph
                    for node_name, node_output in chunk.items():
                        if "messages" in node_output:
                            for message in node_output["messages"]:
                                if isinstance(message, AIMessage):
                                    # Send message content as it streams
                                    event = {
                                        "type": "message",
                                        "data": {
                                            "role": "assistant",
                                            "content": message.content,
                                            "timestamp": datetime.now().isoformat(),
                                            "node": node_name
                                        }
                                    }
                                    yield f"data: {json.dumps(event)}\n\n"
                                
                                # Handle tool calls
                                if hasattr(message, 'tool_calls') and message.tool_calls:
                                    for tool_call in message.tool_calls:
                                        tool_event = {
                                            "type": "tool_call",
                                            "data": {
                                                "tool": tool_call["name"],
                                                "args": tool_call.get("args", {}),
                                                "timestamp": datetime.now().isoformat()
                                            }
                                        }
                                        yield f"data: {json.dumps(tool_event)}\n\n"
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'complete', 'data': {'timestamp': datetime.now().isoformat()}})}\n\n"
                
            except Exception as e:
                error_event = {
                    "type": "error",
                    "data": {
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                }
                yield f"data: {json.dumps(error_event)}\n\n"
        
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat streaming error: {str(e)}")


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Non-streaming chat endpoint for simple interactions.
    """
    try:
        # Convert Pydantic models to LangChain messages
        messages = _convert_messages_to_langchain(request.messages)
        
        # Create configuration
        config = _create_config(request.thread_id)
        
        # Get response from LangGraph
        result = await graph.ainvoke({"messages": messages}, config=config)
        
        # Extract the last AI message
        last_message = result["messages"][-1]
        response_content = last_message.content if isinstance(last_message, AIMessage) else "No response generated"
        
        # Create response
        response_message = ChatMessage(
            role="assistant",
            content=response_content,
            timestamp=datetime.now().isoformat(),
            id=str(uuid.uuid4())
        )
        
        thread_id = request.thread_id or f"chat-{datetime.now().isoformat()}"
        
        return ChatResponse(
            message=response_message,
            thread_id=thread_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.get("/health", response_model=HealthResponse)
async def chat_health():
    """
    Health check endpoint for chat functionality.
    """
    try:
        # Test if the graph is available and working
        agent_ready = graph is not None
        
        return HealthResponse(
            status="healthy" if agent_ready else "degraded",
            agent_ready=agent_ready,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            agent_ready=False,
            timestamp=datetime.now().isoformat()
        )


@router.get("/tools")
async def get_available_tools():
    """
    Get list of available tools that the agent can use.
    """
    try:
        from tools import get_all_tools
        
        tools = get_all_tools()
        tools_info = []
        
        for tool in tools:
            tools_info.append({
                "name": tool.name,
                "description": tool.description,
                "args_schema": tool.args_schema.model_json_schema() if hasattr(tool, 'args_schema') and tool.args_schema else {}
            })
        
        return {
            "tools": tools_info,
            "count": len(tools_info),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tools error: {str(e)}") 