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

from agent.chat_agent import create_chat_agent
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Global chat agent instance for streaming endpoints
_chat_agent = None

async def get_chat_agent():
    """Get or create the chat agent instance."""
    global _chat_agent
    if _chat_agent is None:
        logger.info("Creating new chat agent instance")
        try:
            _chat_agent = await create_chat_agent()
            logger.info(f"Created chat agent with checkpointer: {type(_chat_agent.checkpointer)}")
        except Exception as e:
            logger.error(f"Error creating chat agent: {e}")
            raise
    else:
        logger.debug("Reusing existing chat agent instance")
    return _chat_agent


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


async def _get_chat_history_with_checkpointer(thread_id: str, checkpointer) -> List[ChatMessageDetail]:
    """Get chat history from a specific checkpointer.
    
    Args:
        thread_id: Chat thread identifier
        checkpointer: Checkpointer instance to use
        
    Returns:
        List of chat messages (reconstructed to match streaming experience)
    """
    try:
        config = _create_config(thread_id)
        
        # Get the current state from the checkpointer
        state = await checkpointer.aget(config)
        
        logger.debug(f"Getting chat history for {thread_id}, state type: {type(state)}")
        
        if not state:
            logger.debug(f"No state found for thread {thread_id}")
            return []
            
        # Access messages from channel_values
        channel_values = state.get('channel_values', {})
        if "messages" not in channel_values:
            logger.debug(f"No messages in state for thread {thread_id}, available keys: {list(channel_values.keys())}")
            return []
        
        messages = channel_values["messages"]
        chat_messages = []
        
        logger.debug(f"Found {len(messages)} raw messages in state")
        
        # Process messages and reconstruct AI message content to match streaming experience
        i = 0
        while i < len(messages):
            msg = messages[i]
            
            # Process each message type
            logger.debug(f"Processing message {i}: {type(msg).__name__}")
            
            if isinstance(msg, HumanMessage):
                # Always include user messages
                chat_messages.append(ChatMessageDetail(
                    id=f"{thread_id}-msg-{i}",
                    sender="user",
                    content=str(msg.content),
                    created_at=datetime.now().isoformat(),  # TODO: Use actual timestamp if available
                    needs_decision=False  # TODO: Implement decision detection logic
                ))
                logger.debug(f"Included user message: '{str(msg.content)[:50]}...'")
                
            elif isinstance(msg, AIMessage):
                # For AI messages, reconstruct the complete content including tool calls
                ai_content = str(msg.content).strip()
                
                # Check if this AI message has tool calls
                has_tool_calls = hasattr(msg, 'tool_calls') and bool(getattr(msg, 'tool_calls', None))
                
                if has_tool_calls:
                    # Get the tool calls to include in the message
                    tool_calls = getattr(msg, 'tool_calls', [])
                    logger.debug(f"AI message has {len(tool_calls)} tool calls")
                    
                    # If the AI message has no content but has tool calls, start with empty content
                    if not ai_content or ai_content in ['', 'null', 'None']:
                        ai_content = ""
                    
                    # Add tool call indicators (matching streaming format)
                    for tool_call in tool_calls:
                        tool_name = tool_call.get('name', 'unknown') if isinstance(tool_call, dict) else getattr(tool_call, 'name', 'unknown')
                        if ai_content:
                            ai_content += f"\n\n🔧 Using tool: {tool_name}..."
                        else:
                            ai_content = f"🔧 Using tool: {tool_name}..."
                    
                    # Look ahead for ToolMessage results and the final AI response
                    j = i + 1
                    while j < len(messages):
                        next_msg = messages[j]
                        if isinstance(next_msg, AIMessage):
                            # This is the final AI response after tool execution
                            final_content = str(next_msg.content).strip()
                            if final_content and final_content not in ['', 'null', 'None']:
                                if ai_content:
                                    ai_content += f"\n\n{final_content}"
                                else:
                                    ai_content = final_content
                                logger.debug(f"Added final AI response: '{final_content[:50]}...'")
                            # Skip this message in the outer loop since we've processed it
                            i = j
                            break
                        elif isinstance(next_msg, type(msg)) and not isinstance(next_msg, (HumanMessage, AIMessage)):
                            # Skip ToolMessage and other internal messages
                            logger.debug(f"Skipping {type(next_msg).__name__} at position {j}")
                        j += 1
                
                # Only include AI messages that have actual content
                if ai_content and ai_content not in ['', 'null', 'None']:
                    chat_messages.append(ChatMessageDetail(
                        id=f"{thread_id}-msg-{i}",
                        sender="assistant",
                        content=ai_content,
                        created_at=datetime.now().isoformat(),
                        needs_decision=False
                    ))
                    logger.debug(f"Included AI message with reconstructed content: '{ai_content[:100]}...'")
                else:
                    logger.debug(f"Skipped AI message with no content after reconstruction")
            else:
                # Skip other message types (ToolMessage, SystemMessage, etc.)
                logger.debug(f"Skipped message type: {type(msg).__name__}")
            
            i += 1
        
        logger.debug(f"Returning {len(chat_messages)} chat messages (from {len(messages)} total)")
        return chat_messages
        
    except Exception as e:
        logger.error(f"Error getting chat history for {thread_id}: {e}")
        return []


