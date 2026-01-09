"""
Chat Service.

Service for chat streaming, LangGraph interaction, and message handling.
Handles chat streaming orchestration, message conversion, and memory injection.
"""

import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from models.chat import ChatMessage, ChatRequest
from utils.logging import get_logger, log_timing
from utils.phoenix_integration import is_phoenix_enabled
from utils.langgraph_utils import create_langgraph_config

logger = get_logger(__name__)

# Note on imports: Some imports are done inside function bodies to avoid circular
# dependencies. The service layer sits between endpoints and core agent modules,
# so we import memory_functions, langgraph types, etc. lazily when needed.
# See ADR-018 for the service layer architecture.

# Type alias for checkpointer - avoid importing at module level to prevent circular imports.
# The actual type is langgraph.checkpoint.postgres.aio.AsyncPostgresSaver.
# We use a Protocol to define the interface we need.
from typing import Protocol, runtime_checkable, AsyncIterator


@runtime_checkable
class CheckpointerProtocol(Protocol):
    """Protocol defining the checkpointer interface used by services.

    This avoids importing AsyncPostgresSaver directly, which can cause
    circular import issues. The actual implementation is AsyncPostgresSaver
    from langgraph.checkpoint.postgres.aio.
    """

    async def aget(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get checkpoint state for a config."""
        ...

    def alist(self, config: Optional[Dict[str, Any]]) -> AsyncIterator:
        """List checkpoints matching config."""
        ...


class ChatService:
    """Service for chat streaming and LangGraph interactions."""

    def convert_messages_to_langchain(self, messages: List[ChatMessage]) -> List:
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

    async def is_first_turn(
        self, thread_id: str, checkpointer: CheckpointerProtocol
    ) -> bool:
        """Check if this is the first turn in a conversation.

        Args:
            thread_id: The conversation thread ID
            checkpointer: The checkpointer instance to query

        Returns:
            True if this is the first turn (no previous messages), False otherwise
        """
        config = create_langgraph_config(thread_id)
        try:
            state = await checkpointer.aget(config)
            if not state:
                return True  # No checkpoint yet - first turn

            messages = state.get("channel_values", {}).get("messages", [])
            return len(messages) == 0  # Checkpoint exists but no messages yet

        except Exception as e:
            logger.warning(f"Could not inspect checkpoints for {thread_id}: {e}")
            return False  # Be safe - treat as not-first to avoid memory search on errors

    async def inject_memory_context(self, user_message: str) -> List:
        """Search memory and create tool injection messages for first turn.

        Args:
            user_message: The user's message to search memory for

        Returns:
            List of LangChain messages (AI tool call + tool result) or empty list
        """
        try:
            from memory.memory_functions import search_memory

            t0 = time.time()
            memory_result = await search_memory(user_message, limit=5)
            log_timing("memory_search", t0)

            if memory_result["success"] and memory_result["results"]:
                memory_facts = [result["fact"] for result in memory_result["results"]]
                tool_result = (
                    f"Found {len(memory_facts)} relevant memories:\n"
                    + "\n".join([f"- {fact}" for fact in memory_facts])
                )
                logger.info(f"Found {len(memory_facts)} memory facts for tool injection")
            else:
                tool_result = "No relevant memories found for your query."
                logger.debug("No memory context found for first turn")

            # Create tool call message (AI calling the tool)
            ai_tool_call = AIMessage(
                content="Before answering you, let me search my memory for relevant information...",
                tool_calls=[
                    {
                        "name": "search_memory",
                        "args": {"query": user_message},
                        "id": "memory_search_auto",
                        "type": "tool_call",
                    }
                ],
            )

            # Create tool result message
            tool_result_message = ToolMessage(
                content=tool_result, tool_call_id="memory_search_auto"
            )

            return [ai_tool_call, tool_result_message]

        except Exception as memory_error:
            logger.warning(f"Failed to search memory for tool injection: {memory_error}")
            return []

    async def stream_chat(
        self,
        chat_request: ChatRequest,
        checkpointer: CheckpointerProtocol,
        chat_agent: Any,  # CompiledStateGraph - imported lazily to avoid circular deps
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Core streaming logic - yields SSE events.

        Args:
            chat_request: The chat request with messages and thread_id
            checkpointer: The checkpointer for conversation state
            chat_agent: The LangGraph chat agent

        Yields:
            Dict events for SSE streaming (start, message, tool_call, tool_result, complete, error)
        """
        request_start = time.time()
        config = create_langgraph_config(chat_request.thread_id)

        # Check if there's an active interrupt that needs to be resumed
        resume_from_interrupt = False
        user_response = None
        try:
            t0 = time.time()
            state = await chat_agent.aget_state(config)
            log_timing("check_interrupts", t0)
            logger.info(
                f"Checking for interrupts in thread {chat_request.thread_id}: "
                f"state={state}, interrupts={state.interrupts if state else None}"
            )
            if state and state.interrupts:
                logger.info(
                    f"Found active interrupt for thread {chat_request.thread_id}, "
                    "resuming with user response"
                )
                resume_from_interrupt = True
                user_response = chat_request.messages[-1].content
        except Exception as state_error:
            logger.warning(f"Could not check for interrupts: {state_error}")

        # Inject memory search tool call on first turn (skip if resuming from interrupt)
        memory_tool_messages = []
        t0 = time.time()
        is_first = await self.is_first_turn(chat_request.thread_id, checkpointer)
        log_timing("is_first_turn_check", t0)

        if is_first and not resume_from_interrupt:
            logger.info("First turn in conversation - injecting memory search tool call")
            memory_tool_messages = await self.inject_memory_context(
                chat_request.messages[0].content
            )
        else:
            logger.debug("Not first turn - skipping memory search tool injection")

        # Convert Pydantic models to LangChain messages (skip if resuming from interrupt)
        messages = []
        if not resume_from_interrupt:
            logger.debug("Converting messages...")
            messages = self.convert_messages_to_langchain(chat_request.messages)

            # Inject memory tool messages if this is first turn
            if memory_tool_messages:
                messages.extend(memory_tool_messages)
                logger.info(f"Injected {len(memory_tool_messages)} memory tool messages")

            logger.debug(f"Converted {len(messages)} messages to LangChain format")

        log_timing("total_pre_stream_setup", request_start)
        logger.debug(
            f"Starting stream for thread_id: {chat_request.thread_id}, "
            f"resume_from_interrupt: {resume_from_interrupt}"
        )

        # Yield start event
        yield {
            "type": "start",
            "data": {
                "thread_id": chat_request.thread_id,
                "timestamp": datetime.now().isoformat(),
            },
        }

        # Yield memory tool calls first if they exist (for immediate display)
        if not resume_from_interrupt and memory_tool_messages and len(memory_tool_messages) >= 2:
            timestamp = datetime.now().isoformat()
            ai_msg = memory_tool_messages[0]

            # First, yield the AI message content if it exists
            if ai_msg.content and ai_msg.content.strip():
                yield {
                    "type": "message",
                    "data": {
                        "role": "assistant",
                        "content": ai_msg.content,
                        "timestamp": timestamp,
                        "node": "agent",
                    },
                }
                logger.info(f"Yielded memory AI message content: {ai_msg.content[:50]}...")

            # Then yield the tool calls
            if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
                for tool_call in ai_msg.tool_calls:
                    yield {
                        "type": "tool_call",
                        "data": {
                            "tool": tool_call["name"],
                            "args": tool_call.get("args", {}),
                            "tool_call_id": tool_call.get("id"),
                            "timestamp": timestamp,
                        },
                    }
                    logger.info(f"Yielded memory tool call: {tool_call['name']}")

            # Get the tool result message (second message)
            tool_result_msg = memory_tool_messages[1]
            if hasattr(tool_result_msg, "tool_call_id"):
                yield {
                    "type": "tool_result",
                    "data": {
                        "tool": "search_memory",
                        "result": str(tool_result_msg.content),
                        "tool_call_id": tool_result_msg.tool_call_id,
                        "timestamp": timestamp,
                    },
                }
                logger.info("Yielded memory tool result")

        # Now process the agent stream
        first_token_time = None
        stream_start = time.time()
        stream_count = 0
        trace_info_sent = False

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
                stream_input, config=config, stream_mode="updates"
            ):
                stream_count += 1
                if stream_count == 1:
                    first_token_time = time.time()
                    first_token_ms = (first_token_time - stream_start) * 1000
                    logger.info(
                        f"⏱️ TIMING: first_chunk took {first_token_ms:.2f}ms "
                        "(time to first LLM response)"
                    )
                logger.debug(f"Stream chunk {stream_count}: {chunk}")

                # Process chunk data
                for node_name, node_output in chunk.items():
                    if "messages" in node_output:
                        for message in node_output["messages"]:
                            if isinstance(message, AIMessage):
                                logger.debug(f"Streaming AI message: {message.content[:50]}...")
                                timestamp = datetime.now().isoformat()

                                # Extract and send trace info from message metadata
                                if not trace_info_sent and is_phoenix_enabled():
                                    metadata = getattr(message, "additional_kwargs", {}).get(
                                        "metadata", {}
                                    )
                                    phoenix_url = metadata.get("phoenix_url")
                                    if phoenix_url:
                                        yield {
                                            "type": "trace_info",
                                            "data": {
                                                "phoenix_url": phoenix_url,
                                                "trace_id": metadata.get("trace_id"),
                                            },
                                        }
                                        trace_info_sent = True
                                        logger.debug(f"Sent trace_info event: {phoenix_url}")

                                # Send message content as it streams
                                content = message.content
                                if not isinstance(content, str):
                                    logger.warning(
                                        f"Non-string content from LLM: {type(content)} - {content}"
                                    )
                                    if isinstance(content, list):
                                        content = "\n\n".join(str(item) for item in content)
                                    else:
                                        content = str(content)

                                # Skip empty messages and single punctuation
                                if (
                                    content
                                    and content.strip()
                                    and content.strip() not in [".", "!", "?", ":", ";", ","]
                                ):
                                    event = {
                                        "type": "message",
                                        "data": {
                                            "role": "assistant",
                                            "content": content,
                                            "timestamp": timestamp,
                                            "node": node_name,
                                        },
                                    }
                                    # Include metadata in message event for frontend persistence
                                    msg_metadata = getattr(message, "additional_kwargs", {}).get(
                                        "metadata", {}
                                    )
                                    if msg_metadata:
                                        event["data"]["metadata"] = msg_metadata
                                    yield event

                                # Handle tool calls
                                if hasattr(message, "tool_calls") and message.tool_calls:
                                    for tool_call in message.tool_calls:
                                        timestamp = datetime.now().isoformat()
                                        yield {
                                            "type": "tool_call",
                                            "data": {
                                                "tool": tool_call["name"],
                                                "args": tool_call.get("args", {}),
                                                "tool_call_id": tool_call.get("id"),
                                                "timestamp": timestamp,
                                            },
                                        }

                            # Handle tool results
                            elif isinstance(message, ToolMessage):
                                logger.debug(f"Streaming tool result: {message.name}")
                                timestamp = datetime.now().isoformat()
                                yield {
                                    "type": "tool_result",
                                    "data": {
                                        "tool": getattr(message, "name", "unknown"),
                                        "result": str(message.content),
                                        "tool_call_id": getattr(message, "tool_call_id", None),
                                        "timestamp": timestamp,
                                    },
                                }

            total_stream_ms = (time.time() - stream_start) * 1000
            logger.info(
                f"⏱️ TIMING: total_streaming took {total_stream_ms:.2f}ms ({stream_count} chunks)"
            )
            logger.info(
                f"Finished streaming for thread_id: {chat_request.thread_id} "
                f"after {stream_count} chunks"
            )

            # Verify checkpoints were saved and check for pending interrupts
            try:
                checkpoint_state = await checkpointer.aget(config)
                if checkpoint_state and "messages" in checkpoint_state.get("channel_values", {}):
                    messages_count = len(checkpoint_state["channel_values"]["messages"])
                    logger.debug(
                        f"Conversation saved: {messages_count} messages in thread "
                        f"{chat_request.thread_id}"
                    )
                else:
                    logger.warning(
                        f"No state found for thread {chat_request.thread_id} after streaming"
                    )

                # Check for pending interrupts using agent state
                agent_state = await chat_agent.aget_state(config)
                if agent_state and agent_state.interrupts:
                    logger.info(
                        f"Found {len(agent_state.interrupts)} pending interrupts after streaming"
                    )

            except Exception as checkpoint_error:
                logger.error(f"Error verifying checkpoints: {checkpoint_error}")

            # Send completion signal
            yield {"type": "complete", "data": {"timestamp": datetime.now().isoformat()}}

        except Exception as e:
            logger.error(f"Error during streaming: {e}")
            yield {
                "type": "error",
                "data": {"error": str(e), "timestamp": datetime.now().isoformat()},
            }

    async def check_interrupts(
        self,
        thread_id: str,
        chat_agent: Any,  # CompiledStateGraph
    ) -> Optional[Dict[str, Any]]:
        """Check for pending escalations/tool approvals in a conversation.

        Args:
            thread_id: The conversation thread ID
            chat_agent: The LangGraph chat agent

        Returns:
            Dict with escalation info if pending, None otherwise
        """
        from langchain_core.runnables import RunnableConfig

        config = RunnableConfig(configurable={"thread_id": thread_id})

        try:
            state = await chat_agent.aget_state(config)

            # Helper function to find most recent ask_user tool call
            def find_escalation_tool_call():
                if not state.values:
                    return None
                for msg in reversed(state.values.get("messages", [])):
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        escalation_call = next(
                            (tc for tc in msg.tool_calls if tc.get("name") == "ask_user"),
                            None,
                        )
                        if escalation_call:
                            return escalation_call
                return None

            escalation_data = None

            # First check active interrupts (immediate detection)
            if state.interrupts:
                for interrupt in state.interrupts:
                    if hasattr(interrupt, "value") and isinstance(interrupt.value, dict):
                        interrupt_type = interrupt.value.get("type")
                        if interrupt_type == "user_question":
                            escalation_data = interrupt.value
                            break
                        elif interrupt_type == "tool_approval_request":
                            escalation_data = interrupt.value
                            escalation_data["type"] = "tool_approval_request"
                            break

            # If no active interrupts, check if waiting for resume
            if not escalation_data and state.next and "__interrupt__" in state.next:
                escalation_call = find_escalation_tool_call()
                if escalation_call:
                    escalation_data = {
                        "question": escalation_call.get("args", {}).get(
                            "question", "No question provided"
                        ),
                        "instructions": "Please respond to continue",
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
                    return {
                        "question": f"Nova wants to use the tool: {escalation_data.get('tool_name', 'unknown')}",
                        "instructions": "Please choose your approval option",
                        "tool_call_id": escalation_data.get("tool_call_id", tool_call_id),
                        "type": "tool_approval_request",
                        "tool_name": escalation_data.get("tool_name"),
                        "tool_args": escalation_data.get("tool_args", {}),
                    }
                else:
                    # Regular user question escalation
                    return {
                        "question": escalation_data.get("question", "No question provided"),
                        "instructions": escalation_data.get(
                            "instructions", "Please respond to continue"
                        ),
                        "tool_call_id": escalation_data.get("tool_call_id", tool_call_id),
                        "type": "user_question",
                    }

            return None

        except Exception as e:
            logger.warning(f"Could not get escalation info for {thread_id}: {e}")
            return None

    async def resume_interrupt(
        self,
        thread_id: str,
        response: Dict[str, Any],
        chat_agent: Any,  # CompiledStateGraph
    ) -> Dict[str, Any]:
        """Resume from an interrupt with user response.

        Args:
            thread_id: The conversation thread ID
            response: The user's response dict
            chat_agent: The LangGraph chat agent

        Returns:
            Dict with success status
        """
        from langchain_core.runnables import RunnableConfig
        from langgraph.graph.graph import Command

        config = RunnableConfig(configurable={"thread_id": thread_id})

        # Determine response format based on response data
        if "type" in response:
            # Tool approval response
            response_data = {"type": response["type"]}  # approve, always_allow, or deny
            if "response" in response:
                response_data["message"] = response["response"]
        else:
            # User question response (plain text)
            response_data = response.get("response", "")

        logger.info(f"Resuming escalation for {thread_id} with response: {response_data}")

        # Resume with the response
        await chat_agent.aupdate_state(config, {"messages": []}, as_node=None)
        await chat_agent.ainvoke(Command(resume=response_data), config)

        logger.info(f"Escalation response processed for {thread_id}")

        return {"success": True, "message": "Escalation response processed"}


# Global service instance
chat_service = ChatService()
