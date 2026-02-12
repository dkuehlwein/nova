"""Service for managing chat conversation metadata (titles, tool approvals)."""

from typing import Optional

from sqlalchemy import select

from database.database import db_manager
from models.models import ChatMetadata
from utils.logging import get_logger

logger = get_logger(__name__)


class ChatMetadataService:
    """Manages persistent metadata for chat conversations."""

    async def get_metadata(self, thread_id: str) -> Optional[ChatMetadata]:
        """Get metadata for a thread, or None if not found."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(ChatMetadata).where(ChatMetadata.thread_id == thread_id)
            )
            return result.scalar_one_or_none()

    async def get_title(self, thread_id: str) -> Optional[str]:
        """Get custom title for a thread, or None if not set."""
        metadata = await self.get_metadata(thread_id)
        return metadata.custom_title if metadata else None

    async def set_title(self, thread_id: str, title: str) -> None:
        """Set or update custom title for a thread."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(ChatMetadata).where(ChatMetadata.thread_id == thread_id)
            )
            metadata = result.scalar_one_or_none()

            if metadata:
                metadata.custom_title = title
            else:
                metadata = ChatMetadata(
                    thread_id=thread_id,
                    custom_title=title,
                    approved_tool_calls=[],
                )
                session.add(metadata)

    async def record_approval(self, thread_id: str, tool_call_id: str) -> None:
        """Record that a tool call was manually approved."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(ChatMetadata).where(ChatMetadata.thread_id == thread_id)
            )
            metadata = result.scalar_one_or_none()

            if metadata:
                if tool_call_id not in (metadata.approved_tool_calls or []):
                    approved = list(metadata.approved_tool_calls or [])
                    approved.append(tool_call_id)
                    metadata.approved_tool_calls = approved
            else:
                metadata = ChatMetadata(
                    thread_id=thread_id,
                    approved_tool_calls=[tool_call_id],
                )
                session.add(metadata)

    async def get_approved_tool_calls(self, thread_id: str) -> set[str]:
        """Get set of approved tool call IDs for a thread."""
        metadata = await self.get_metadata(thread_id)
        return set(metadata.approved_tool_calls or []) if metadata else set()


chat_metadata_service = ChatMetadataService()