async def _list_chat_threads(request: Request) -> List[str]:
    """List all chat thread IDs from the checkpointer.
    
    Args:
        request: FastAPI request object to access app state
        
    Returns:
        List of thread IDs
    """
    try:
        # Get the appropriate checkpointer from app state
        checkpointer = await get_checkpointer_from_app(request)
        
        logger.debug(f"Checkpointer type: {type(checkpointer)}")
        
        # For MemorySaver, we need to provide a config parameter
        from langgraph.checkpoint.memory import MemorySaver
        
        if isinstance(checkpointer, MemorySaver):
            # For MemorySaver, use alist(None) to get ALL checkpoints then extract unique thread_ids
            thread_ids = []
            try:
                checkpoint_count = 0
                # Use None to get ALL checkpoints, not filtered by thread_id
                async for checkpoint_tuple in checkpointer.alist(None):
                    checkpoint_count += 1
                    if checkpoint_tuple.config and checkpoint_tuple.config.get("configurable", {}).get("thread_id"):
                        thread_id = checkpoint_tuple.config["configurable"]["thread_id"]
                        # Only add non-empty thread_ids and avoid duplicates
                        if thread_id and thread_id not in thread_ids:
                            thread_ids.append(thread_id)
                            logger.debug(f"Added unique thread_id: {thread_id}")
                
                logger.debug(f"Total checkpoints found: {checkpoint_count}, unique threads: {len(thread_ids)}")
                
            except Exception as e:
                logger.error(f"Error listing threads from MemorySaver: {e}")
            return thread_ids
        
        # For PostgreSQL checkpointers, we need to properly handle the async generator
        elif hasattr(checkpointer, 'alist'):
            thread_ids = []
            try:
                # For PostgreSQL, get all checkpoints first
                checkpoint_count = 0
                async for checkpoint_tuple in checkpointer.alist(None):
                    checkpoint_count += 1
                    if checkpoint_tuple.config and checkpoint_tuple.config.get("configurable", {}).get("thread_id"):
                        thread_id = checkpoint_tuple.config["configurable"]["thread_id"]
                        # Only add non-empty thread_ids and avoid duplicates
                        if thread_id and thread_id not in thread_ids:
                            thread_ids.append(thread_id)
                            logger.debug(f"Added PostgreSQL thread_id: {thread_id}")
                
                logger.debug(f"PostgreSQL total checkpoints found: {checkpoint_count}, unique threads: {len(thread_ids)}")
                
            except Exception as e:
                logger.error(f"Error listing threads from PostgreSQL: {e}")
            return thread_ids
        else:
            # For other checkpointers that can't list threads, return empty
            logger.debug(f"Checkpointer doesn't support listing threads")
            return []
            
    except Exception as e:
        logger.error(f"Error listing chat threads: {e}")
        return []


async def get_checkpointer_from_app(request: Request):
    """Get the appropriate checkpointer based on app state."""
    try:
        # Check if we have a PostgreSQL connection pool available
        if hasattr(request.app.state, 'pg_pool') and request.app.state.pg_pool:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            logger.debug("Using PostgreSQL checkpointer from app state")
            return AsyncPostgresSaver(request.app.state.pg_pool)
        else:
            logger.debug("No PostgreSQL pool available, using MemorySaver")
            from langgraph.checkpoint.memory import MemorySaver
            return MemorySaver()
    except Exception as e:
        logger.error(f"Error creating checkpointer: {e}")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()


