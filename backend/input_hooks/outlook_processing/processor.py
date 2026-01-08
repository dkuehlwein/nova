"""
Outlook email processing orchestration for Nova.

Coordinates the Outlook email-to-task pipeline:
1. Fetch unprocessed emails from Outlook
2. Create Nova tasks from emails
3. Mark emails as processed in Outlook
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from tools.task_tools import create_task_tool
from utils.logging import get_logger
from .fetcher import OutlookFetcher

logger = get_logger(__name__)


@dataclass
class OutlookProcessingResult:
    """Result of processing Outlook emails."""
    emails_fetched: int = 0
    tasks_created: int = 0
    emails_marked: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "emails_fetched": self.emails_fetched,
            "tasks_created": self.tasks_created,
            "emails_marked": self.emails_marked,
            "errors": self.errors,
            "success": len(self.errors) == 0
        }


class OutlookProcessor:
    """Orchestrates the Outlook email-to-task processing pipeline."""

    def __init__(self):
        self.fetcher = OutlookFetcher()

    async def process_emails(
        self,
        max_emails: int = 50,
        folder: str = "inbox",
        since_date: Optional[str] = None
    ) -> OutlookProcessingResult:
        """
        Process unprocessed Outlook emails and create Nova tasks.

        Args:
            max_emails: Maximum number of emails to process
            folder: Outlook folder to process
            since_date: Only process emails from this date onwards (YYYY-MM-DD)

        Returns:
            OutlookProcessingResult with processing statistics
        """
        result = OutlookProcessingResult()

        try:
            # Step 1: Fetch unprocessed emails
            logger.info(
                "Starting Outlook email processing",
                extra={"data": {"max_emails": max_emails, "folder": folder, "since_date": since_date}}
            )

            emails = await self.fetcher.fetch_unprocessed_emails(
                max_emails=max_emails,
                folder=folder,
                since_date=since_date
            )

            result.emails_fetched = len(emails)

            if not emails:
                logger.info("No unprocessed Outlook emails found")
                return result

            logger.info(
                f"Processing {len(emails)} Outlook emails",
                extra={"data": {"count": len(emails)}}
            )

            # Step 2: Process each email
            for email in emails:
                email_id = email.get("id")
                subject = email.get("subject", "(No Subject)")

                try:
                    # Create Nova task from email
                    task_id = await self._create_task_from_email(email)

                    if task_id:
                        result.tasks_created += 1

                        # Mark email as processed in Outlook
                        marked = await self.fetcher.mark_email_processed(email_id)
                        if marked:
                            result.emails_marked += 1
                        else:
                            result.errors.append(
                                f"Failed to mark email {email_id} as processed"
                            )

                        logger.info(
                            f"Created task from Outlook email",
                            extra={"data": {
                                "email_id": email_id,
                                "task_id": task_id,
                                "subject": subject[:100]
                            }}
                        )
                    else:
                        result.errors.append(
                            f"Failed to create task for email: {subject[:50]}"
                        )

                except Exception as e:
                    error_msg = f"Error processing email {email_id}: {str(e)}"
                    result.errors.append(error_msg)
                    logger.error(
                        error_msg,
                        exc_info=True,
                        extra={"data": {"email_id": email_id}}
                    )

            logger.info(
                "Outlook email processing completed",
                extra={"data": result.to_dict()}
            )

            return result

        except Exception as e:
            result.errors.append(f"Processing failed: {str(e)}")
            logger.error(
                "Outlook email processing failed",
                exc_info=True,
                extra={"data": {"error": str(e)}}
            )
            raise

    async def _create_task_from_email(self, email: Dict[str, Any]) -> Optional[str]:
        """
        Create a Nova task from an Outlook email.

        Args:
            email: Outlook email data dict

        Returns:
            Task ID if successful, None otherwise
        """
        try:
            # Extract email fields
            email_id = email.get("id", "")
            subject = email.get("subject", "(No Subject)")
            sender_name = email.get("sender_name", "Unknown")
            sender_email = email.get("sender_email", "")
            date = email.get("date", "")
            body = email.get("body", email.get("content", ""))
            to_recipients = email.get("to", [])
            is_read = email.get("is_read", False)

            # Format sender
            if sender_email:
                sender = f"{sender_name} <{sender_email}>"
            else:
                sender = sender_name

            # Format recipients
            if isinstance(to_recipients, list):
                recipients = ", ".join(to_recipients)
            else:
                recipients = str(to_recipients) if to_recipients else ""

            # Create task title (per user spec: "Read Outlook Email: {subject}")
            task_title = f"Read Outlook Email: {subject}"

            # Create task description
            task_description = self._format_task_description(
                email_id=email_id,
                sender=sender,
                recipients=recipients,
                date=date,
                body=body,
                is_read=is_read
            )

            # Create the task
            result_json = await create_task_tool(
                title=task_title,
                description=task_description,
                tags=["outlook", "email"]
            )

            # Extract task ID from result
            task_id = self._extract_task_id(result_json)

            return task_id

        except Exception as e:
            logger.error(
                "Failed to create task from Outlook email",
                extra={"data": {"email_id": email.get("id"), "error": str(e)}}
            )
            raise

    def _format_task_description(
        self,
        email_id: str,
        sender: str,
        recipients: str,
        date: str,
        body: str,
        is_read: bool
    ) -> str:
        """Format the task description with email content."""
        parts = [
            f"**From:** {sender}",
            f"**To:** {recipients}" if recipients else None,
            f"**Date:** {date}",
            f"**Outlook Email ID:** {email_id}",
            f"**Read Status:** {'Read' if is_read else 'Unread'}",
            "",
            "---",
            "",
            "**Email Content:**",
            "",
            body[:5000] if body else "(No content)",  # Limit body size
        ]

        return "\n".join(p for p in parts if p is not None)

    def _extract_task_id(self, result_json: str) -> Optional[str]:
        """Extract task ID from create_task_tool result."""
        try:
            if "Task created successfully:" in result_json:
                json_part = result_json.split("Task created successfully:", 1)[1].strip()
                task_data = json.loads(json_part)
                return task_data.get("id")
            else:
                logger.error(
                    "Unexpected task creation result",
                    extra={"data": {"result": result_json[:200]}}
                )
                return None
        except Exception as e:
            logger.error(
                "Failed to parse task creation result",
                extra={"data": {"result": result_json[:200], "error": str(e)}}
            )
            return None

    async def health_check(self) -> Dict[str, Any]:
        """Check health of Outlook processing components."""
        return await self.fetcher.health_check()
