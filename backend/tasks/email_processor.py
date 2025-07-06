"""
Email processing core component for Nova.
"""
import asyncio
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import select, text
from utils.logging import get_logger
from config import settings
from database.database import db_manager
from models.models import ProcessedEmail
from mcp_client import mcp_manager
from tools.task_tools import create_task_tool
from models.email import EmailMetadata, EmailProcessingResult

logger = get_logger(__name__)


class EmailProcessor:
    """Handles email fetching and task creation with proper deduplication."""
    
    def __init__(self):
        self.mcp_tools = None
    
    async def _get_email_tools(self) -> Dict[str, Any]:
        """Get email-related MCP tools using configurable interface mapping."""
        if self.mcp_tools is None:
            # Get all available MCP tools
            all_tools = await mcp_manager.get_tools()
            
            # Import email interface configuration
            from config.email_interface import EMAIL_TOOL_INTERFACE
            
            self.mcp_tools = {}
            tool_mapping = {}
            
            # Map available tools to our interface
            for tool in all_tools:
                tool_name = getattr(tool, 'name', '')
                for interface_name, possible_names in EMAIL_TOOL_INTERFACE.items():
                    if tool_name in possible_names:
                        self.mcp_tools[interface_name] = tool
                        tool_mapping[interface_name] = tool_name
                        break
            
            logger.info(
                f"Found {len(self.mcp_tools)} email tools: {tool_mapping}",
                extra={"data": {"interface_mapping": tool_mapping}}
            )
        
        return self.mcp_tools
    
    async def _call_email_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call an email MCP tool with the given parameters."""
        tools = await self._get_email_tools()
        
        if tool_name not in tools:
            raise ValueError(f"Email tool '{tool_name}' not available. Available tools: {list(tools.keys())}")
        
        tool = tools[tool_name]
        concrete_tool_name = getattr(tool, 'name', tool_name)
        
        # Map parameters based on concrete tool name
        from config.email_interface import EMAIL_TOOL_PARAMETERS
        parameter_mapping = EMAIL_TOOL_PARAMETERS.get(concrete_tool_name, {})
        
        # Apply parameter mapping
        mapped_kwargs = {}
        for param_key, param_value in kwargs.items():
            mapped_key = parameter_mapping.get(param_key, param_key)
            mapped_kwargs[mapped_key] = param_value
        
        try:
            # Call the tool with the mapped arguments
            result = await tool.arun(**mapped_kwargs)
            
            # Parse the result if it's a string (some MCP tools return JSON strings)
            if isinstance(result, str):
                import json
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    # If it's not JSON, wrap it in a simple structure
                    result = {"data": result}
            
            return result
            
        except Exception as e:
            logger.error(
                f"Failed to call email tool {tool_name} (concrete: {concrete_tool_name})",
                extra={"data": {"interface_tool": tool_name, "concrete_tool": concrete_tool_name, "error": str(e), "kwargs": mapped_kwargs}}
            )
            raise
    
    async def fetch_new_emails(self) -> List[Dict[str, Any]]:
        """
        Fetch new emails from email provider with dynamic configuration.
        
        Returns:
            List of email dictionaries
        """
        try:
            # Check if email processing is enabled
            if not settings.EMAIL_ENABLED:
                logger.info("Email processing is disabled in current configuration")
                return []
            
            # Test MCP connection health by checking available tools
            try:
                tools = await self._get_email_tools()
                if not tools:
                    logger.error("No email tools available from MCP servers")
                    return []
                
                # Quick health check by calling list_labels interface
                if "list_labels" in tools:
                    await self._call_email_tool("list_labels")
                    logger.debug("Email API health check passed")
                else:
                    logger.warning("list_labels tool not available, skipping health check")
                    
            except Exception as e:
                logger.error(
                    "Email API health check failed",
                    extra={"data": {"error": str(e)}}
                )
                raise
            
            # Fetch emails using MCP client
            logger.info(
                "Fetching emails from email provider",
                extra={"data": {
                    "max_results": settings.EMAIL_MAX_PER_FETCH,
                    "label_filter": settings.EMAIL_LABEL_FILTER
                }}
            )
            
            # Call email list_emails interface via MCP
            result = await self._call_email_tool(
                "list_emails",
                max_results=settings.EMAIL_MAX_PER_FETCH
            )
            
            if not result or "messages" not in result:
                logger.info("No messages found or invalid response from email API")
                return []
            
            messages = result["messages"]
            logger.info(
                "Fetched message list from email provider",
                extra={"data": {"message_count": len(messages)}}
            )
            
            # Filter out already processed emails
            new_messages = await self._filter_new_messages(messages)
            
            logger.info(
                "Filtered new messages",
                extra={"data": {
                    "total_messages": len(messages),
                    "new_messages": len(new_messages)
                }}
            )
            
            # Get full message details for new messages
            emails = []
            for message_info in new_messages:
                try:
                    message_id = message_info["id"]
                    
                    # Get full message details
                    message_result = await self._call_email_tool(
                        "get_email",
                        message_id=message_id
                    )
                    
                    if message_result:
                        emails.append(message_result)
                        
                except Exception as e:
                    logger.error(
                        "Failed to fetch individual email details",
                        extra={"data": {
                            "message_id": message_info.get("id"),
                            "error": str(e)
                        }}
                    )
                    continue
            
            logger.info(
                "Successfully fetched email details",
                extra={"data": {"email_count": len(emails)}}
            )
            
            return emails
            
        except Exception as e:
            logger.error(
                "Failed to fetch emails",
                extra={"data": {"error": str(e)}}
            )
            raise
    
    async def _filter_new_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out already processed messages using database lookup."""
        if not messages:
            return []
        
        message_ids = [msg["id"] for msg in messages]
        
        async with db_manager.get_session() as session:
            # Query for already processed emails
            stmt = select(ProcessedEmail.email_id).where(
                ProcessedEmail.email_id.in_(message_ids)
            )
            result = await session.execute(stmt)
            processed_ids = {row[0] for row in result.fetchall()}
            
            # Return only new messages
            new_messages = [msg for msg in messages if msg["id"] not in processed_ids]
            
            logger.info(
                "Email deduplication check completed",
                extra={"data": {
                    "total_messages": len(messages),
                    "already_processed": len(processed_ids),
                    "new_messages": len(new_messages)
                }}
            )
            
            return new_messages
    
    async def process_email(self, email_data: Dict[str, Any]) -> bool:
        """
        Process a single email and create a task if needed.
        
        Args:
            email_data: Email data from email API
            
        Returns:
            True if task was created, False otherwise
        """
        start_time = datetime.utcnow()
        email_id = email_data.get("id")
        
        try:
            # Check if task creation from emails is enabled
            if not settings.EMAIL_CREATE_TASKS:
                logger.info(
                    "Task creation from emails is disabled",
                    extra={"data": {"email_id": email_id}}
                )
                return False
            
            # Extract email metadata
            metadata = self._extract_email_metadata(email_data)
            
            logger.info(
                "Processing email",
                extra={"data": {
                    "email_id": email_id,
                    "subject": metadata.subject[:100],
                    "sender": metadata.sender
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
            task_id = await self._create_task_from_email(email_data, metadata)
            
            if task_id:
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
    
    def _extract_email_metadata(self, email_data: Dict[str, Any]) -> EmailMetadata:
        """Extract metadata from email data."""
        headers = {}
        
        # Extract headers from email message format
        if "payload" in email_data and "headers" in email_data["payload"]:
            for header in email_data["payload"]["headers"]:
                headers[header["name"].lower()] = header["value"]
        
        # Parse date
        date_str = headers.get("date", "")
        try:
            # This is a simplified date parsing - in production you'd want more robust parsing
            email_date = datetime.utcnow()  # Fallback to current time
        except:
            email_date = datetime.utcnow()
        
        return EmailMetadata(
            email_id=email_data.get("id", ""),
            thread_id=email_data.get("threadId", ""),
            subject=headers.get("subject", "No Subject"),
            sender=headers.get("from", "Unknown Sender"),
            recipient=headers.get("to", ""),
            date=email_date,
            has_attachments=self._has_attachments(email_data),
            labels=email_data.get("labelIds", [])
        )
    
    def _has_attachments(self, email_data: Dict[str, Any]) -> bool:
        """Check if email has attachments."""
        if "payload" not in email_data:
            return False
        
        payload = email_data["payload"]
        
        # Check if there are parts with attachments
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("filename") and part["filename"].strip():
                    return True
        
        return False
    
    async def _create_task_from_email(
        self, 
        email_data: Dict[str, Any], 
        metadata: EmailMetadata
    ) -> Optional[str]:
        """Create a Nova task from email data."""
        try:
            # Extract email body
            email_body = self._extract_email_body(email_data)
            
            # Create task title
            task_title = f"Read Email: {metadata.subject}"
            
            # Create task description with email content
            task_description = self._format_task_description(metadata, email_body)
            
            # Use internal task creation function
            result_json = await create_task_tool(
                title=task_title,
                description=task_description,
                tags=["email"]  # Tag as email-generated task
            )
            
            # Parse the JSON result to extract task ID
            try:
                import json
                if "Task created successfully:" in result_json:
                    # Extract the JSON part after the prefix
                    json_part = result_json.split("Task created successfully:", 1)[1].strip()
                    task_data = json.loads(json_part)
                    task_id = task_data.get("id")
                    
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
                    else:
                        logger.error(
                            "Failed to extract task ID from result",
                            extra={"data": {
                                "email_id": metadata.email_id,
                                "result": result_json
                            }}
                        )
                        return None
                else:
                    logger.error(
                        "Task creation failed",
                        extra={"data": {
                            "email_id": metadata.email_id,
                            "result": result_json
                        }}
                    )
                    return None
                    
            except Exception as e:
                logger.error(
                    "Failed to parse task creation result",
                    extra={"data": {
                        "email_id": metadata.email_id,
                        "result": result_json,
                        "error": str(e)
                    }}
                )
                return None
                    
        except Exception as e:
            logger.error(
                "Failed to create task from email",
                extra={"data": {
                    "email_id": metadata.email_id,
                    "error": str(e)
                }}
            )
            raise
    
    def _extract_email_body(self, email_data: Dict[str, Any]) -> str:
        """Extract email body text."""
        if "payload" not in email_data:
            return "No content available"
        
        payload = email_data["payload"]
        
        # Try to get plain text first
        body_text = self._extract_text_from_payload(payload, "text/plain")
        
        # If no plain text, try HTML
        if not body_text:
            body_text = self._extract_text_from_payload(payload, "text/html")
        
        # If still no content, return fallback
        if not body_text:
            body_text = "Content could not be extracted"
        
        return body_text
    
    def _extract_text_from_payload(self, payload: Dict[str, Any], mime_type: str) -> str:
        """Extract text from email payload by MIME type."""
        # Check if this payload matches the desired MIME type
        if payload.get("mimeType") == mime_type:
            if "body" in payload and "data" in payload["body"]:
                try:
                    decoded = base64.urlsafe_b64decode(payload["body"]["data"])
                    return decoded.decode("utf-8")
                except Exception:
                    pass
        
        # Check parts recursively
        if "parts" in payload:
            for part in payload["parts"]:
                text = self._extract_text_from_payload(part, mime_type)
                if text:
                    return text
        
        return ""
    
    def _format_task_description(self, metadata: EmailMetadata, body: str) -> str:
        """Format task description with email metadata and content."""
        description_parts = [
            f"**From:** {metadata.sender}",
            f"**To:** {metadata.recipient}",
            f"**Date:** {metadata.date.strftime('%Y-%m-%d %H:%M:%S UTC')}",
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
    
    async def close(self):
        """Clean up resources."""
        # Clear cached tools to free memory
        self.mcp_tools = None
        logger.debug("Email processor resources cleaned up") 