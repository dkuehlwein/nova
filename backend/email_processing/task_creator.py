"""
Email to task conversion for Nova.

Handles converting normalized email data into Nova tasks with proper formatting.
"""
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from models.email import EmailMetadata
from models.user_settings import UserSettings
from tools.task_tools import create_task_tool
from utils.logging import get_logger

logger = get_logger(__name__)


class EmailTaskCreator:
    """Creates Nova tasks from email data."""
    
    async def create_task_from_email(
        self, 
        normalized_email: Dict[str, Any], 
        user_settings: UserSettings
    ) -> Optional[str]:
        """
        Create a Nova task from normalized email data.
        
        Args:
            normalized_email: Normalized email dict from EmailNormalizer
            user_settings: User settings for preferences and timezone
            
        Returns:
            Task ID if successful, None otherwise
        """
        try:
            # Extract metadata from normalized email
            metadata = self._create_metadata(normalized_email)
            
            # Create task title and description
            task_title = f"Read Email: {metadata.subject}"
            task_description = self._format_task_description(
                metadata, 
                normalized_email.get("content", ""), 
                user_settings
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
    
    def _create_metadata(self, normalized_email: Dict[str, Any]) -> EmailMetadata:
        """Create EmailMetadata from normalized email data."""
        # Parse date properly
        email_date = self._parse_email_date(normalized_email.get("date"))
        
        # Generate email ID if missing
        email_id = normalized_email.get("id") or self._generate_email_id(normalized_email)
        
        return EmailMetadata(
            email_id=email_id,
            thread_id=normalized_email.get("thread_id", ""),
            subject=normalized_email.get("subject", "No Subject"),
            sender=normalized_email.get("from", "Unknown Sender"),
            recipient=normalized_email.get("to", ""),
            date=email_date,
            has_attachments=normalized_email.get("has_attachments", False),
            labels=normalized_email.get("labels", [])
        )
    
    def _parse_email_date(self, date_str: str = None) -> datetime:
        """Parse email date string into datetime object with proper timezone handling."""
        if not date_str:
            return datetime.utcnow()
        
        try:
            # Import email utils for RFC 2822 date parsing
            from email.utils import parsedate_to_datetime
            
            # Parse RFC 2822 date format (standard email date format)
            parsed_date = parsedate_to_datetime(date_str)
            
            # Store as UTC internally for consistency, but preserve original timezone info
            # for user-facing display in _format_task_description
            if parsed_date.tzinfo is not None:
                from datetime import timezone
                utc_date = parsed_date.astimezone(timezone.utc)
                return utc_date.replace(tzinfo=None)  # Store as naive UTC
            else:
                # If no timezone info, assume it's already in a reasonable timezone
                return parsed_date
                
        except Exception as e:
            logger.warning(f"Failed to parse email date '{date_str}': {e}")
            return datetime.utcnow()
    
    def _generate_email_id(self, normalized_email: Dict[str, Any]) -> str:
        """Generate a unique email ID from email metadata."""
        # Create hash from subject, sender, and date for uniqueness
        content = f"{normalized_email.get('subject', '')}{normalized_email.get('from', '')}{normalized_email.get('date', '')}"
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        return f"email_{content_hash}"
    
    def _format_task_description(
        self, 
        metadata: EmailMetadata, 
        body: str, 
        user_settings: UserSettings
    ) -> str:
        """Format task description with email metadata and content."""
        # Format date in user's timezone for better UX
        formatted_date = self._format_date_for_user(metadata.date, user_settings.timezone)
        
        description_parts = [
            f"**From:** {metadata.sender}",
            f"**To:** {metadata.recipient}",
            f"**Date:** {formatted_date}",
            f"**Email ID:** {metadata.email_id}",
        ]
        
        if metadata.has_attachments:
            description_parts.append("**Attachments:** Yes")
        
        description_parts.extend([
            "",
            "---",
            "",
            "**Email Content:**",
            "",
            body
        ])
        
        return "\n".join(description_parts)
    
    def _format_date_for_user(self, utc_date: datetime, user_timezone: str) -> str:
        """Format datetime in user's timezone for display."""
        try:
            # Convert UTC datetime to user's timezone
            import pytz
            from datetime import timezone
            
            # Make UTC datetime timezone-aware
            utc_aware = utc_date.replace(tzinfo=timezone.utc)
            
            # Convert to user's timezone
            user_tz = pytz.timezone(user_timezone)
            local_date = utc_aware.astimezone(user_tz)
            
            # Format with timezone abbreviation
            tz_abbrev = local_date.strftime('%Z')
            return local_date.strftime(f'%Y-%m-%d %H:%M:%S {tz_abbrev}')
            
        except Exception as e:
            logger.warning(f"Failed to format date for user timezone '{user_timezone}': {e}")
            # Fallback to UTC
            return utc_date.strftime('%Y-%m-%d %H:%M:%S UTC')
    
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