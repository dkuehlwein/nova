"""
Nova Chat API Endpoints

FastAPI endpoints for LangGraph agent compatible with agent-chat-ui patterns.
"""

import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage


from models.chat import (
    ChatMessage, ChatRequest, ChatSummary,
    ChatMessageDetail, TaskChatResponse
)
from utils.logging import get_logger, log_timing
from utils.phoenix_integration import is_phoenix_enabled

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
        # Group AI messages by "turn" (between user messages) and merge them
        # A turn consists of: [AIMessage with tool_calls] -> [ToolMessage results] -> [AIMessage with response]
        # We want to merge these into a single message with tool calls shown inline

        # First, group messages by turn (separated by HumanMessage)
        turns = []  # List of turns, each turn is a list of messages
        current_turn = []

        for msg in messages:
            if isinstance(msg, HumanMessage):
                if current_turn:
                    turns.append(current_turn)
                    current_turn = []
                turns.append([msg])  # User message is its own "turn"
            else:
                current_turn.append(msg)

        if current_turn:
            turns.append(current_turn)

        # Now process each turn
        msg_index = 0
        for turn in turns:
            if not turn:
                continue

            first_msg = turn[0]

            if isinstance(first_msg, HumanMessage):
                # User message turn - single message
                message_timestamp = get_message_timestamp(first_msg, checkpoint_timestamp)
                metadata = None
                if hasattr(first_msg, 'additional_kwargs') and first_msg.additional_kwargs.get('metadata'):
                    metadata = first_msg.additional_kwargs['metadata']

                chat_messages.append(ChatMessageDetail(
                    id=f"{thread_id}-msg-{msg_index}",
                    sender="user",
                    content=str(first_msg.content),
                    created_at=message_timestamp,
                    needs_decision=False,
                    metadata=metadata
                ))
                msg_index += 1
            else:
                # AI turn - merge all AI messages in this turn
                # Build content with tool call markers embedded to preserve order
                # Format: content appears inline, tool calls are marked with [[TOOL:index]]
                merged_content_parts = []
                all_tool_calls = []
                first_timestamp = None
                turn_metadata = None

                for msg in turn:
                    if isinstance(msg, AIMessage):
                        message_timestamp = get_message_timestamp(msg, checkpoint_timestamp)
                        if first_timestamp is None:
                            first_timestamp = message_timestamp

                        ai_content = str(msg.content).strip()

                        # Check for metadata
                        if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('metadata'):
                            turn_metadata = msg.additional_kwargs['metadata']
                        elif thread_id.startswith("core_agent_task_") and "**Current Task:**" in ai_content:
                            turn_metadata = {"type": "task_introduction"}

                        # Add content if present (before tool calls from this message)
                        if ai_content and ai_content not in ['', 'null', 'None']:
                            merged_content_parts.append(ai_content)

                        # Add tool call markers after the content from this message
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                tool_name = tool_call.get('name', 'unknown') if isinstance(tool_call, dict) else getattr(tool_call, 'name', 'unknown')
                                tool_args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
                                tool_call_id = tool_call.get('id') if isinstance(tool_call, dict) else getattr(tool_call, 'id', None)

                                tool_call_obj = {
                                    'tool': tool_name,
                                    'args': tool_args,
                                    'timestamp': message_timestamp,
                                    'tool_call_id': tool_call_id
                                }

                                if tool_call_id and tool_call_id in tool_results:
                                    tool_call_obj['result'] = tool_results[tool_call_id]['content']

                                # Add marker in content for tool call position
                                tool_index = len(all_tool_calls)
                                merged_content_parts.append(f"[[TOOL:{tool_index}]]")
                                all_tool_calls.append(tool_call_obj)

                # Create merged message if there's anything to show
                if merged_content_parts or all_tool_calls:
                    merged_content = '\n\n'.join(merged_content_parts)

                    chat_messages.append(ChatMessageDetail(
                        id=f"{thread_id}-msg-{msg_index}",
                        sender="assistant",
                        content=merged_content,
                        created_at=first_timestamp or checkpoint_timestamp,
                        needs_decision=False,
                        metadata=turn_metadata,
                        tool_calls=all_tool_calls if all_tool_calls else None
                    ))
                    msg_index += 1
        
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

        service_manager = get_service_manager()

        # Initialize pg_pool if needed
        if service_manager.pg_pool is None:
            logger.debug("PostgreSQL pool is None, initializing...")
            await service_manager.init_pg_pool()

        if service_manager.pg_pool:
            checkpointer = create_postgres_checkpointer(service_manager.pg_pool)
            return checkpointer
        else:
            # PostgreSQL is mandatory - raise error if not available
            logger.error("PostgreSQL connection pool is required but not available")
            raise RuntimeError("PostgreSQL connection pool is required but not available")

    except Exception as e:
        logger.error(f"Error creating PostgreSQL checkpointer: {e}")
        raise RuntimeError(f"Failed to create PostgreSQL checkpointer: {str(e)}")


