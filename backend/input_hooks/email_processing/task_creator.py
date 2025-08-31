"""
Email to task conversion for Nova.

Handles converting normalized email data into Nova tasks with proper formatting.
"""
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from models.email import EmailMetadata
from tools.task_tools import create_task_tool
from utils.logging import get_logger
from ..datetime_utils import parse_datetime

logger = get_logger(__name__)


class EmailTaskCreator:
    """Creates Nova tasks from email data."""
    
    async def create_task_from_email(
        self, 
        normalized_email: Dict[str, Any], 
    ) -> Optional[str]:
        """
        Create a Nova task from normalized email data.
        
        Args:
            normalized_email: Normalized email dict from EmailNormalizer
            hook_config: EmailHookConfig from the hook system
            
        Returns:
            Task ID if successful, None otherwise
        """
        try:
            # Extract metadata from normalized email
            metadata = await self._create_metadata(normalized_email)
            
            # Create task title and description
            task_title = f"Read Email: {metadata.subject}"
            task_description = self._format_task_description(
                metadata,                 
                normalized_email
            )
            
            # Create the task
            result_json = await create_task_tool(
                title=task_title,
                description=task_description,
                tags=["email"]  # Tag as email-generated task
            )
            
            # Parse the result to extract task ID
            task_id = self._extract_task_id(result_json, metadata.email_id)
            
            if task_id:
                logger.info(
                    "Created task from email",
                    extra={"data": {
                        "email_id": metadata.email_id,
                        "task_id": task_id,
                        "task_title": task_title
                    }}
                )
            
            return task_id
                    
        except Exception as e:
            logger.error(
                "Failed to create task from email",
                extra={"data": {
                    "email_id": normalized_email.get("id", "unknown"),
                    "error": str(e)
                }}
            )
            raise
    
    async def _create_metadata(self, normalized_email: Dict[str, Any]) -> EmailMetadata:
        """Create EmailMetadata from normalized email data."""
        # Generate email ID if missing
        email_id = normalized_email.get("id") or self._generate_email_id(normalized_email)
        
        return EmailMetadata(
            email_id=email_id,
            thread_id=normalized_email.get("thread_id", ""),
            subject=normalized_email.get("subject", "No Subject"),
            sender=normalized_email.get("from", "Unknown Sender"),
            recipient=normalized_email.get("to", ""),
            date=self._ensure_naive_datetime(parse_datetime(normalized_email.get("date"), source_type="email")),
            has_attachments=normalized_email.get("has_attachments", False),
            labels=normalized_email.get("labels", [])
        )
    
    def _generate_email_id(self, normalized_email: Dict[str, Any]) -> str:
        """Generate a unique email ID from email metadata."""
        # Create hash from subject, sender, and date for uniqueness
        content = f"{normalized_email.get('subject', '')}{normalized_email.get('from', '')}{normalized_email.get('date', '')}"
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        return f"email_{content_hash}"
    
    def _ensure_naive_datetime(self, dt: datetime) -> datetime:
        """Convert datetime to naive (no timezone) for database storage."""
        if dt and dt.tzinfo:
            return dt.replace(tzinfo=None)
        return dt
    
    async def _get_user_timezone(self) -> str:
        """Get user's timezone setting from database."""
        try:
            from database.database import db_manager
            from models.user_settings import UserSettings
            from sqlalchemy import select
            
            async with db_manager.get_session() as session:
                stmt = select(UserSettings.timezone).limit(1)
                result = await session.execute(stmt)
                timezone_row = result.first()
                
                if timezone_row and timezone_row[0]:
                    return timezone_row[0]
                else:
                    logger.info("No user timezone found, defaulting to UTC")
                    return "UTC"
                    
        except Exception as e:
            logger.error(f"Failed to get user timezone: {e}")
            return "UTC"  # Safe fallback
    
    def _format_task_description(
        self, 
        metadata: EmailMetadata, 
        normalized_email: Dict[str, Any] = None
    ) -> str:
        """Format task description with email metadata and content."""

        
        # Include both the generated Nova email ID and original Gmail message ID
        description_parts = [
            f"**From:** {metadata.sender}\n",
            f"**To:** {metadata.recipient}\n",
            f"**Date:** {metadata.date}\n",
            f"**Email ID:** {metadata.email_id}\n",
        ]
        
        # If we have the original Gmail message ID, include it for agent tools
        if normalized_email:
            original_gmail_id = normalized_email.get("id")
            if original_gmail_id and original_gmail_id != metadata.email_id:
                description_parts.append(f"**Gmail Message ID:** {original_gmail_id}\n")
            elif original_gmail_id:
                # If they're the same, the agent should use the Email ID field
                description_parts.append(f"**Gmail Message ID:** {original_gmail_id}\n")
        
        if metadata.has_attachments:
            description_parts.append("**Attachments:** Yes\n")
        
        description_parts.extend([
            "",
            "---",
            "",
            "**Email Content:**",
            "",
            normalized_email.get("content", "")
        ])
        
        return "\n".join(description_parts)
    

    
    def _extract_task_id(self, result_json: str, email_id: str) -> Optional[str]:
        """Extract task ID from task creation result."""
        try:
            import json
            if "Task created successfully:" in result_json:
                # Extract the JSON part after the prefix
                json_part = result_json.split("Task created successfully:", 1)[1].strip()
                task_data = json.loads(json_part)
                task_id = task_data.get("id")
                
                if task_id:
                    return task_id
                else:
                    logger.error(
                        "Failed to extract task ID from result",
                        extra={"data": {
                            "email_id": email_id,
                            "result": result_json
                        }}
                    )
                    return None
            else:
                logger.error(
                    "Task creation failed",
                    extra={"data": {
                        "email_id": email_id,
                        "result": result_json
                    }}
                )
                return None
                
        except Exception as e:
            logger.error(
                "Failed to parse task creation result",
                extra={"data": {
                    "email_id": email_id,
                    "result": result_json,
                    "error": str(e)
                }}
            )
            return None