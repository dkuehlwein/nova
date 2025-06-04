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

from agent.chat_agent import graph, create_async_graph


router = APIRouter(prefix="/chat", tags=["chat"])

# Global async graph instance for streaming endpoints
_async_graph = None

async def get_async_graph():
    """Get or create the async graph instance."""
    global _async_graph
    if _async_graph is None:
        print("DEBUG: Creating new async graph instance")
        _async_graph = await create_async_graph()
        print(f"DEBUG: Created async graph with checkpointer: {type(_async_graph.checkpointer)}")
    else:
        print("DEBUG: Reusing existing async graph instance")
    return _async_graph


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


# Models for chat management
class ChatSummary(BaseModel):
    """Chat summary for listing chats."""
    id: str = Field(..., description="Chat thread ID")
    title: str = Field(..., description="Chat title")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    last_message: Optional[str] = Field(None, description="Last message preview")
    last_activity: Optional[str] = Field(None, description="Last activity timestamp")
    has_decision: bool = Field(False, description="Whether chat needs user decision")
    message_count: int = Field(0, description="Number of messages in chat")


class ChatMessageDetail(BaseModel):
    """Detailed chat message for message history."""
    id: str = Field(..., description="Message ID")
    sender: str = Field(..., description="Message sender (user or assistant)")
    content: str = Field(..., description="Message content")
    created_at: str = Field(..., description="Message creation timestamp")
    needs_decision: bool = Field(False, description="Whether message needs user decision")


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


async def _get_chat_history(thread_id: str) -> List[ChatMessageDetail]:
    """Get chat history from the checkpointer.
    
    Args:
        thread_id: Chat thread identifier
        
    Returns:
        List of chat messages
    """
    try:
        config = _create_config(thread_id)
        
        # Get the async graph and its checkpointer
        async_graph = await get_async_graph()
        checkpointer = async_graph.checkpointer
        
        # Get the current state from the checkpointer
        state = await checkpointer.aget(config)
        
        print(f"DEBUG: Getting chat history for {thread_id}, state type: {type(state)}")
        
        if not state:
            print(f"DEBUG: No state found for thread {thread_id}")
            return []
            
        # Fix: Access messages from channel_values, not from state.values()
        channel_values = state.get('channel_values', {})
        if "messages" not in channel_values:
            print(f"DEBUG: No messages in state for thread {thread_id}, keys: {list(state.keys())}")
            print(f"DEBUG: Channel values keys: {list(channel_values.keys())}")
            return []
        
        messages = channel_values["messages"]
        chat_messages = []
        
        print(f"DEBUG: Found {len(messages)} messages in state")
        
        for i, msg in enumerate(messages):
            if isinstance(msg, (HumanMessage, AIMessage)):
                chat_messages.append(ChatMessageDetail(
                    id=f"{thread_id}-msg-{i}",
                    sender="user" if isinstance(msg, HumanMessage) else "assistant",
                    content=str(msg.content),
                    created_at=datetime.now().isoformat(),  # TODO: Use actual timestamp if available
                    needs_decision=False  # TODO: Implement decision detection logic
                ))
        
        print(f"DEBUG: Returning {len(chat_messages)} chat messages")
        return chat_messages
        
    except Exception as e:
        print(f"Error getting chat history for {thread_id}: {e}")
        import traceback
        traceback.print_exc()
        return []