@router.get("/health")
async def health_check():
    """Lightweight health check for chat service.

    Only verifies essential components without creating full agent.
    Full agent creation is expensive and should not happen on every health check.
    """
    from datetime import datetime

    try:
        # Just verify the service manager and pg_pool are available
        from start_website import get_service_manager
        service_manager = get_service_manager()

        pg_pool_ready = service_manager.pg_pool is not None

        return {
            "status": "healthy" if pg_pool_ready else "degraded",
            "agent_ready": pg_pool_ready,  # Assume agent can be created if pg_pool is ready
            "pg_pool_available": pg_pool_ready,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "agent_ready": False,
            "pg_pool_available": False,
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.post("/stream")
async def stream_chat(chat_request: ChatRequest):
    """Stream chat messages with the assistant."""
    try:
        request_start = time.time()
        logger.info(f"⏱️ TIMING: Starting stream_chat for thread_id: {chat_request.thread_id}")

        # Get the appropriate checkpointer
        t0 = time.time()
        checkpointer = await get_checkpointer_from_service_manager()
        log_timing("get_checkpointer", t0)

        # Get chat agent with specific checkpointer (for conversation state)
        # Note: When using custom checkpointer, we don't cache the agent since each conversation
        # needs its own checkpointer instance for proper state management
        logger.info("Getting chat agent with checkpointer...")
        try:
            from agent.chat_agent import create_chat_agent
            t0 = time.time()
            chat_agent = await create_chat_agent(checkpointer=checkpointer, include_escalation=True)
            log_timing("create_chat_agent", t0)
            logger.info(f"Chat agent ready. Using checkpointer: {type(checkpointer)} (id: {id(checkpointer)})")
        except Exception as agent_error:
            logger.error(f"Failed to create chat agent: {agent_error}")
            raise HTTPException(status_code=500, detail=f"Failed to create chat agent: {str(agent_error)}")
        
        # Create config
        config = _create_config(chat_request.thread_id)
        
        # Check if there's an active interrupt that needs to be resumed
        resume_from_interrupt = False
        user_response = None
        try:
            t0 = time.time()
            state = await chat_agent.aget_state(config)
            log_timing("check_interrupts", t0)
            logger.info(f"Checking for interrupts in thread {chat_request.thread_id}: state={state}, interrupts={state.interrupts if state else None}")
            if state and state.interrupts:
                logger.info(f"Found active interrupt for thread {chat_request.thread_id}, resuming with user response")
                resume_from_interrupt = True
                user_response = chat_request.messages[-1].content
        except Exception as state_error:
            logger.warning(f"Could not check for interrupts: {state_error}")

        # Inject memory search tool call on first turn (skip if resuming from interrupt)
        memory_tool_messages = []
        t0 = time.time()
        is_first_turn = await _is_first_turn(chat_request.thread_id, checkpointer)
        log_timing("is_first_turn_check", t0)

        if is_first_turn and not resume_from_interrupt:
            logger.info("First turn in conversation - injecting memory search tool call")
            try:
                from memory.memory_functions import search_memory

                # Use the user's message for context search
                user_message = chat_request.messages[0].content
                t0 = time.time()
                memory_result = await search_memory(user_message, limit=5)
                log_timing("memory_search", t0)
                
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
        
        # Convert Pydantic models to LangChain messages (skip if resuming from interrupt)
        messages = []
        if not resume_from_interrupt:
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
        
        log_timing("total_pre_stream_setup", request_start)
        logger.debug(f"Starting stream for thread_id: {chat_request.thread_id}, resume_from_interrupt: {resume_from_interrupt}")

        async def generate_response():
            """Generate SSE (Server-Sent Events) response stream."""
            first_token_time = None
            stream_start = time.time()
            trace_info_sent = False  # Track if we've sent trace info

            # Yield start event
            start_event = {
                "type": "start",
                "data": {
                    "thread_id": chat_request.thread_id,
                    "timestamp": datetime.now().isoformat(),
                }
            }
            yield f"data: {json.dumps(start_event)}\n\n"

            # Yield memory tool calls first if they exist (for immediate display)
            # Skip memory tool injection if resuming from interrupt
            if not resume_from_interrupt and memory_tool_messages and len(memory_tool_messages) >= 2:
                timestamp = datetime.now().isoformat()
                
                # Get the AI message with tool calls (first message)
                ai_msg = memory_tool_messages[0]
                
                # First, yield the AI message content if it exists
                if ai_msg.content and ai_msg.content.strip():
                    message_event = {
                        "type": "message",
                        "data": {
                            "role": "assistant",
                            "content": ai_msg.content,
                            "timestamp": timestamp,
                            "node": "agent"
                        }
                    }
                    yield f"data: {json.dumps(message_event)}\n\n"
                    logger.info(f"Yielded memory AI message content: {ai_msg.content[:50]}...")
                
                # Then yield the tool calls
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
                # Choose input based on whether we're resuming from interrupt
                if resume_from_interrupt:
                    from langgraph.types import Command
                    stream_input = Command(resume=user_response)
                    logger.info(f"Resuming from interrupt with user response: {user_response}")
                else:
                    stream_input = {"messages": messages}
                    logger.info(f"Starting new conversation with {len(messages)} messages")
                
                async for chunk in chat_agent.astream(
                    stream_input,
                    config=config,
                    stream_mode="updates"
                ):
                    stream_count += 1
                    if stream_count == 1:
                        first_token_time = time.time()
                        first_token_ms = (first_token_time - stream_start) * 1000
                        logger.info(f"⏱️ TIMING: first_chunk took {first_token_ms:.2f}ms (time to first LLM response)")
                    logger.debug(f"Stream chunk {stream_count}: {chunk}")
                    
                    # Process chunk data
                    for node_name, node_output in chunk.items():
                        if "messages" in node_output:
                            for message in node_output["messages"]:
                                if isinstance(message, AIMessage):
                                    logger.debug(f"Streaming AI message: {message.content[:50]}...")

                                    # Generate timestamp for this specific message
                                    timestamp = datetime.now().isoformat()

                                    # Extract and send trace info from message metadata (captured in chat_agent.py)
                                    if not trace_info_sent and is_phoenix_enabled():
                                        metadata = getattr(message, 'additional_kwargs', {}).get('metadata', {})
                                        phoenix_url = metadata.get('phoenix_url')
                                        if phoenix_url:
                                            trace_event = {
                                                "type": "trace_info",
                                                "data": {
                                                    "phoenix_url": phoenix_url,
                                                    "trace_id": metadata.get('trace_id'),
                                                }
                                            }
                                            yield f"data: {json.dumps(trace_event)}\n\n"
                                            trace_info_sent = True
                                            logger.debug(f"Sent trace_info event: {phoenix_url}")

                                    # Send message content as it streams
                                    # Defensive check: ensure content is a string
                                    content = message.content
                                    if not isinstance(content, str):
                                        logger.warning(f"Non-string content from LLM: {type(content)} - {content}")
                                        if isinstance(content, list):
                                            content = '\n\n'.join(str(item) for item in content)
                                        else:
                                            content = str(content)

                                    # Skip empty messages and single punctuation to avoid displaying dots
                                    if content and content.strip() and not (content.strip() in ['.', '!', '?', ':', ';', ',']):
                                        event = {
                                            "type": "message",
                                            "data": {
                                                "role": "assistant",
                                                "content": content,
                                                "timestamp": timestamp,
                                                "node": node_name,
                                            }
                                        }
                                        # Include metadata in message event for frontend persistence
                                        msg_metadata = getattr(message, 'additional_kwargs', {}).get('metadata', {})
                                        if msg_metadata:
                                            event["data"]["metadata"] = msg_metadata
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
                
                total_stream_ms = (time.time() - stream_start) * 1000
                logger.info(f"⏱️ TIMING: total_streaming took {total_stream_ms:.2f}ms ({stream_count} chunks)")
                logger.info(f"Finished streaming for thread_id: {chat_request.thread_id} after {stream_count} chunks")
                
                # Verify checkpoints were saved and check for pending interrupts
                try:
                    checkpointer = chat_agent.checkpointer
                    checkpoint_state = await checkpointer.aget(config)
                    if checkpoint_state and 'messages' in checkpoint_state.get('channel_values', {}):
                        messages_count = len(checkpoint_state['channel_values']['messages'])
                        logger.debug(f"Conversation saved: {messages_count} messages in thread {chat_request.thread_id}")
                    else:
                        logger.warning(f"No state found for thread {chat_request.thread_id} after streaming")
                    
                    # Check for pending interrupts using agent state (not checkpointer state)
                    agent_state = await chat_agent.aget_state(config)
                    if agent_state and agent_state.interrupts:
                        logger.info(f"Found {len(agent_state.interrupts)} pending interrupts after streaming - sending complete to trigger frontend polling")
                        for interrupt in agent_state.interrupts:
                            if hasattr(interrupt, 'value') and isinstance(interrupt.value, dict):
                                interrupt_type = interrupt.value.get("type")
                                logger.info(f"Pending interrupt type: {interrupt_type}")
                    
                except Exception as checkpoint_error:
                    logger.error(f"Error verifying checkpoints: {checkpoint_error}")
                
                # Send completion signal (frontend will poll for pending escalations)
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
        from agent.chat_agent import get_all_tools

        tools = await get_all_tools()
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
        
        # Check for escalation info for ALL conversations (universal tool approval support)
        pending_escalation = None
        # Remove the task-only restriction - check all conversations for escalations
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
                        interrupt_type = interrupt.value.get("type")
                        if interrupt_type == "user_question":
                            escalation_data = interrupt.value
                            break
                        elif interrupt_type == "tool_approval_request":
                            escalation_data = interrupt.value
                            escalation_data["type"] = "tool_approval_request"  # Ensure type is preserved
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
                
                # Build escalation based on type
                if escalation_data.get("type") == "tool_approval_request":
                    pending_escalation = {
                        "question": f"Nova wants to use the tool: {escalation_data.get('tool_name', 'unknown')}",
                        "instructions": "Please choose your approval option",
                        "tool_call_id": escalation_data.get("tool_call_id", tool_call_id),
                        "type": "tool_approval_request",
                        "tool_name": escalation_data.get("tool_name"),
                        "tool_args": escalation_data.get("tool_args", {})
                    }
                else:
                    # Regular user question escalation
                    pending_escalation = {
                        "question": escalation_data.get("question", "No question provided"),
                        "instructions": escalation_data.get("instructions", "Please respond to continue"),
                        "tool_call_id": escalation_data.get("tool_call_id", tool_call_id),
                        "type": "user_question"
                    }
        except Exception as e:
            logger.warning(f"Could not get escalation info for {chat_id}: {e}")
        
        return TaskChatResponse(
            messages=messages,
            pending_escalation=pending_escalation
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting task chat data: {str(e)}")


@router.delete("/conversations/{chat_id}")
async def delete_chat(chat_id: str):
    """
    Delete a chat conversation.

    For task-related chats (core_agent_task_*), this will also delete the associated task.
    Returns information about what was deleted to help frontend show appropriate feedback.
    """
    from api.api_endpoints import cleanup_task_chat_data
    from config import settings
    from psycopg_pool import AsyncConnectionPool
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    try:
        is_task_chat = chat_id.startswith("core_agent_task_")
        task_id = chat_id.replace("core_agent_task_", "") if is_task_chat else None

        if is_task_chat and task_id:
            # This is a task chat - delete the task which cascades to chat cleanup
            from database.database import db_manager
            from sqlalchemy import select
            from models.models import Task

            task_found = False
            async with db_manager.get_session() as session:
                result = await session.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()

                if task:
                    task_found = True
                    from sqlalchemy import text

                    # Clean up foreign key references first
                    await session.execute(
                        text("UPDATE processed_items SET task_id = NULL WHERE task_id = :task_id"),
                        {"task_id": task_id}
                    )

                    # Delete the task
                    await session.delete(task)
                    await session.commit()

            # Clean up chat data AFTER transaction completes successfully
            if task_found:
                try:
                    await cleanup_task_chat_data(task_id)
                except Exception as cleanup_error:
                    # Task is already deleted, log but don't fail
                    logger.warning(f"Failed to cleanup chat data for task {task_id}: {cleanup_error}")

                logger.info(f"Deleted task chat {chat_id} and associated task {task_id}")
                return {
                    "success": True,
                    "deleted_chat": chat_id,
                    "deleted_task": task_id,
                    "message": "Deleted chat and associated task"
                }
            else:
                # Task doesn't exist but thread might - fall through to delete just the thread
                logger.info(f"Task {task_id} not found, attempting to delete thread only")

        # Regular chat or task not found - delete just the checkpointer thread
        database_url = settings.DATABASE_URL
        pool = AsyncConnectionPool(database_url, open=False)
        await pool.open()

        try:
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                await checkpointer.adelete_thread(chat_id)
                logger.info(f"Deleted chat thread: {chat_id}")

            return {
                "success": True,
                "deleted_chat": chat_id,
                "deleted_task": None,
                "message": "Deleted chat conversation"
            }

        except Exception as e:
            logger.error(f"Failed to delete chat thread {chat_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete chat: {str(e)}")
        finally:
            await pool.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting chat: {str(e)}")


@router.post("/conversations/{chat_id}/escalation-response")
async def respond_to_escalation(chat_id: str, response: dict):
    """
    Respond to an escalation (user question or tool approval) and resume conversation.
    
    Body format:
    - For user questions: {"response": "user's text response"}
    - For tool approvals: {"type": "approve|always_allow|deny", "response": "optional message"}
    """
    try:
        from agent.chat_agent import create_chat_agent
        from langchain_core.runnables import RunnableConfig
        from langgraph.graph.graph import Command
        
        # Get agent and config
        checkpointer = await get_checkpointer_from_service_manager()
        agent = await create_chat_agent(checkpointer=checkpointer, include_escalation=True)
        config = RunnableConfig(configurable={"thread_id": chat_id})
        
        # Determine response format based on response data
        if "type" in response:
            # Tool approval response
            response_data = {
                "type": response["type"]  # approve, always_allow, or deny
            }
            if "response" in response:
                response_data["message"] = response["response"]
        else:
            # User question response (plain text)
            response_data = response.get("response", "")
        
        logger.info(f"Resuming escalation for {chat_id} with response: {response_data}")
        
        # Resume with the response
        await agent.aupdate_state(config, {"messages": []}, as_node=None)
        result = await agent.ainvoke(Command(resume=response_data), config)
        
        logger.info(f"Escalation response processed for {chat_id}")
        
        return {"success": True, "message": "Escalation response processed"}
        
    except Exception as e:
        logger.error(f"Error responding to escalation for {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error responding to escalation: {str(e)}")
