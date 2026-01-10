"""
Email thread consolidation for Nova.

Handles grouping emails by thread, managing stabilization windows,
and creating/superseding tasks based on thread state.

See ADR-019 for design details.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from database.database import db_manager
from models.models import Task, TaskStatus, ProcessedItem
from tools.task_tools import create_task_tool, update_task_tool
from utils.logging import get_logger

logger = get_logger(__name__)


class EmailThreadConsolidator:
    """
    Manages thread-based email consolidation.

    Key responsibilities:
    - Find existing tasks for email threads
    - Manage stabilization windows (delay processing until thread settles)
    - Supersede unprocessed tasks when new emails arrive
    - Create continuation tasks with LLM summaries for completed threads
    """

    def __init__(self, stabilization_minutes: int = 15):
        """
        Initialize the thread consolidator.

        Args:
            stabilization_minutes: Minutes to wait after last email before processing
        """
        self.stabilization_minutes = stabilization_minutes

    async def find_existing_thread_task(self, thread_id: str) -> Optional[Task]:
        """
        Find an existing task for this email thread.

        Looks for tasks with matching email_thread_id in metadata,
        excluding tasks that have been superseded.

        Args:
            thread_id: The email thread ID

        Returns:
            The existing Task if found, None otherwise
        """
        if not thread_id:
            return None

        async with db_manager.get_session() as session:
            # Find tasks with this thread_id that haven't been superseded
            result = await session.execute(
                select(Task)
                .options(selectinload(Task.comments))
                .where(
                    and_(
                        Task.task_metadata['email_thread_id'].astext == thread_id,
                        # Not superseded (superseded_by_task_id is null or not set)
                        or_(
                            Task.task_metadata['superseded_by_task_id'].astext.is_(None),
                            ~Task.task_metadata.has_key('superseded_by_task_id')
                        )
                    )
                )
                .order_by(Task.created_at.desc())
                .limit(1)
            )
            task = result.scalar_one_or_none()

            if task:
                logger.debug(
                    "Found existing thread task",
                    extra={"data": {"thread_id": thread_id, "task_id": str(task.id), "status": task.status.value}}
                )

            return task

    async def should_process_thread(self, task: Task) -> bool:
        """
        Check if a thread task's stabilization window has expired.

        Args:
            task: Task with thread consolidation metadata

        Returns:
            True if stabilization window has passed and task should be processed
        """
        metadata = task.task_metadata or {}

        # If not stabilizing, it's ready to process
        if not metadata.get('is_thread_stabilizing'):
            return True

        # Check if stabilization window has passed
        stabilization_ends_str = metadata.get('thread_stabilization_ends_at')
        if not stabilization_ends_str:
            return True

        try:
            stabilization_ends = datetime.fromisoformat(stabilization_ends_str.replace('Z', '+00:00'))
            # Convert to naive UTC for comparison
            if stabilization_ends.tzinfo:
                stabilization_ends = stabilization_ends.replace(tzinfo=None)

            now = datetime.utcnow()
            should_process = now >= stabilization_ends

            if not should_process:
                remaining = (stabilization_ends - now).total_seconds()
                logger.debug(
                    "Thread still stabilizing",
                    extra={"data": {
                        "task_id": str(task.id),
                        "remaining_seconds": remaining
                    }}
                )

            return should_process

        except (ValueError, TypeError) as e:
            logger.warning(
                "Failed to parse stabilization time, allowing processing",
                extra={"data": {"task_id": str(task.id), "error": str(e)}}
            )
            return True

    async def create_thread_task(
        self,
        thread_id: str,
        emails: List[Dict[str, Any]],
        subject: str
    ) -> Optional[str]:
        """
        Create a new task for an email thread with stabilization window.

        Args:
            thread_id: Email thread ID
            emails: List of normalized emails in the thread
            subject: Thread subject line

        Returns:
            Created task ID if successful, None otherwise
        """
        # Sort emails by date
        sorted_emails = sorted(
            emails,
            key=lambda e: e.get('date', ''),
            reverse=False  # Oldest first
        )

        # Build consolidated task description
        email_count = len(sorted_emails)
        task_title = f"Email Thread: {subject} ({email_count} message{'s' if email_count > 1 else ''})"

        description_parts = [
            f"**Thread ID:** {thread_id}",
            f"**Messages:** {email_count}",
            "",
            "---",
            ""
        ]

        # Add each email to description
        for i, email in enumerate(sorted_emails, 1):
            description_parts.extend([
                f"### Message {i}",
                f"**From:** {email.get('from', 'Unknown')}",
                f"**To:** {email.get('to', '')}",
                f"**Date:** {email.get('date', '')}",
                "",
                email.get('content', ''),
                "",
                "---",
                ""
            ])

        task_description = "\n".join(description_parts)

        # Calculate stabilization end time
        stabilization_ends = datetime.utcnow() + timedelta(minutes=self.stabilization_minutes)

        # Create the task with thread metadata
        try:
            result_json = await create_task_tool(
                title=task_title,
                description=task_description,
                tags=["email", "thread"]
            )

            # Extract task ID from result
            task_id = self._extract_task_id(result_json)

            if task_id:
                # Update task metadata with thread consolidation fields
                await self._update_task_metadata(
                    task_id=task_id,
                    metadata={
                        "email_thread_id": thread_id,
                        "email_count": email_count,
                        "is_thread_stabilizing": True,
                        "thread_stabilization_ends_at": stabilization_ends.isoformat() + "Z",
                        "email_ids": [e.get('id') for e in sorted_emails]
                    }
                )

                logger.info(
                    "Created thread task with stabilization",
                    extra={"data": {
                        "task_id": task_id,
                        "thread_id": thread_id,
                        "email_count": email_count,
                        "stabilization_ends": stabilization_ends.isoformat()
                    }}
                )

            return task_id

        except Exception as e:
            logger.error(
                "Failed to create thread task",
                extra={"data": {"thread_id": thread_id, "error": str(e)}}
            )
            raise

    async def supersede_unprocessed_task(
        self,
        existing_task: Task,
        new_emails: List[Dict[str, Any]],
        all_thread_emails: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Supersede an unprocessed task with a new consolidated version.

        Used when new emails arrive in a thread where Nova hasn't started work yet.
        The old task is marked DONE with superseded metadata, and a new task
        is created with all emails consolidated.

        Args:
            existing_task: The current task for this thread (NEW or USER_INPUT_RECEIVED)
            new_emails: Newly arrived emails to add
            all_thread_emails: All emails in the thread (including new ones)

        Returns:
            New task ID if successful, None otherwise
        """
        metadata = existing_task.task_metadata or {}
        thread_id = metadata.get('email_thread_id', '')

        # Extract subject from existing task title
        subject = existing_task.title.replace("Email Thread: ", "").split(" (")[0]
        if existing_task.title.startswith("Read Email: "):
            subject = existing_task.title.replace("Read Email: ", "")

        # Create new consolidated task
        new_task_id = await self.create_thread_task(
            thread_id=thread_id,
            emails=all_thread_emails,
            subject=subject
        )

        if new_task_id:
            # Mark existing task as superseded
            await self._mark_task_superseded(
                task_id=str(existing_task.id),
                superseded_by_task_id=new_task_id,
                reason="thread_consolidation"
            )

            # Update new task to reference superseded task
            await self._update_task_metadata(
                task_id=new_task_id,
                metadata={
                    "supersedes_task_ids": [str(existing_task.id)]
                },
                merge=True
            )

            logger.info(
                "Superseded unprocessed task with consolidated version",
                extra={"data": {
                    "old_task_id": str(existing_task.id),
                    "new_task_id": new_task_id,
                    "thread_id": thread_id,
                    "total_emails": len(all_thread_emails)
                }}
            )

        return new_task_id

    async def create_continuation_task(
        self,
        completed_task: Task,
        new_emails: List[Dict[str, Any]],
        previous_summary: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a continuation task for a completed thread.

        Used when new emails arrive after Nova has already processed the thread.
        Includes an LLM-generated summary of the previous conversation.

        Args:
            completed_task: The completed (DONE/FAILED) task
            new_emails: New emails that arrived after completion
            previous_summary: Optional pre-generated summary of previous conversation

        Returns:
            New task ID if successful, None otherwise
        """
        metadata = completed_task.task_metadata or {}
        thread_id = metadata.get('email_thread_id', '')

        # Extract subject
        subject = completed_task.title.replace("Email Thread: ", "").split(" (")[0]
        if completed_task.title.startswith("Read Email: "):
            subject = completed_task.title.replace("Read Email: ", "")

        # Generate summary if not provided
        if not previous_summary:
            previous_summary = await self._generate_task_summary(completed_task)

        # Build continuation task
        email_count = len(new_emails)
        task_title = f"Email Thread Continuation: {subject} ({email_count} new message{'s' if email_count > 1 else ''})"

        description_parts = [
            f"**Thread ID:** {thread_id}",
            f"**New Messages:** {email_count}",
            "",
            "## Previous Conversation Summary",
            previous_summary or "No previous summary available.",
            "",
            "---",
            "",
            "## New Messages",
            ""
        ]

        # Sort and add new emails
        sorted_emails = sorted(new_emails, key=lambda e: e.get('date', ''))
        for i, email in enumerate(sorted_emails, 1):
            description_parts.extend([
                f"### New Message {i}",
                f"**From:** {email.get('from', 'Unknown')}",
                f"**To:** {email.get('to', '')}",
                f"**Date:** {email.get('date', '')}",
                "",
                email.get('content', ''),
                "",
                "---",
                ""
            ])

        task_description = "\n".join(description_parts)

        # Calculate stabilization window
        stabilization_ends = datetime.utcnow() + timedelta(minutes=self.stabilization_minutes)

        try:
            result_json = await create_task_tool(
                title=task_title,
                description=task_description,
                tags=["email", "thread", "continuation"]
            )

            task_id = self._extract_task_id(result_json)

            if task_id:
                await self._update_task_metadata(
                    task_id=task_id,
                    metadata={
                        "email_thread_id": thread_id,
                        "email_count": email_count,
                        "is_thread_stabilizing": True,
                        "thread_stabilization_ends_at": stabilization_ends.isoformat() + "Z",
                        "previous_task_id": str(completed_task.id),
                        "previous_task_summary": previous_summary,
                        "email_ids": [e.get('id') for e in sorted_emails]
                    }
                )

                logger.info(
                    "Created continuation task",
                    extra={"data": {
                        "task_id": task_id,
                        "previous_task_id": str(completed_task.id),
                        "thread_id": thread_id,
                        "new_email_count": email_count
                    }}
                )

            return task_id

        except Exception as e:
            logger.error(
                "Failed to create continuation task",
                extra={"data": {"thread_id": thread_id, "error": str(e)}}
            )
            raise

    async def reset_stabilization_window(self, task: Task) -> None:
        """
        Reset the stabilization window for a task.

        Called when new emails arrive in an already-stabilizing thread.

        Args:
            task: Task to reset stabilization for
        """
        new_stabilization_ends = datetime.utcnow() + timedelta(minutes=self.stabilization_minutes)

        await self._update_task_metadata(
            task_id=str(task.id),
            metadata={
                "is_thread_stabilizing": True,
                "thread_stabilization_ends_at": new_stabilization_ends.isoformat() + "Z"
            },
            merge=True
        )

        logger.info(
            "Reset stabilization window",
            extra={"data": {
                "task_id": str(task.id),
                "new_stabilization_ends": new_stabilization_ends.isoformat()
            }}
        )

    async def mark_stabilization_complete(self, task_id: str) -> None:
        """
        Mark a task as done stabilizing and ready for processing.

        Args:
            task_id: Task ID to update
        """
        await self._update_task_metadata(
            task_id=task_id,
            metadata={
                "is_thread_stabilizing": False,
                "thread_stabilization_ends_at": None
            },
            merge=True
        )

        logger.info(
            "Marked stabilization complete",
            extra={"data": {"task_id": task_id}}
        )

    async def get_thread_emails_from_processed_items(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all processed emails for a thread from the database.

        Args:
            thread_id: Email thread ID

        Returns:
            List of email metadata dictionaries
        """
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(ProcessedItem)
                .where(
                    and_(
                        ProcessedItem.source_type == "email",
                        ProcessedItem.source_metadata['thread_id'].astext == thread_id
                    )
                )
                .order_by(ProcessedItem.processed_at.asc())
            )

            items = result.scalars().all()
            return [item.source_metadata for item in items]

    async def _update_task_metadata(
        self,
        task_id: str,
        metadata: Dict[str, Any],
        merge: bool = False
    ) -> None:
        """
        Update task metadata in the database.

        Args:
            task_id: Task ID to update
            metadata: Metadata dictionary to set/merge
            merge: If True, merge with existing metadata; if False, replace
        """
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == UUID(task_id))
            )
            task = result.scalar_one_or_none()

            if task:
                if merge and task.task_metadata:
                    # Merge with existing metadata
                    updated_metadata = {**task.task_metadata, **metadata}
                else:
                    updated_metadata = metadata

                task.task_metadata = updated_metadata
                task.updated_at = datetime.utcnow()
                await session.commit()

    async def _mark_task_superseded(
        self,
        task_id: str,
        superseded_by_task_id: str,
        reason: str
    ) -> None:
        """
        Mark a task as superseded by another task.

        Args:
            task_id: Task ID to mark as superseded
            superseded_by_task_id: ID of the task that supersedes this one
            reason: Reason for superseding (e.g., "thread_consolidation")
        """
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == UUID(task_id))
            )
            task = result.scalar_one_or_none()

            if task:
                # Update metadata
                metadata = dict(task.task_metadata or {})
                metadata.update({
                    "superseded_by_task_id": superseded_by_task_id,
                    "superseded_reason": reason,
                    "superseded_at": datetime.utcnow().isoformat() + "Z"
                })
                task.task_metadata = metadata
                flag_modified(task, 'task_metadata')

                # Mark as DONE
                task.status = TaskStatus.DONE
                task.updated_at = datetime.utcnow()

                await session.commit()

                logger.info(
                    "Marked task as superseded",
                    extra={"data": {
                        "task_id": task_id,
                        "superseded_by": superseded_by_task_id,
                        "reason": reason
                    }}
                )

    async def _generate_task_summary(self, task: Task) -> str:
        """
        Generate a summary of a completed task for continuation context.

        For MVP, uses a simple extraction. Future versions could use LLM.

        Args:
            task: Completed task to summarize

        Returns:
            Summary string
        """
        # For MVP, extract key information from task
        parts = []

        if task.summary:
            parts.append(task.summary)
        else:
            # Extract from description
            if task.description:
                # Get first paragraph as summary
                paragraphs = task.description.split('\n\n')
                if paragraphs:
                    parts.append(paragraphs[0][:500])

        # Add any comments (agent responses)
        if task.comments:
            agent_comments = [c for c in task.comments if c.author == "agent"]
            if agent_comments:
                parts.append("\n**Agent's previous response:**")
                # Get last agent comment
                parts.append(agent_comments[-1].content[:500])

        return "\n".join(parts) if parts else "Previous task completed."

    def _extract_task_id(self, result_json: str) -> Optional[str]:
        """Extract task ID from task creation result."""
        import json
        try:
            if "Task created successfully:" in result_json:
                json_part = result_json.split("Task created successfully:", 1)[1].strip()
                task_data = json.loads(json_part)
                return task_data.get("id")
            return None
        except Exception as e:
            logger.error(
                "Failed to extract task ID from result",
                extra={"data": {"result": result_json[:200], "error": str(e)}}
            )
            return None