async def _list_chat_threads() -> List[str]:
    """List all chat thread IDs from the checkpointer.
    
    Returns:
        List of thread IDs
    """
    try:
        # Get the async graph and its checkpointer
        async_graph = await get_async_graph()
        checkpointer = async_graph.checkpointer
        
        print(f"DEBUG: Checkpointer type: {type(checkpointer)}")
        print(f"DEBUG: Checkpointer instance id: {id(checkpointer)}")
        
        # For MemorySaver, we need to provide a config parameter
        from langgraph.checkpoint.memory import MemorySaver
        
        if isinstance(checkpointer, MemorySaver):
            # For MemorySaver, use alist(None) to get ALL checkpoints then extract unique thread_ids
            thread_ids = []
            try:
                print(f"DEBUG: MemorySaver internal storage keys: {list(checkpointer.storage.keys()) if hasattr(checkpointer, 'storage') else 'No storage attr'}")
                
                checkpoint_count = 0
                # Use None to get ALL checkpoints, not filtered by thread_id
                async for checkpoint_tuple in checkpointer.alist(None):
                    checkpoint_count += 1
                    if checkpoint_tuple.config and checkpoint_tuple.config.get("configurable", {}).get("thread_id"):
                        thread_id = checkpoint_tuple.config["configurable"]["thread_id"]
                        # Only add non-empty thread_ids and avoid duplicates
                        if thread_id and thread_id not in thread_ids:
                            thread_ids.append(thread_id)
                            print(f"DEBUG: Added unique thread_id: {thread_id}")
                
                print(f"DEBUG: Total checkpoints found: {checkpoint_count}, unique threads: {len(thread_ids)}")
                print(f"DEBUG: Unique thread IDs: {thread_ids}")
                
            except Exception as e:
                print(f"Error listing threads from MemorySaver: {e}")
            return thread_ids
        
        # For PostgreSQL checkpointers, we need to properly handle the async generator
        elif hasattr(checkpointer, 'alist'):
            thread_ids = []
            # Use async for to properly consume the async generator
            async for thread_metadata in checkpointer.alist():
                if thread_metadata and hasattr(thread_metadata, 'config'):
                    thread_id = thread_metadata.config.get("configurable", {}).get("thread_id")
                    if thread_id:
                        thread_ids.append(thread_id)
                elif isinstance(thread_metadata, dict):
                    # Handle case where thread_metadata is a dict
                    thread_id = thread_metadata.get("thread_id") or thread_metadata.get("configurable", {}).get("thread_id")
                    if thread_id:
                        thread_ids.append(thread_id)
            return thread_ids
        else:
            # For other checkpointers that can't list threads, return empty
            print(f"DEBUG: Checkpointer doesn't support listing threads")
            return []
            
    except Exception as e:
        print(f"Error listing chat threads: {e}")
        return []


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
        thread_id = config["configurable"]["thread_id"]
        
        print(f"DEBUG: Streaming chat for thread_id: {thread_id}")
        print(f"DEBUG: Input messages count: {len(messages)}")
        
        # Get the async graph instance
        async_graph = await get_async_graph()
        
        print(f"DEBUG: Using checkpointer: {type(async_graph.checkpointer)} (id: {id(async_graph.checkpointer)})")
        
        async def generate_response():
            """Generate SSE (Server-Sent Events) response stream."""
            try:
                # Stream from the LangGraph agent using async graph
                async for chunk in async_graph.astream(
                    {"messages": messages}, 
                    config=config
                ):
                    print(f"DEBUG: Received chunk from node: {list(chunk.keys())}")
                    # Handle different types of chunks from LangGraph
                    for node_name, node_output in chunk.items():
                        if "messages" in node_output:
                            for message in node_output["messages"]:
                                if isinstance(message, AIMessage):
                                    print(f"DEBUG: Streaming AI message: {message.content[:50]}...")
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
                
                print(f"DEBUG: Finished streaming for thread_id: {thread_id}")
                
                # DEBUG: Check if checkpoints were actually saved
                try:
                    from langgraph.checkpoint.memory import MemorySaver
                    checkpointer = async_graph.checkpointer
                    print(f"DEBUG: Checking saved checkpoints for thread {thread_id}")
                    
                    # Try to get the current state to see if anything was saved
                    current_state = await checkpointer.aget(config)
                    if current_state:
                        print(f"DEBUG: Found current state: {current_state.get('channel_values', {}).keys()}")
                        if 'messages' in current_state.get('channel_values', {}):
                            messages_count = len(current_state['channel_values']['messages'])
                            print(f"DEBUG: State contains {messages_count} messages")
                    else:
                        print(f"DEBUG: No current state found for thread {thread_id}")
                    
                    # Check internal storage directly
                    if hasattr(checkpointer, 'storage'):
                        print(f"DEBUG: Internal storage keys after conversation: {list(checkpointer.storage.keys())}")
                        for key, value in checkpointer.storage.items():
                            print(f"DEBUG: Storage key: {key}")
                    
                    # Try to list checkpoints for this specific thread
                    if isinstance(checkpointer, MemorySaver):
                        checkpoint_count = 0
                        print(f"DEBUG: Calling alist with config: {config}")
                        async for checkpoint_tuple in checkpointer.alist(config):
                            checkpoint_count += 1
                            print(f"DEBUG: Post-stream checkpoint {checkpoint_count}: {checkpoint_tuple.config}")
                        print(f"DEBUG: Total checkpoints after streaming: {checkpoint_count}")
                        
                        # Try with just the thread_id config to see if that works
                        simple_config = {"configurable": {"thread_id": thread_id}}
                        print(f"DEBUG: Trying with simple config: {simple_config}")
                        simple_count = 0
                        async for checkpoint_tuple in checkpointer.alist(simple_config):
                            simple_count += 1
                            print(f"DEBUG: Simple config checkpoint {simple_count}: {checkpoint_tuple.config}")
                        print(f"DEBUG: Simple config checkpoints: {simple_count}")
                    
                except Exception as debug_error:
                    print(f"DEBUG: Error checking checkpoints: {debug_error}")
                    import traceback
                    traceback.print_exc()
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'complete', 'data': {'timestamp': datetime.now().isoformat()}})}\n\n"
                
            except Exception as e:
                print(f"DEBUG: Error during streaming: {e}")
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


