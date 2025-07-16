"""
Nova Chat API Endpoints

FastAPI endpoints for LangGraph agent compatible with agent-chat-ui patterns.
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage


from models.chat import (
    ChatMessage, ChatRequest, ChatSummary, 
    ChatMessageDetail, TaskChatResponse
)
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


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
    """Create configuration for LangGraph with thread ID."""
    if thread_id is None:
        thread_id = f"chat-{datetime.now().isoformat()}"
    
    return {
        "configurable": {
            "thread_id": thread_id
        }
    }


async def _is_first_turn(thread_id: str, checkpointer) -> bool:
    """Check if this is the first turn in a conversation by querying the checkpointer.
    
    Args:
        thread_id: The conversation thread ID
        checkpointer: The checkpointer instance to query
        
    Returns:
        True if this is the first turn (no previous messages), False otherwise
    """
    config = _create_config(thread_id)
    try:
        state = await checkpointer.aget(config)
        if not state:
            return True  # No checkpoint yet - first turn
        
        messages = state.get("channel_values", {}).get("messages", [])
        return len(messages) == 0  # Checkpoint exists but no messages yet
        
    except Exception as e:
        logger.warning(f"Could not inspect checkpoints for {thread_id}: {e}")
        return False  # Be safe - treat as not-first to avoid memory search on errors


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
        
        # Get the checkpoint timestamp as fallback only
        checkpoint_timestamp = state.get('ts', datetime.now().isoformat())
        
        logger.debug(f"Found {len(messages)} raw messages in state, checkpoint timestamp: {checkpoint_timestamp}")
        
        # If there are no messages, return empty (no system message needed for empty conversations)
        if not messages:
            return []
        
        # Build a mapping of message ID to creation timestamp by analyzing checkpoint history
        logger.debug("Building message ID to timestamp mapping from checkpoint history...")
        message_to_timestamp = {}
        
        try:
            # Get full checkpoint history
            history = []
            async for checkpoint_tuple in checkpointer.alist(config):
                history.append(checkpoint_tuple)
            
            # Sort by timestamp (oldest first) to get chronological order
            history.sort(key=lambda x: x.checkpoint.get('ts', ''))
            
            # Go through each checkpoint and map messages to when they were first added
            for checkpoint_tuple in history:
                checkpoint = checkpoint_tuple.checkpoint
                metadata = checkpoint_tuple.metadata
                checkpoint_ts = checkpoint.get('ts')
                
                # Check writes to see what messages were added in this checkpoint
                writes = metadata.get('writes', {})
                if writes:
                    for key, value in writes.items():
                        if isinstance(value, dict) and 'messages' in value:
                            for msg in value['messages']:
                                if hasattr(msg, 'id') and msg.id:
                                    # Only map if we haven't seen this message ID before
                                    if msg.id not in message_to_timestamp:
                                        message_to_timestamp[msg.id] = checkpoint_ts
                                        logger.debug(f"Mapped message {msg.id} -> {checkpoint_ts}")
            
            logger.debug(f"Successfully mapped {len(message_to_timestamp)} messages to timestamps")
            
        except Exception as e:
            logger.warning(f"Error building message timestamp mapping: {e}")
            # Fallback to checkpoint timestamp for all messages
            message_to_timestamp = {}
        
        # Helper function to get message timestamp
        def get_message_timestamp(msg, fallback_timestamp: str) -> str:
            """Get timestamp for a message from our ID mapping."""
            if hasattr(msg, 'id') and msg.id and msg.id in message_to_timestamp:
                return message_to_timestamp[msg.id]
            return fallback_timestamp        

        # First pass: collect all tool results by tool_call_id
        tool_results = {}  # tool_call_id -> tool result content
        for msg in messages:
            if isinstance(msg, ToolMessage):
                if hasattr(msg, 'tool_call_id') and msg.tool_call_id:
                    tool_results[msg.tool_call_id] = {
                        'content': str(msg.content),
                        'name': getattr(msg, 'name', 'unknown'),
                        'tool_call_id': msg.tool_call_id
                    }
        
        logger.debug(f"Collected {len(tool_results)} tool results")
        
        # Process the actual conversation messages from LangGraph
        for i, msg in enumerate(messages):
            # Process each message type
            logger.debug(f"Processing message {i}: {type(msg).__name__}")
            message_timestamp = get_message_timestamp(msg, checkpoint_timestamp)
            
            
            if isinstance(msg, HumanMessage):
                chat_messages.append(ChatMessageDetail(
                    id=f"{thread_id}-msg-{i}",
                    sender="user",
                    content=str(msg.content),
                    created_at=message_timestamp,
                    needs_decision=False
                ))
                logger.debug(f"Included user message: '{str(msg.content)[:50]}...' with timestamp: {message_timestamp}")
            elif isinstance(msg, AIMessage):
                # For AI messages, keep content and tool calls separate (consistent with streaming)
                ai_content = str(msg.content).strip()
                
                # Check if this AI message has tool calls
                has_tool_calls = hasattr(msg, 'tool_calls') and bool(getattr(msg, 'tool_calls', None))
                
                # Prepare tool calls data for frontend (same format as streaming)
                message_tool_calls = []
                if has_tool_calls:
                    tool_calls = getattr(msg, 'tool_calls', [])
                    logger.debug(f"AI message has {len(tool_calls)} tool calls")
                    
                    for tool_call in tool_calls:
                        tool_name = tool_call.get('name', 'unknown') if isinstance(tool_call, dict) else getattr(tool_call, 'name', 'unknown')
                        tool_args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
                        tool_call_id = tool_call.get('id') if isinstance(tool_call, dict) else getattr(tool_call, 'id', None)
                        
                        # Create tool call object matching streaming format
                        tool_call_obj = {
                            'tool': tool_name,
                            'args': tool_args,
                            'timestamp': message_timestamp,
                            'tool_call_id': tool_call_id
                        }
                        
                        # Add result if available
                        if tool_call_id and tool_call_id in tool_results:
                            result = tool_results[tool_call_id]
                            tool_call_obj['result'] = result['content']
                        
                        message_tool_calls.append(tool_call_obj)
                
                # Include AI messages with content OR tool calls (consistent with streaming)
                if (ai_content and ai_content not in ['', 'null', 'None']) or message_tool_calls:
                    # Check for explicit metadata (consistent approach for all context types)
                    metadata = None
                    if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('metadata'):
                        # Always preserve existing metadata (memory_context, task_context, etc.)
                        metadata = msg.additional_kwargs['metadata']
                        logger.debug(f"Found message with explicit metadata type: {metadata.get('type', 'unknown')}")
                    elif thread_id.startswith("core_agent_task_") and "**Current Task:**" in ai_content:
                        # Only detect current task introduction (no metadata)
                        metadata = {
                            "type": "task_introduction"
                        }
                    chat_messages.append(ChatMessageDetail(
                        id=f"{thread_id}-msg-{i}",
                        sender="assistant",
                        content=ai_content or "",  # Allow empty content if there are tool calls
                        created_at=message_timestamp,
                        needs_decision=False,
                        metadata=metadata,
                        tool_calls=message_tool_calls if message_tool_calls else None
                    ))
                    logger.debug(f"Included AI message with content: '{ai_content[:100] if ai_content else 'empty'}...' and {len(message_tool_calls)} tool calls with timestamp: {message_timestamp}")
                else:
                    logger.debug(f"Skipped AI message with no content and no tool calls")
            else:
                # Skip other message types (ToolMessage, SystemMessage, etc.)
                logger.debug(f"Skipped message type: {type(msg).__name__}")
        
        logger.debug(f"Returning {len(chat_messages)} chat messages (from {len(messages)} total)")
        return chat_messages
        
    except Exception as e:
        logger.error(f"Error getting chat history for {thread_id}: {e}")
        return []


async def _list_chat_threads() -> List[str]:
    """List all chat thread IDs from the PostgreSQL checkpointer.
    
    Returns:
        List of unique thread IDs from all conversations
    """
    try:
        # Get the PostgreSQL checkpointer from app state
        checkpointer = await get_checkpointer_from_service_manager()
        
        logger.debug(f"Checkpointer type: {type(checkpointer)}")
        
        # For PostgreSQL checkpointers, we need to properly handle the async generator
        if hasattr(checkpointer, 'alist'):
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
            # Unsupported checkpointer type
            logger.error(f"Unsupported checkpointer type: {type(checkpointer)}")
            return []
            
    except Exception as e:
        logger.error(f"Error listing chat threads: {e}")
        return []


async def get_checkpointer_from_service_manager():
    """Get the PostgreSQL checkpointer from ServiceManager."""
    try:
        # Import here to avoid circular dependency
        from start_website import get_service_manager
        from utils.service_manager import create_postgres_checkpointer
        
        logger.info("Getting service manager...")
        service_manager = get_service_manager()
        logger.info(f"Service manager: {service_manager}, pg_pool: {service_manager.pg_pool}")
        
        # The service manager is not unique and different from the one in the app lifespan.
        if service_manager.pg_pool is None:
            logger.info("PostgreSQL pool is None, initializing...")
            await service_manager.init_pg_pool()
            logger.info(f"After init_pg_pool, pg_pool: {service_manager.pg_pool}")
        
        if service_manager.pg_pool:
            logger.info("Using PostgreSQL checkpointer from ServiceManager", extra={
                "data": {"pool_id": id(service_manager.pg_pool)}
            })
            checkpointer = create_postgres_checkpointer(service_manager.pg_pool)
            logger.info(f"Created checkpointer: {checkpointer}")
            return checkpointer
        else:
            # PostgreSQL is mandatory - raise error if not available
            logger.error("PostgreSQL connection pool is still None after init")
            raise RuntimeError("PostgreSQL connection pool is required but not available")
            
    except Exception as e:
        logger.error(f"Error creating PostgreSQL checkpointer: {e}")
        raise RuntimeError(f"Failed to create PostgreSQL checkpointer: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check for chat service."""
    from datetime import datetime
    
    try:
        # Check if we can create a chat agent
        checkpointer = await get_checkpointer_from_service_manager()
        from agent.chat_agent import create_chat_agent
        chat_agent = await create_chat_agent(checkpointer=checkpointer, include_escalation=True)
        
        return {
            "status": "healthy",
            "agent_ready": True,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "agent_ready": False,
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.post("/stream")
async def stream_chat(chat_request: ChatRequest):
    """Stream chat messages with the assistant."""
    try:
        logger.info(f"Streaming chat for thread_id: {chat_request.thread_id}")
        
        # Get the appropriate checkpointer
        checkpointer = await get_checkpointer_from_service_manager()
        
        # Get chat agent with specific checkpointer (for conversation state)
        # Note: When using custom checkpointer, we don't cache the agent since each conversation
        # needs its own checkpointer instance for proper state management
        logger.info("Getting chat agent with checkpointer...")
        try:
            from agent.chat_agent import create_chat_agent
            chat_agent = await create_chat_agent(checkpointer=checkpointer, include_escalation=True)
            logger.info(f"Chat agent ready. Using checkpointer: {type(checkpointer)} (id: {id(checkpointer)})")
        except Exception as agent_error:
            logger.error(f"Failed to create chat agent: {agent_error}")
            raise HTTPException(status_code=500, detail=f"Failed to create chat agent: {str(agent_error)}")
        
        # Create config
        config = _create_config(chat_request.thread_id)
        
        # Inject memory search tool call on first turn
        memory_tool_messages = []
        is_first_turn = await _is_first_turn(chat_request.thread_id, checkpointer)
        
        if is_first_turn:
            logger.info("First turn in conversation - injecting memory search tool call")
            try:
                from memory.memory_functions import search_memory
                
                # Use the user's message for context search
                user_message = chat_request.messages[0].content
                memory_result = await search_memory(user_message, limit=5)
                
                if memory_result["success"] and memory_result["results"]:
                    memory_facts = [result["fact"] for result in memory_result["results"]]
                    tool_result = f"Found {len(memory_facts)} relevant memories:\n" + "\n".join([f"- {fact}" for fact in memory_facts])
                    
                    logger.info(f"Found {len(memory_facts)} memory facts for tool injection")
                else:
                    tool_result = "No relevant memories found for your query."
                    logger.debug("No memory context found for first turn")
                
                # Create tool call message (AI calling the tool) 
                ai_tool_call = AIMessage(
                    content="Before answering you, let me search my memory for relevant information...",
                    tool_calls=[{
                        "name": "search_memory",
                        "args": {"query": user_message},
                        "id": "memory_search_auto",
                        "type": "tool_call"
                    }]
                )
                
                # Create tool result message
                tool_result_message = ToolMessage(
                    content=tool_result,
                    tool_call_id="memory_search_auto"
                )
                
                # These will be injected after message conversion
                memory_tool_messages = [ai_tool_call, tool_result_message]
                
            except Exception as memory_error:
                logger.warning(f"Failed to search memory for tool injection: {memory_error}")
                memory_tool_messages = []
        else:
            logger.debug("Not first turn - skipping memory search tool injection")
            memory_tool_messages = []
        
        # Convert Pydantic models to LangChain messages
        logger.debug("Converting messages...")
        try:
            messages = _convert_messages_to_langchain(chat_request.messages)
            
            # Inject memory tool messages if this is first turn
            if memory_tool_messages:
                # Add memory tool messages AFTER the user message
                # This ensures they become part of the conversation history
                messages.extend(memory_tool_messages)  # Add memory tool call and result
                
                logger.info(f"Injected {len(memory_tool_messages)} memory tool messages")
                for i, msg in enumerate(memory_tool_messages):
                    logger.info(f"Memory tool message {i}: {type(msg).__name__} - {getattr(msg, 'tool_calls', 'no tool_calls')} - {msg.content[:100] if hasattr(msg, 'content') else 'no content'}")
            
            logger.debug(f"Converted {len(messages)} messages to LangChain format")
            logger.info(f"Final message list has {len(messages)} messages:")
            for i, msg in enumerate(messages):
                logger.info(f"Message {i}: {type(msg).__name__} - {getattr(msg, 'tool_calls', 'no tool_calls')} - {msg.content[:50] if hasattr(msg, 'content') else 'no content'}...")
        except Exception as convert_error:
            logger.error(f"Failed to convert messages: {convert_error}")
            raise HTTPException(status_code=500, detail=f"Failed to convert messages: {str(convert_error)}")
        
        logger.debug(f"Starting stream for thread_id: {chat_request.thread_id} with {len(messages)} messages")
        
        
        async def generate_response():
            """Generate SSE (Server-Sent Events) response stream."""
            # Yield memory tool calls first if they exist (for immediate display)
            if memory_tool_messages and len(memory_tool_messages) >= 2:
                timestamp = datetime.now().isoformat()
                
                # Get the AI message with tool calls (first message)
                ai_msg = memory_tool_messages[0]
                if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                    for tool_call in ai_msg.tool_calls:
                        tool_event = {
                            "type": "tool_call",
                            "data": {
                                "tool": tool_call["name"],
                                "args": tool_call.get("args", {}),
                                "tool_call_id": tool_call.get("id"),
                                "timestamp": timestamp
                            }
                        }
                        yield f"data: {json.dumps(tool_event)}\n\n"
                        logger.info(f"Yielded memory tool call: {tool_call['name']}")
                
                # Get the tool result message (second message)
                tool_result_msg = memory_tool_messages[1]
                if hasattr(tool_result_msg, 'tool_call_id'):
                    tool_result_event = {
                        "type": "tool_result",
                        "data": {
                            "tool": "search_memory",
                            "result": str(tool_result_msg.content),
                            "tool_call_id": tool_result_msg.tool_call_id,
                            "timestamp": timestamp
                        }
                    }
                    yield f"data: {json.dumps(tool_result_event)}\n\n"
                    logger.info("Yielded memory tool result")
            
            # Now process the agent stream
            stream_count = 0
            try:
                async for chunk in chat_agent.astream(
                    {"messages": messages},
                    config=config,
                    stream_mode="updates"
                ):
                    stream_count += 1
                    logger.debug(f"Stream chunk {stream_count}: {chunk}")
                    
                    # Process chunk data
                    for node_name, node_output in chunk.items():
                        if "messages" in node_output:
                            for message in node_output["messages"]:
                                if isinstance(message, AIMessage):
                                    logger.debug(f"Streaming AI message: {message.content[:50]}...")
                                    
                                    # Generate timestamp for this specific message
                                    timestamp = datetime.now().isoformat()
                                    
                                    # Send message content as it streams
                                    # Defensive check: ensure content is a string
                                    content = message.content
                                    if not isinstance(content, str):
                                        logger.warning(f"Non-string content from LLM: {type(content)} - {content}")
                                        if isinstance(content, list):
                                            content = '\n\n'.join(str(item) for item in content)
                                        else:
                                            content = str(content)
                                    
                                    event = {
                                        "type": "message",
                                        "data": {
                                            "role": "assistant",
                                            "content": content,
                                            "timestamp": timestamp,
                                            "node": node_name
                                        }
                                    }
                                    yield f"data: {json.dumps(event)}\n\n"
                                
                                # Handle tool calls
                                if hasattr(message, 'tool_calls') and message.tool_calls:
                                    for tool_call in message.tool_calls:
                                        # Generate timestamp for this specific tool call
                                        timestamp = datetime.now().isoformat()
                                        
                                        tool_event = {
                                            "type": "tool_call",
                                            "data": {
                                                "tool": tool_call["name"],
                                                "args": tool_call.get("args", {}),
                                                "tool_call_id": tool_call.get("id"),
                                                "timestamp": timestamp
                                            }
                                        }
                                        yield f"data: {json.dumps(tool_event)}\n\n"
                                
                                # Handle tool results
                                elif isinstance(message, ToolMessage):
                                    logger.debug(f"Streaming tool result: {message.name}")
                                    
                                    # Generate timestamp for this tool result
                                    timestamp = datetime.now().isoformat()
                                    
                                    tool_result_event = {
                                        "type": "tool_result",
                                        "data": {
                                            "tool": getattr(message, 'name', 'unknown'),
                                            "result": str(message.content),
                                            "tool_call_id": getattr(message, 'tool_call_id', None),
                                            "timestamp": timestamp
                                        }
                                    }
                                    yield f"data: {json.dumps(tool_result_event)}\n\n"
                
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
async def list_chats(limit: int = 5, offset: int = 0):
    """
    List chat conversations with pagination support.
    
    Excludes task chats that have NEEDS_REVIEW status (those appear in "Needs decision" section only).
    
    Args:
        limit: Number of chats to return (default: 5)
        offset: Number of chats to skip (default: 0)
    """
    try:
        # Get checkpointer from app state
        checkpointer = await get_checkpointer_from_service_manager()
        
        thread_ids = await _list_chat_threads()
        chat_summaries = []
        
        for thread_id in thread_ids:
            try:
                messages = await _get_chat_history_with_checkpointer(thread_id, checkpointer)
                
                if not messages:
                    continue
                
                # Check if this is a task chat with NEEDS_REVIEW status
                if thread_id.startswith("core_agent_task_"):
                    task_id = thread_id.replace("core_agent_task_", "")
                    
                    # Check task status
                    from database.database import db_manager
                    from sqlalchemy import select
                    from models.models import Task, TaskStatus
                    
                    try:
                        async with db_manager.get_session() as session:
                            result = await session.execute(
                                select(Task.status).where(Task.id == task_id)
                            )
                            task_status = result.scalar_one_or_none()
                            
                            # Skip task chats with NEEDS_REVIEW status (they belong in "Needs decision" only)
                            if task_status == TaskStatus.NEEDS_REVIEW:
                                continue
                                
                    except Exception as task_error:
                        print(f"Error checking task status for {task_id}: {task_error}")
                        # If we can't check task status, include the chat to be safe
                        pass
                
                # Determine title based on thread type
                title = await _get_chat_title(thread_id, messages)
                
                # Get last message
                last_message = messages[-1] if messages else None
                
                # Get last message content, fallback to tool calls if content is empty
                last_message_text = ""
                if last_message:
                    if last_message.content:
                        last_message_text = last_message.content
                    elif last_message.tool_calls:
                        # Show tool call info when content is empty
                        tool_names = [tc.get('tool', 'unknown') for tc in last_message.tool_calls]
                        last_message_text = f"Used tools: {', '.join(tool_names)}"
                
                # Truncate if too long
                if len(last_message_text) > 100:
                    last_message_text = last_message_text[:100] + "..."
                
                chat_summaries.append(ChatSummary(
                    id=thread_id,
                    title=title,
                    created_at=messages[0].created_at if messages else datetime.now().isoformat(),
                    updated_at=last_message.created_at if last_message else datetime.now().isoformat(),
                    last_message=last_message_text,
                    last_activity=last_message.created_at if last_message else datetime.now().isoformat(),
                    has_decision=any(msg.needs_decision for msg in messages),
                    message_count=len(messages)
                ))
                
            except Exception as msg_error:
                print(f"Error processing chat {thread_id}: {msg_error}")
                continue
        
        # Sort by last activity (most recent first) - already correct ordering
        chat_summaries.sort(key=lambda x: x.updated_at, reverse=True)
        
        # Apply pagination
        paginated_chats = chat_summaries[offset:offset + limit]
        
        return paginated_chats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing chats: {str(e)}")


async def _get_chat_title(thread_id: str, messages: List[ChatMessageDetail]) -> str:
    """
    Generate appropriate title for a chat based on its thread ID and messages.
    
    For task chats (core_agent_task_*), use the actual task title.
    For regular chats, use the first user message.
    """
    # Check if this is a task-related chat
    if thread_id.startswith("core_agent_task_"):
        try:
            # Extract task ID from thread ID
            task_id = thread_id.replace("core_agent_task_", "")
            
            # Fetch task details to get the title
            from database.database import db_manager
            from sqlalchemy import select
            from models.models import Task
            
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(Task.title).where(Task.id == task_id)
                )
                task_title = result.scalar_one_or_none()
                
                if task_title:
                    return f"Task: {task_title}"
                else:
                    # Fallback if task not found
                    return f"Task Chat (ID: {task_id[:8]}...)"
                    
        except Exception as e:
            print(f"Error fetching task title for {thread_id}: {e}")
            # Fallback to task ID
            task_id = thread_id.replace("core_agent_task_", "")
            return f"Task Chat (ID: {task_id[:8]}...)"
    
    # For regular chats, use first user message
    first_user_msg = next((msg for msg in messages if msg.sender == "user"), None)
    if first_user_msg:
        title = first_user_msg.content[:50]
        return title + "..." if len(first_user_msg.content) > 50 else title
    
    return "New Chat"


