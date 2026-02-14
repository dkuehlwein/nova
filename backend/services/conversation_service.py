"""
Conversation Service.

Service for conversation/thread management and history retrieval.
Handles chat history reconstruction, thread listing, and conversation CRUD.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Protocol, runtime_checkable, AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from models.chat import ChatMessageDetail, ChatSummary
from utils.logging import get_logger
from utils.langgraph_utils import create_langgraph_config, TASK_THREAD_PREFIX, TOOL_PLACEHOLDER_TEMPLATE

logger = get_logger(__name__)

# Note on imports: Some imports are done inside function bodies to avoid circular
# dependencies. The service layer sits between endpoints and core agent modules,
# so we import database, models, etc. lazily when needed.
# See ADR-018 for the service layer architecture.


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


class ConversationService:
    """Service for conversation management and history retrieval."""

    async def list_threads(self, checkpointer: CheckpointerProtocol) -> List[str]:
        """List all conversation thread IDs from the checkpointer.

        Args:
            checkpointer: The checkpointer instance to query

        Returns:
            List of unique thread IDs from all conversations
        """
        try:
            logger.debug(f"Checkpointer type: {type(checkpointer)}")

            if hasattr(checkpointer, "alist"):
                thread_ids = []
                try:
                    checkpoint_count = 0
                    async for checkpoint_tuple in checkpointer.alist(None):
                        checkpoint_count += 1
                        if checkpoint_tuple.config and checkpoint_tuple.config.get(
                            "configurable", {}
                        ).get("thread_id"):
                            thread_id = checkpoint_tuple.config["configurable"]["thread_id"]
                            if thread_id and thread_id not in thread_ids:
                                thread_ids.append(thread_id)
                                logger.debug(f"Added thread_id: {thread_id}")

                    logger.debug(
                        f"Total checkpoints found: {checkpoint_count}, "
                        f"unique threads: {len(thread_ids)}"
                    )

                except Exception as e:
                    logger.error(f"Error listing threads from checkpointer: {e}")
                return thread_ids
            else:
                logger.error(f"Unsupported checkpointer type: {type(checkpointer)}")
                return []

        except Exception as e:
            logger.error(f"Error listing chat threads: {e}")
            return []

    async def get_history(
        self, thread_id: str, checkpointer: CheckpointerProtocol
    ) -> List[ChatMessageDetail]:
        """Get chat history from a checkpointer, reconstructing message display.

        Args:
            thread_id: Chat thread identifier
            checkpointer: Checkpointer instance to use

        Returns:
            List of chat messages (reconstructed to match streaming experience)
        """
        try:
            config = create_langgraph_config(thread_id)
            state = await checkpointer.aget(config)

            logger.debug(f"Getting chat history for {thread_id}, state type: {type(state)}")

            if not state:
                logger.debug(f"No state found for thread {thread_id}")
                return []

            channel_values = state.get("channel_values", {})
            if "messages" not in channel_values:
                logger.debug(
                    f"No messages in state for thread {thread_id}, "
                    f"available keys: {list(channel_values.keys())}"
                )
                return []

            messages = channel_values["messages"]
            chat_messages = []

            checkpoint_timestamp = state.get("ts", datetime.now().isoformat())
            logger.debug(
                f"Found {len(messages)} raw messages in state, "
                f"checkpoint timestamp: {checkpoint_timestamp}"
            )

            if not messages:
                return []

            # Build message ID to timestamp mapping from checkpoint history
            message_to_timestamp = await self._build_timestamp_mapping(
                config, checkpointer, checkpoint_timestamp
            )

            def get_message_timestamp(msg, fallback: str) -> str:
                if hasattr(msg, "id") and msg.id and msg.id in message_to_timestamp:
                    return message_to_timestamp[msg.id]
                return fallback

            # First pass: collect all tool results by tool_call_id
            tool_results = {}
            for msg in messages:
                if isinstance(msg, ToolMessage):
                    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                        tool_results[msg.tool_call_id] = {
                            "content": str(msg.content),
                            "name": getattr(msg, "name", "unknown"),
                            "tool_call_id": msg.tool_call_id,
                        }

            logger.debug(f"Collected {len(tool_results)} tool results")

            # Fetch approved tool call IDs from metadata
            from services.chat_metadata_service import chat_metadata_service
            approved_tool_call_ids = await chat_metadata_service.get_approved_tool_calls(thread_id)

            # Group messages by turn (separated by HumanMessage)
            turns = []
            current_turn = []

            for msg in messages:
                if isinstance(msg, HumanMessage):
                    if current_turn:
                        turns.append(current_turn)
                        current_turn = []
                    turns.append([msg])
                else:
                    current_turn.append(msg)

            if current_turn:
                turns.append(current_turn)

            # Process each turn
            msg_index = 0
            for turn in turns:
                if not turn:
                    continue

                first_msg = turn[0]

                if isinstance(first_msg, HumanMessage):
                    message_timestamp = get_message_timestamp(first_msg, checkpoint_timestamp)
                    metadata = None
                    if hasattr(first_msg, "additional_kwargs") and first_msg.additional_kwargs.get(
                        "metadata"
                    ):
                        metadata = first_msg.additional_kwargs["metadata"]

                    chat_messages.append(
                        ChatMessageDetail(
                            id=f"{thread_id}-msg-{msg_index}",
                            sender="user",
                            content=str(first_msg.content),
                            created_at=message_timestamp,
                            needs_decision=False,
                            metadata=metadata,
                        )
                    )
                    msg_index += 1
                else:
                    # AI turn - merge all AI messages
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
                            if hasattr(msg, "additional_kwargs") and msg.additional_kwargs.get(
                                "metadata"
                            ):
                                turn_metadata = msg.additional_kwargs["metadata"]
                            elif thread_id.startswith(
                                TASK_THREAD_PREFIX
                            ) and "**Current Task:**" in ai_content:
                                turn_metadata = {"type": "task_introduction"}

                            # Add content if present
                            if ai_content and ai_content not in ["", "null", "None"]:
                                merged_content_parts.append(ai_content)

                            # Add tool call markers after content
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    tool_name = (
                                        tool_call.get("name", "unknown")
                                        if isinstance(tool_call, dict)
                                        else getattr(tool_call, "name", "unknown")
                                    )
                                    tool_args = (
                                        tool_call.get("args", {})
                                        if isinstance(tool_call, dict)
                                        else getattr(tool_call, "args", {})
                                    )
                                    tool_call_id = (
                                        tool_call.get("id")
                                        if isinstance(tool_call, dict)
                                        else getattr(tool_call, "id", None)
                                    )

                                    tool_call_obj = {
                                        "tool": tool_name,
                                        "args": tool_args,
                                        "timestamp": message_timestamp,
                                        "tool_call_id": tool_call_id,
                                    }

                                    if tool_call_id and tool_call_id in tool_results:
                                        tool_call_obj["result"] = tool_results[tool_call_id][
                                            "content"
                                        ]

                                    if tool_call_id and tool_call_id in approved_tool_call_ids:
                                        tool_call_obj["approved"] = True

                                    tool_index = len(all_tool_calls)
                                    merged_content_parts.append(TOOL_PLACEHOLDER_TEMPLATE.format(index=tool_index))
                                    all_tool_calls.append(tool_call_obj)

                    # Create merged message if there's anything to show
                    if merged_content_parts or all_tool_calls:
                        merged_content = "\n\n".join(merged_content_parts)

                        chat_messages.append(
                            ChatMessageDetail(
                                id=f"{thread_id}-msg-{msg_index}",
                                sender="assistant",
                                content=merged_content,
                                created_at=first_timestamp or checkpoint_timestamp,
                                needs_decision=False,
                                metadata=turn_metadata,
                                tool_calls=all_tool_calls if all_tool_calls else None,
                            )
                        )
                        msg_index += 1

            logger.debug(
                f"Returning {len(chat_messages)} chat messages (from {len(messages)} total)"
            )
            return chat_messages

        except Exception as e:
            logger.error(f"Error getting chat history for {thread_id}: {e}")
            return []

    async def _build_timestamp_mapping(
        self, config: Dict[str, Any], checkpointer: CheckpointerProtocol, fallback_timestamp: str
    ) -> Dict[str, str]:
        """Build a mapping of message ID to creation timestamp from checkpoint history."""
        message_to_timestamp = {}

        try:
            history = []
            async for checkpoint_tuple in checkpointer.alist(config):
                history.append(checkpoint_tuple)

            history.sort(key=lambda x: x.checkpoint.get("ts", ""))

            for checkpoint_tuple in history:
                checkpoint = checkpoint_tuple.checkpoint
                metadata = checkpoint_tuple.metadata
                checkpoint_ts = checkpoint.get("ts")

                writes = metadata.get("writes", {})
                if writes:
                    for key, value in writes.items():
                        if isinstance(value, dict) and "messages" in value:
                            for msg in value["messages"]:
                                if hasattr(msg, "id") and msg.id:
                                    if msg.id not in message_to_timestamp:
                                        message_to_timestamp[msg.id] = checkpoint_ts
                                        logger.debug(f"Mapped message {msg.id} -> {checkpoint_ts}")

            logger.debug(f"Successfully mapped {len(message_to_timestamp)} messages to timestamps")

        except Exception as e:
            logger.warning(f"Error building message timestamp mapping: {e}")

        return message_to_timestamp

    async def get_title(
        self, thread_id: str, messages: List[ChatMessageDetail]
    ) -> str:
        """Generate appropriate title for a chat based on thread ID and messages.

        For task chats (core_agent_task_*), use the actual task title.
        For regular chats, use the first user message.
        """
        if thread_id.startswith(TASK_THREAD_PREFIX):
            try:
                task_id = thread_id.replace(TASK_THREAD_PREFIX, "")

                from database.database import db_manager
                from models.models import Task
                from sqlalchemy import select

                async with db_manager.get_session() as session:
                    result = await session.execute(select(Task.title).where(Task.id == task_id))
                    task_title = result.scalar_one_or_none()

                    if task_title:
                        return f"Task: {task_title}"
                    else:
                        return f"Task Chat (ID: {task_id[:8]}...)"

            except Exception as e:
                logger.warning(f"Error fetching task title for {thread_id}: {e}")
                task_id = thread_id.replace(TASK_THREAD_PREFIX, "")
                return f"Task Chat (ID: {task_id[:8]}...)"

        # Check for custom title in metadata
        try:
            from services.chat_metadata_service import chat_metadata_service
            custom_title = await chat_metadata_service.get_title(thread_id)
            if custom_title:
                return custom_title
        except Exception as e:
            logger.warning(f"Error fetching custom title for {thread_id}: {e}")

        # For regular chats, use first user message
        first_user_msg = next((msg for msg in messages if msg.sender == "user"), None)
        if first_user_msg:
            return self._truncate_title(first_user_msg.content)

        return "New Chat"

    @staticmethod
    def _truncate_title(content: str, max_length: int = 70) -> str:
        """Truncate content to max_length chars, adding ellipsis if needed."""
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."

    async def generate_title(
        self, thread_id: str, messages: List[ChatMessageDetail]
    ) -> Optional[str]:
        """Generate and persist a title for a chat conversation.

        Uses the first user message as the title. Returns None for task chats
        or conversations with no user messages.
        """
        if thread_id.startswith(TASK_THREAD_PREFIX):
            return None

        first_user_msg = next((m for m in messages if m.sender == "user"), None)
        if not first_user_msg:
            return None

        title = self._truncate_title(first_user_msg.content)

        from services.chat_metadata_service import chat_metadata_service
        await chat_metadata_service.set_title(thread_id, title)

        return title

    async def get_summary(
        self, thread_id: str, checkpointer: CheckpointerProtocol
    ) -> Optional[ChatSummary]:
        """Build complete conversation summary for a thread.

        Args:
            thread_id: Chat thread identifier
            checkpointer: Checkpointer instance to use

        Returns:
            ChatSummary or None if thread not found
        """
        messages = await self.get_history(thread_id, checkpointer)

        if not messages:
            return None

        # Check if this is a task chat with NEEDS_REVIEW status (should be filtered out)
        if thread_id.startswith(TASK_THREAD_PREFIX):
            task_id = thread_id.replace(TASK_THREAD_PREFIX, "")

            from database.database import db_manager
            from models.models import Task, TaskStatus
            from sqlalchemy import select

            try:
                async with db_manager.get_session() as session:
                    result = await session.execute(
                        select(Task.status).where(Task.id == task_id)
                    )
                    task_status = result.scalar_one_or_none()

                    if task_status == TaskStatus.NEEDS_REVIEW:
                        return None  # Skip - belongs in "Needs decision" only

            except Exception as task_error:
                logger.warning(f"Error checking task status for {task_id}: {task_error}")

        title = await self.get_title(thread_id, messages)
        last_message = messages[-1] if messages else None

        # Get last message content, fallback to tool calls if content is empty
        last_message_text = ""
        if last_message:
            if last_message.content:
                last_message_text = last_message.content
            elif last_message.tool_calls:
                tool_names = [tc.get("tool", "unknown") for tc in last_message.tool_calls]
                last_message_text = f"Used tools: {', '.join(tool_names)}"

        # Truncate if too long
        if len(last_message_text) > 100:
            last_message_text = last_message_text[:100] + "..."

        return ChatSummary(
            id=thread_id,
            title=title,
            created_at=messages[0].created_at if messages else datetime.now().isoformat(),
            updated_at=last_message.created_at if last_message else datetime.now().isoformat(),
            last_message=last_message_text,
            last_activity=last_message.created_at if last_message else datetime.now().isoformat(),
            has_decision=any(msg.needs_decision for msg in messages),
            message_count=len(messages),
        )

    async def delete(self, thread_id: str) -> Dict[str, Any]:
        """Delete a conversation and cleanup associated data.

        For task-related chats (core_agent_task_*), also deletes the associated task.

        Args:
            thread_id: Chat thread identifier

        Returns:
            Dict with deletion results
        """
        is_task_chat = thread_id.startswith(TASK_THREAD_PREFIX)
        task_id = thread_id.replace(TASK_THREAD_PREFIX, "") if is_task_chat else None

        if is_task_chat and task_id:
            from database.database import db_manager
            from models.models import Task
            from sqlalchemy import select, text

            task_found = False
            async with db_manager.get_session() as session:
                result = await session.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()

                if task:
                    task_found = True

                    # Clean up foreign key references first
                    await session.execute(
                        text("UPDATE processed_items SET task_id = NULL WHERE task_id = :task_id"),
                        {"task_id": task_id},
                    )

                    # Delete the task
                    await session.delete(task)
                    await session.commit()

            # Clean up chat data AFTER transaction completes
            if task_found:
                try:
                    await cleanup_task_chat_data(task_id)
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to cleanup chat data for task {task_id}: {cleanup_error}"
                    )

                logger.info(f"Deleted task chat {thread_id} and associated task {task_id}")
                return {
                    "success": True,
                    "deleted_chat": thread_id,
                    "deleted_task": task_id,
                    "message": "Deleted chat and associated task",
                }
            else:
                logger.info(f"Task {task_id} not found, attempting to delete thread only")

        # Regular chat or task not found - delete just the checkpointer thread
        # Use the ServiceManager's pool for consistency (avoid creating new pools)
        from utils.checkpointer_utils import get_checkpointer_from_service_manager

        try:
            checkpointer = await get_checkpointer_from_service_manager()
            await checkpointer.adelete_thread(thread_id)
            logger.info(f"Deleted chat thread: {thread_id}")

            return {
                "success": True,
                "deleted_chat": thread_id,
                "deleted_task": None,
                "message": "Deleted chat conversation",
            }

        except Exception as e:
            logger.error(f"Failed to delete chat thread {thread_id}: {e}")
            raise


async def cleanup_task_chat_data(task_id: str) -> None:
    """Clean up LangGraph checkpointer data associated with a task.

    This function is called when a task is deleted to clean up the associated
    chat thread in LangGraph's checkpoint storage.

    Uses the ServiceManager's connection pool for consistency.

    Args:
        task_id: The task ID whose chat data should be cleaned up
    """
    from utils.langgraph_utils import create_task_thread_id
    from utils.checkpointer_utils import get_checkpointer_from_service_manager

    try:
        thread_id = create_task_thread_id(task_id)
        checkpointer = await get_checkpointer_from_service_manager()
        await checkpointer.adelete_thread(thread_id)
        logger.info(f"Deleted LangGraph thread: {thread_id}")

    except Exception as e:
        logger.warning(f"Failed to delete LangGraph thread for task {task_id}: {e}")


# Global service instance
conversation_service = ConversationService()