# Chat Management Endpoints

@router.get("/conversations", response_model=List[ChatSummary])
async def list_chats():
    """
    List all chat conversations.
    """
    try:
        thread_ids = await _list_chat_threads()
        chat_summaries = []
        
        for thread_id in thread_ids:
            try:
                messages = await _get_chat_history(thread_id)
                
                if not messages:
                    continue
                
                # Create title from first user message
                first_user_msg = next((msg for msg in messages if msg.sender == "user"), None)
                title = first_user_msg.content[:50] + "..." if first_user_msg and len(first_user_msg.content) > 50 else (first_user_msg.content if first_user_msg else "New Chat")
                
                # Get last message
                last_message = messages[-1] if messages else None
                
                chat_summaries.append(ChatSummary(
                    id=thread_id,
                    title=title,
                    created_at=messages[0].created_at if messages else datetime.now().isoformat(),
                    updated_at=last_message.created_at if last_message else datetime.now().isoformat(),
                    last_message=last_message.content[:100] + "..." if last_message and len(last_message.content) > 100 else (last_message.content if last_message else ""),
                    last_activity=last_message.created_at if last_message else datetime.now().isoformat(),
                    has_decision=any(msg.needs_decision for msg in messages),
                    message_count=len(messages)
                ))
                
            except Exception as msg_error:
                print(f"Error processing chat {thread_id}: {msg_error}")
                continue
        
        # Sort by last activity (most recent first)
        chat_summaries.sort(key=lambda x: x.updated_at, reverse=True)
        
        return chat_summaries
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing chats: {str(e)}")


@router.get("/conversations/{chat_id}", response_model=ChatSummary)
async def get_chat(chat_id: str):
    """
    Get a specific chat conversation summary.
    """
    try:
        messages = await _get_chat_history(chat_id)
        
        if not messages:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Create title from first user message
        first_user_msg = next((msg for msg in messages if msg.sender == "user"), None)
        title = first_user_msg.content[:50] + "..." if first_user_msg and len(first_user_msg.content) > 50 else (first_user_msg.content if first_user_msg else "New Chat")
        
        # Get last message
        last_message = messages[-1] if messages else None
        
        return ChatSummary(
            id=chat_id,
            title=title,
            created_at=messages[0].created_at if messages else datetime.now().isoformat(),
            updated_at=last_message.created_at if last_message else datetime.now().isoformat(),
            last_message=last_message.content[:100] + "..." if last_message and len(last_message.content) > 100 else (last_message.content if last_message else ""),
            last_activity=last_message.created_at if last_message else datetime.now().isoformat(),
            has_decision=any(msg.needs_decision for msg in messages),
            message_count=len(messages)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chat: {str(e)}")


@router.get("/conversations/{chat_id}/messages", response_model=List[ChatMessageDetail])
async def get_chat_messages(chat_id: str):
    """
    Get messages for a specific chat conversation.
    """
    try:
        messages = await _get_chat_history(chat_id)
        return messages
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chat messages: {str(e)}") 