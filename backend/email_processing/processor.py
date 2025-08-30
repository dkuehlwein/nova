"""
Email processing orchestration for Nova.

Coordinates the email-to-task pipeline using specialized components.
"""
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import select
from database.database import db_manager
from models.models import ProcessedEmail
from models.email import EmailMetadata
from utils.logging import get_logger
from .normalizer import EmailNormalizer
from .fetcher import EmailFetcher
from .task_creator import EmailTaskCreator

logger = get_logger(__name__)


class EmailProcessor:
    """Orchestrates the email-to-task processing pipeline."""
    
    def __init__(self):
        self.normalizer = EmailNormalizer()
        self.fetcher = EmailFetcher()
        self.task_creator = EmailTaskCreator()
    
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
        
        Args:
            normalized_email: Email data in normalized format
            hook_config: EmailHookConfig from the hook system
            
        Returns:
            True if task was created, False otherwise
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
                    "sender": normalized_email.get("from", "")
                }}
            )
            
            # Check if already processed (safety check)
            if await self._is_email_processed(email_id):
                logger.info(
                    "Email already processed, skipping",
                    extra={"data": {"email_id": email_id}}
                )
                return False
            
            # Create task from email
            task_id = await self.task_creator.create_task_from_email(normalized_email)
            
            if task_id:
                # Create metadata for database record
                metadata = self.task_creator._create_metadata(normalized_email)
                
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
            # Query for already processed emails
            stmt = select(ProcessedEmail.email_id).where(
                ProcessedEmail.email_id.in_(email_ids)
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
            stmt = select(ProcessedEmail).where(ProcessedEmail.email_id == email_id)
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
            processed_email = ProcessedEmail(
                email_id=email_id,
                thread_id=metadata.thread_id,
                subject=metadata.subject,
                sender=metadata.sender,
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