@router.post("/stream")
async def stream_chat(request: Request, chat_request: ChatRequest):
    """Stream chat messages with the assistant."""
    try:
        logger.info(f"Streaming chat for thread_id: {chat_request.thread_id}")
        logger.debug(f"Input messages count: {len(chat_request.messages)}")
        
        # Get the appropriate checkpointer
        logger.debug("Getting checkpointer from app state...")
        checkpointer = await get_checkpointer_from_app(request)
        logger.debug(f"Checkpointer obtained: {type(checkpointer)}")
        
        # Create a new chat agent instance with the checkpointer for this request
        logger.info("Creating chat agent with checkpointer...")
        try:
            from agent.chat_agent import create_chat_agent
            chat_agent = await create_chat_agent(checkpointer=checkpointer)
            logger.info(f"Using checkpointer: {type(checkpointer)} (id: {id(checkpointer)})")
            logger.info("Chat agent created successfully")
        except Exception as agent_error:
            logger.error(f"Failed to create chat agent: {agent_error}")
            raise HTTPException(status_code=500, detail=f"Failed to create chat agent: {str(agent_error)}")
        
        # Create config
        logger.debug("Creating config...")
        config = _create_config(chat_request.thread_id)
        logger.debug(f"Config created: {config}")
        
        # Convert Pydantic models to LangChain messages
        logger.debug("Converting messages...")
        try:
            messages = _convert_messages_to_langchain(chat_request.messages)
            logger.debug(f"Converted {len(messages)} messages to LangChain format")
        except Exception as convert_error:
            logger.error(f"Failed to convert messages: {convert_error}")
            raise HTTPException(status_code=500, detail=f"Failed to convert messages: {str(convert_error)}")
        
        logger.debug(f"Starting stream for thread_id: {chat_request.thread_id} with {len(messages)} messages")
        
        async def generate_response():
            """Generate SSE (Server-Sent Events) response stream."""
            try:
                logger.debug("Starting to stream from LangGraph...")
                # Stream from the LangGraph agent
                stream_count = 0
                async for chunk in chat_agent.astream(
                    {"messages": messages}, 
                    config=config
                ):
                    stream_count += 1
                    logger.debug(f"Received chunk #{stream_count} from node: {list(chunk.keys())}")
                    # Handle different types of chunks from LangGraph
                    for node_name, node_output in chunk.items():
                        if "messages" in node_output:
                            for message in node_output["messages"]:
                                if isinstance(message, AIMessage):
                                    logger.debug(f"Streaming AI message: {message.content[:50]}...")
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
                
                logger.info(f"Finished streaming for thread_id: {chat_request.thread_id} after {stream_count} chunks")
                
                # Verify checkpoints were saved
                try:
                    checkpointer = chat_agent.checkpointer
                    current_state = await checkpointer.aget(config)
                    if current_state and 'messages' in current_state.get('channel_values', {}):
                        messages_count = len(current_state['channel_values']['messages'])
                        logger.debug(f"Conversation saved: {messages_count} messages in thread {chat_request.thread_id}")
                    else:
                        logger.warning(f"No state found for thread {chat_request.thread_id} after streaming")
                    
                except Exception as checkpoint_error:
                    logger.error(f"Error verifying checkpoints: {checkpoint_error}")
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'complete', 'data': {'timestamp': datetime.now().isoformat()}})}\n\n"
                
            except Exception as e:
                logger.error(f"Error during streaming: {e}")
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
        
        # Get chat agent instance
        chat_agent = await get_chat_agent()
        
        # Get response from LangGraph
        result = await chat_agent.ainvoke({"messages": messages}, config=config)
        
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
        # Test if the chat agent can be created and is working
        chat_agent = await get_chat_agent()
        agent_ready = chat_agent is not None
        
        return HealthResponse(
            status="healthy" if agent_ready else "degraded",
            agent_ready=agent_ready,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
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
        from agent.chat_agent import get_all_tools_with_mcp
        
        tools = await get_all_tools_with_mcp()
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
async def list_chats(request: Request):
    """
    List all chat conversations.
    """
    try:
        # Get checkpointer from app state
        checkpointer = await get_checkpointer_from_app(request)
        
        thread_ids = await _list_chat_threads(request)
        chat_summaries = []
        
        for thread_id in thread_ids:
            try:
                messages = await _get_chat_history_with_checkpointer(thread_id, checkpointer)
                
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
async def get_chat(request: Request, chat_id: str):
    """
    Get a specific chat conversation summary.
    """
    try:
        checkpointer = await get_checkpointer_from_app(request)
        messages = await _get_chat_history_with_checkpointer(chat_id, checkpointer)
        
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
async def get_chat_messages(request: Request, chat_id: str):
    """
    Get messages for a specific chat conversation.
    """
    try:
        checkpointer = await get_checkpointer_from_app(request)
        messages = await _get_chat_history_with_checkpointer(chat_id, checkpointer)
        return messages
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chat messages: {str(e)}") 