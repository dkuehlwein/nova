"""
Email processing orchestration for Nova.

Coordinates the email-to-task pipeline using specialized components.
Supports thread consolidation for grouping related emails (see ADR-019).
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from database.database import db_manager
from models.models import ProcessedItem, Task, TaskStatus
from models.email import EmailMetadata
from utils.logging import get_logger
from .normalizer import EmailNormalizer
from .fetcher import EmailFetcher
from .task_creator import EmailTaskCreator
from .thread_consolidator import EmailThreadConsolidator

logger = get_logger(__name__)


class EmailProcessor:
    """Orchestrates the email-to-task processing pipeline."""

    def __init__(self, thread_consolidation_enabled: bool = False, stabilization_minutes: int = 15):
        """
        Initialize the email processor.

        Args:
            thread_consolidation_enabled: Whether to enable thread-based task grouping
            stabilization_minutes: Minutes to wait after last email before processing
        """
        self.normalizer = EmailNormalizer()
        self.fetcher = EmailFetcher()
        self.task_creator = EmailTaskCreator()
        self.thread_consolidation_enabled = thread_consolidation_enabled
        self.thread_consolidator = EmailThreadConsolidator(stabilization_minutes=stabilization_minutes)
    
    async def fetch_new_emails(self, hook_config) -> List[Dict[str, Any]]:
        """
        Fetch new emails from email provider and filter out already processed ones.
        
        Args:
            hook_config: EmailHookConfig from the hook system
        
        Returns:
            List of normalized email dictionaries
        """
        try:
            # Fetch emails from MCP using hook configuration
            raw_emails = await self.fetcher.fetch_new_emails(hook_config)
            
            if not raw_emails:
                return []
            
            # Normalize all emails to unified format
            normalized_emails = []
            for raw_email in raw_emails:
                try:
                    normalized = self.normalizer.normalize(raw_email)
                    normalized_emails.append(normalized)
                except Exception as e:
                    logger.error(
                        "Failed to normalize email",
                        extra={"data": {"error": str(e), "email_keys": list(raw_email.keys())}}
                    )
                    continue
            
            # Filter out already processed emails
            new_emails = await self._filter_new_emails(normalized_emails)
            
            logger.info(
                "Email processing summary",
                extra={"data": {
                    "raw_emails": len(raw_emails),
                    "normalized_emails": len(normalized_emails),
                    "new_emails": len(new_emails)
                }}
            )
            
            return new_emails
            
        except Exception as e:
            logger.error(
                "Failed to fetch and process emails",
                extra={"data": {"error": str(e)}}
            )
            raise
    
    async def process_email(self, normalized_email: Dict[str, Any], hook_config) -> bool:
        """
        Process a single normalized email and create a task if needed.

        If thread consolidation is enabled, delegates to thread-aware processing.

        Args:
            normalized_email: Email data in normalized format
            hook_config: EmailHookConfig from the hook system

        Returns:
            True if task was created/updated, False otherwise
        """
        start_time = datetime.utcnow()
        email_id = normalized_email.get("id", "unknown")

        try:
            # Check if task creation from emails is enabled
            if not hook_config.create_tasks:
                logger.info(
                    "Task creation from emails is disabled in hook config",
                    extra={"data": {"email_id": email_id, "hook_name": hook_config.name}}
                )
                return False

            logger.info(
                "Processing email",
                extra={"data": {
                    "email_id": email_id,
                    "subject": normalized_email.get("subject", "")[:100],
                    "sender": normalized_email.get("from", ""),
                    "thread_consolidation": self.thread_consolidation_enabled
                }}
            )

            # Check if already processed (safety check)
            if await self._is_email_processed(email_id):
                logger.info(
                    "Email already processed, skipping",
                    extra={"data": {"email_id": email_id}}
                )
                return False

            # Use thread consolidation if enabled and email has thread_id
            thread_id = normalized_email.get("thread_id")
            if self.thread_consolidation_enabled and thread_id:
                return await self._process_with_thread_consolidation(normalized_email, hook_config)

            # Standard single-email processing
            task_id = await self.task_creator.create_task_from_email(normalized_email)

            if task_id:
                # Create metadata for database record
                metadata = await self.task_creator._create_metadata(normalized_email)

                # Mark as processed in database
                await self._mark_email_processed(email_id, metadata, task_id)

                processing_time = (datetime.utcnow() - start_time).total_seconds()

                logger.info(
                    "Email processing completed successfully",
                    extra={"data": {
                        "email_id": email_id,
                        "task_id": task_id,
                        "processing_time_seconds": processing_time
                    }}
                )

                return True
            else:
                logger.error(
                    "Failed to create task from email",
                    extra={"data": {"email_id": email_id}}
                )
                return False

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            logger.error(
                "Email processing failed",
                extra={"data": {
                    "email_id": email_id,
                    "error": str(e),
                    "processing_time_seconds": processing_time
                }}
            )
            raise

    async def _process_with_thread_consolidation(
        self,
        normalized_email: Dict[str, Any],
        hook_config
    ) -> bool:
        """
        Process email with thread-based consolidation.

        Handles different scenarios based on existing task state:
        - No task: Create new task with stabilization window
        - NEW/USER_INPUT_RECEIVED: Supersede with consolidated version
        - DONE/FAILED: Create continuation task with summary
        - IN_PROGRESS: Skip (will be handled on next poll)

        Args:
            normalized_email: Email data in normalized format
            hook_config: EmailHookConfig from the hook system

        Returns:
            True if task was created/updated, False otherwise
        """
        email_id = normalized_email.get("id", "unknown")
        thread_id = normalized_email.get("thread_id", "")
        subject = normalized_email.get("subject", "No Subject")

        logger.info(
            "Processing email with thread consolidation",
            extra={"data": {"email_id": email_id, "thread_id": thread_id}}
        )

        # Find existing task for this thread
        existing_task = await self.thread_consolidator.find_existing_thread_task(thread_id)

        if existing_task is None:
            # No existing task - create new thread task
            task_id = await self.thread_consolidator.create_thread_task(
                thread_id=thread_id,
                emails=[normalized_email],
                subject=subject
            )

            if task_id:
                metadata = await self.task_creator._create_metadata(normalized_email)
                await self._mark_email_processed(email_id, metadata, task_id)
                return True
            return False

        # Handle based on existing task status
        task_status = existing_task.status

        if task_status == TaskStatus.IN_PROGRESS:
            # Skip - will be handled on next poll after processing completes
            logger.info(
                "Thread task is in progress, skipping consolidation",
                extra={"data": {"task_id": str(existing_task.id), "email_id": email_id}}
            )
            return False

        if task_status in [TaskStatus.NEW, TaskStatus.USER_INPUT_RECEIVED]:
            # Nova hasn't processed yet - supersede with consolidated version
            all_thread_emails = await self._get_all_thread_emails(thread_id, normalized_email)

            new_task_id = await self.thread_consolidator.supersede_unprocessed_task(
                existing_task=existing_task,
                new_emails=[normalized_email],
                all_thread_emails=all_thread_emails
            )

            if new_task_id:
                metadata = await self.task_creator._create_metadata(normalized_email)
                await self._mark_email_processed(email_id, metadata, new_task_id)
                return True
            return False

        if task_status in [TaskStatus.DONE, TaskStatus.FAILED]:
            # Thread was already processed - create continuation task
            new_task_id = await self.thread_consolidator.create_continuation_task(
                completed_task=existing_task,
                new_emails=[normalized_email]
            )

            if new_task_id:
                metadata = await self.task_creator._create_metadata(normalized_email)
                await self._mark_email_processed(email_id, metadata, new_task_id)
                return True
            return False

        # NEEDS_REVIEW or other status - reset stabilization and add to thread
        await self.thread_consolidator.reset_stabilization_window(existing_task)
        metadata = await self.task_creator._create_metadata(normalized_email)
        await self._mark_email_processed(email_id, metadata, str(existing_task.id))

        # Update existing task with new email count
        await self._append_email_to_task(existing_task, normalized_email)
        return True

    async def _get_all_thread_emails(
        self,
        thread_id: str,
        new_email: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get all emails in a thread, including the new one.

        Args:
            thread_id: Email thread ID
            new_email: The newly arrived email

        Returns:
            List of all email dictionaries in the thread
        """
        # Get previously processed emails from database
        existing_emails = await self.thread_consolidator.get_thread_emails_from_processed_items(thread_id)

        # Add the new email
        all_emails = existing_emails + [new_email]

        return all_emails

    async def _append_email_to_task(self, task: Task, email: Dict[str, Any]) -> None:
        """
        Append a new email to an existing thread task's description.

        Args:
            task: Existing task to update
            email: New email to append
        """
        from tools.task_tools import update_task_tool

        # Get current email count
        metadata = task.task_metadata or {}
        email_count = metadata.get('email_count', 1) + 1

        # Update title with new count
        subject = task.title.replace("Email Thread: ", "").split(" (")[0]
        new_title = f"Email Thread: {subject} ({email_count} messages)"

        # Append new email to description
        new_email_section = "\n".join([
            "",
            f"### Message {email_count}",
            f"**From:** {email.get('from', 'Unknown')}",
            f"**To:** {email.get('to', '')}",
            f"**Date:** {email.get('date', '')}",
            "",
            email.get('content', ''),
            "",
            "---",
            ""
        ])

        new_description = (task.description or "") + new_email_section

        await update_task_tool(
            task_id=str(task.id),
            title=new_title,
            description=new_description
        )

        # Update metadata
        await self.thread_consolidator._update_task_metadata(
            task_id=str(task.id),
            metadata={"email_count": email_count},
            merge=True
        )
    
    
    async def _filter_new_emails(self, normalized_emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out already processed emails using database lookup."""
        if not normalized_emails:
            return []
        
        # Extract email IDs (generate them if missing)
        email_ids = []
        for email in normalized_emails:
            email_id = email.get("id")
            if not email_id:
                # Generate ID using same logic as task creator
                content = f"{email.get('subject', '')}{email.get('from', '')}{email.get('date', '')}"
                import hashlib
                content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
                email_id = f"email_{content_hash}"
                email["id"] = email_id  # Update the email dict
            email_ids.append(email_id)
        
        async with db_manager.get_session() as session:
            # Query for already processed emails (now in ProcessedItem table)
            stmt = select(ProcessedItem.source_id).where(
                ProcessedItem.source_type == "email",
                ProcessedItem.source_id.in_(email_ids)
            )
            result = await session.execute(stmt)
            processed_ids = {row[0] for row in result.fetchall()}
            
            # Return only new emails
            new_emails = [email for email in normalized_emails if email["id"] not in processed_ids]
            
            logger.info(
                "Email deduplication check completed",
                extra={"data": {
                    "total_emails": len(normalized_emails),
                    "already_processed": len(processed_ids),
                    "new_emails": len(new_emails)
                }}
            )
            
            return new_emails
    
    async def _is_email_processed(self, email_id: str) -> bool:
        """Check if email has already been processed."""
        async with db_manager.get_session() as session:
            stmt = select(ProcessedItem).where(
                ProcessedItem.source_type == "email",
                ProcessedItem.source_id == email_id
            )
            result = await session.execute(stmt)
            return result.first() is not None
    
    async def _mark_email_processed(
        self, 
        email_id: str, 
        metadata: EmailMetadata, 
        task_id: str
    ) -> None:
        """Mark email as processed in database."""
        async with db_manager.get_session() as session:
            processed_email = ProcessedItem(
                source_type="email",
                source_id=email_id,
                source_metadata={
                    "thread_id": metadata.thread_id,
                    "subject": metadata.subject,
                    "sender": metadata.sender
                },
                processed_at=datetime.utcnow(),
                task_id=task_id
            )
            
            session.add(processed_email)
            await session.commit()
            
            logger.info(
                "Marked email as processed",
                extra={"data": {
                    "email_id": email_id,
                    "task_id": task_id
                }}
            )
    
    async def close(self):
        """Clean up resources."""
        # Clear cached tools in fetcher
        if hasattr(self.fetcher, 'mcp_tools'):
            self.fetcher.mcp_tools = None
        logger.debug("Email processor resources cleaned up")