@router.get("/conversations/{chat_id}", response_model=ChatSummary)
async def get_chat(chat_id: str):
    """
    Get a specific chat conversation summary.
    """
    try:
        checkpointer = await get_checkpointer_from_service_manager()
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
async def get_chat_messages(chat_id: str):
    """
    Get messages for a specific chat conversation.
    """
    try:
        checkpointer = await get_checkpointer_from_service_manager()
        messages = await _get_chat_history_with_checkpointer(chat_id, checkpointer)
        return messages
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chat messages: {str(e)}")


@router.get("/conversations/{chat_id}/task-data", response_model=TaskChatResponse)
async def get_task_chat_data(chat_id: str):
    """
    Get task chat messages with escalation information.
    Specifically for task threads (core_agent_task_*).
    """
    try:
        checkpointer = await get_checkpointer_from_service_manager()
        messages = await _get_chat_history_with_checkpointer(chat_id, checkpointer)
        
        # Check for escalation info if this is a task thread
        pending_escalation = None
        if chat_id.startswith("core_agent_task_"):
            try:
                from agent.chat_agent import create_chat_agent
                from langchain_core.runnables import RunnableConfig
                
                # Get agent with the same checkpointer and check current state for interrupts
                agent = await create_chat_agent(checkpointer=checkpointer, include_escalation=True)
                config = RunnableConfig(configurable={"thread_id": chat_id})
                state = await agent.aget_state(config)
                
                # Helper function to find most recent ask_user tool call
                def find_escalation_tool_call():
                    if not state.values:
                        return None
                    for msg in reversed(state.values.get("messages", [])):
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            escalation_call = next((tc for tc in msg.tool_calls if tc.get("name") == "ask_user"), None)
                            if escalation_call:
                                return escalation_call
                    return None
                
                # Check for human escalation interrupts
                pending_escalation = None
                escalation_data = None
                
                # First check active interrupts (immediate detection)
                if state.interrupts:
                    for interrupt in state.interrupts:
                        if hasattr(interrupt, 'value') and isinstance(interrupt.value, dict):
                            if interrupt.value.get("type") == "human_escalation":
                                escalation_data = interrupt.value
                                break
                
                # If no active interrupts, check if waiting for resume (persistent detection)
                if not escalation_data and state.next and "__interrupt__" in state.next:
                    escalation_call = find_escalation_tool_call()
                    if escalation_call:
                        escalation_data = {
                            "question": escalation_call.get("args", {}).get("question", "No question provided"),
                            "instructions": "Please respond to continue"
                        }
                
                # Build pending escalation response
                if escalation_data:
                    tool_call_id = None
                    if "tool_call_id" not in escalation_data:
                        escalation_call = find_escalation_tool_call()
                        if escalation_call:
                            tool_call_id = escalation_call.get("id")
                    
                    pending_escalation = {
                        "question": escalation_data.get("question", "No question provided"),
                        "instructions": escalation_data.get("instructions", "Please respond to continue"),
                        "tool_call_id": escalation_data.get("tool_call_id", tool_call_id)
                    }
            except Exception as e:
                logger.warning(f"Could not get escalation info for {chat_id}: {e}")
        
        return TaskChatResponse(
            messages=messages,
            pending_escalation=pending_escalation
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting task chat data: {str(e)}")
