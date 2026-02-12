"""
Nova Chat API Endpoints

FastAPI endpoints for LangGraph agent compatible with agent-chat-ui patterns.
Thin HTTP handlers that delegate to services for business logic.
"""

import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from models.chat import (
    ChatMessageDetail,
    ChatRequest,
    ChatSummary,
    ChatTitleUpdateRequest,
    TaskChatResponse,
)
from services.chat_service import chat_service
from services.conversation_service import conversation_service
from utils.checkpointer_utils import get_checkpointer_from_service_manager
from utils.logging import get_logger

logger = get_logger(__name__)


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def stream_chat(chat_request: ChatRequest):
    """Stream chat messages with the assistant."""
    try:
        logger.info(f"Starting stream_chat for thread_id: {chat_request.thread_id}")

        checkpointer = await get_checkpointer_from_service_manager()

        # Get chat agent with specific checkpointer
        logger.info("Getting chat agent with checkpointer...")
        try:
            from agent.chat_agent import create_chat_agent

            chat_agent = await create_chat_agent(
                checkpointer=checkpointer, include_escalation=True
            )
            logger.info(f"Chat agent ready. Using checkpointer: {type(checkpointer)}")
        except Exception as agent_error:
            logger.error(f"Failed to create chat agent: {agent_error}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create chat agent: {str(agent_error)}"
            )

        async def generate_response():
            """Generate SSE (Server-Sent Events) response stream."""
            async for event in chat_service.stream_chat(
                chat_request, checkpointer, chat_agent
            ):
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat streaming error: {str(e)}")


@router.get("/tools")
async def get_available_tools():
    """Get list of available tools that the agent can use."""
    try:
        from agent.chat_agent import get_all_tools

        tools = await get_all_tools()
        tools_info = []

        for tool in tools:
            tools_info.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "args_schema": tool.args_schema.model_json_schema()
                    if hasattr(tool, "args_schema") and tool.args_schema
                    else {},
                }
            )

        return {
            "tools": tools_info,
            "count": len(tools_info),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tools error: {str(e)}")


# Chat Management Endpoints


@router.get("/conversations", response_model=List[ChatSummary])
async def list_chats(limit: int = 5, offset: int = 0):
    """List chat conversations with pagination support.

    Excludes task chats that have NEEDS_REVIEW status (those appear in "Needs decision" section only).

    Args:
        limit: Number of chats to return (default: 5)
        offset: Number of chats to skip (default: 0)
    """
    try:
        checkpointer = await get_checkpointer_from_service_manager()
        thread_ids = await conversation_service.list_threads(checkpointer)
        chat_summaries = []

        for thread_id in thread_ids:
            try:
                summary = await conversation_service.get_summary(thread_id, checkpointer)
                if summary:
                    chat_summaries.append(summary)
            except Exception as msg_error:
                logger.warning(f"Error processing chat {thread_id}: {msg_error}")
                continue

        # Sort by last activity (most recent first)
        chat_summaries.sort(key=lambda x: x.updated_at, reverse=True)

        # Apply pagination
        return chat_summaries[offset : offset + limit]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing chats: {str(e)}")


@router.get("/conversations/{chat_id}", response_model=ChatSummary)
async def get_chat(chat_id: str):
    """Get a specific chat conversation summary."""
    try:
        checkpointer = await get_checkpointer_from_service_manager()
        summary = await conversation_service.get_summary(chat_id, checkpointer)

        if not summary:
            raise HTTPException(status_code=404, detail="Chat not found")

        return summary

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chat: {str(e)}")


@router.get("/conversations/{chat_id}/messages", response_model=List[ChatMessageDetail])
async def get_chat_messages(chat_id: str):
    """Get messages for a specific chat conversation."""
    try:
        checkpointer = await get_checkpointer_from_service_manager()
        messages = await conversation_service.get_history(chat_id, checkpointer)
        return messages

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chat messages: {str(e)}")


@router.get("/conversations/{chat_id}/task-data", response_model=TaskChatResponse)
async def get_task_chat_data(chat_id: str):
    """Get task chat messages with escalation information.

    Works for all conversation types with universal tool approval support.
    """
    try:
        checkpointer = await get_checkpointer_from_service_manager()
        messages = await conversation_service.get_history(chat_id, checkpointer)

        # Check for escalation info
        pending_escalation = None
        try:
            from agent.chat_agent import create_chat_agent

            agent = await create_chat_agent(checkpointer=checkpointer, include_escalation=True)
            pending_escalation = await chat_service.check_interrupts(chat_id, agent)
        except Exception as e:
            logger.warning(f"Could not get escalation info for {chat_id}: {e}")

        return TaskChatResponse(messages=messages, pending_escalation=pending_escalation)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting task chat data: {str(e)}"
        )


@router.delete("/conversations/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a chat conversation.

    For task-related chats (core_agent_task_*), this will also delete the associated task.
    Returns information about what was deleted to help frontend show appropriate feedback.
    """
    try:
        result = await conversation_service.delete(chat_id)
        return result

    except Exception as e:
        logger.error(f"Error deleting chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting chat: {str(e)}")


@router.post("/conversations/{chat_id}/escalation-response")
async def respond_to_escalation(chat_id: str, response: dict):
    """Respond to an escalation (user question or tool approval) and resume conversation.

    Body format:
    - For user questions: {"response": "user's text response"}
    - For tool approvals: {"type": "approve|always_allow|deny", "response": "optional message"}
    """
    try:
        checkpointer = await get_checkpointer_from_service_manager()

        from agent.chat_agent import create_chat_agent

        agent = await create_chat_agent(checkpointer=checkpointer, include_escalation=True)

        result = await chat_service.resume_interrupt(chat_id, response, agent)
        return result

    except Exception as e:
        logger.error(f"Error responding to escalation for {chat_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error responding to escalation: {str(e)}"
        )


@router.post("/conversations/{chat_id}/generate-title")
async def generate_chat_title(chat_id: str):
    """Generate an LLM-based title for a chat conversation.

    Called after the first assistant response in a new chat.
    """
    try:
        checkpointer = await get_checkpointer_from_service_manager()
        messages = await conversation_service.get_history(chat_id, checkpointer)

        if not messages:
            raise HTTPException(status_code=404, detail="Chat not found")

        generated_title = await conversation_service.generate_title(chat_id, messages)

        if generated_title:
            return {"title": generated_title, "generated": True}

        # Fallback to current behavior
        fallback_title = await conversation_service.get_title(chat_id, messages)
        return {"title": fallback_title, "generated": False}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating title for {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/conversations/{chat_id}/title")
async def update_chat_title(chat_id: str, body: ChatTitleUpdateRequest):
    """Update the title of a chat conversation manually."""
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title cannot be blank")

    try:
        from services.chat_metadata_service import chat_metadata_service
        await chat_metadata_service.set_title(chat_id, title)
        return {"title": title}

    except Exception as e:
        logger.error(f"Error updating title for {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
