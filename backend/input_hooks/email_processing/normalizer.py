"""
Email format normalization for Nova.

Handles conversion of various email formats (Gmail API, simplified MCP, etc.) 
to a unified internal format.
"""
import base64
from typing import Dict, Any
from utils.logging import get_logger

logger = get_logger(__name__)


class EmailNormalizer:
    """Normalizes various email formats to a unified structure."""
    
    def normalize(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize any email format to a unified structure.
        
        Handles:
        - Gmail API format (payload.headers, payload.parts)
        - Simplified MCP format (direct fields)
        - Any other email provider formats
        
        Returns a standardized email dict with: id, thread_id, subject, from, to, date, content, has_attachments, labels
        """
        # Detect format and extract accordingly
        if self._is_gmail_api_format(email_data):
            return self._normalize_gmail_format(email_data)
        else:
            return self._normalize_simple_format(email_data)
    
    def _is_gmail_api_format(self, email_data: Dict[str, Any]) -> bool:
        """Check if email data is in Gmail API format."""
        return "payload" in email_data and "headers" in email_data.get("payload", {})
    
    def _normalize_gmail_format(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Gmail API format to unified structure."""
        normalized = {}
        
        # Extract ID and thread ID from top level
        normalized["id"] = email_data.get("id", "")
        normalized["thread_id"] = email_data.get("threadId", "")
        normalized["labels"] = email_data.get("labelIds", [])
        
        # Extract headers from payload
        payload = email_data.get("payload", {})
        headers = {}
        for header in payload.get("headers", []):
            headers[header["name"].lower()] = header["value"]
        
        # Map standard email headers
        normalized["subject"] = headers.get("subject", "")
        normalized["from"] = headers.get("from", "")
        normalized["to"] = headers.get("to", "")
        normalized["date"] = headers.get("date", "")
        
        # Extract content and check attachments
        normalized["content"] = self._extract_gmail_content(payload)
        normalized["has_attachments"] = self._check_gmail_attachments(payload)
        
        return normalized
    
    def _normalize_simple_format(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize simplified/MCP format to unified structure."""
        # Direct field mapping for simplified formats
        field_mapping = {
            "id": ["id", "email_id", "message_id"],
            "thread_id": ["threadId", "thread_id"],
            "subject": ["subject"],
            "from": ["from", "sender"],
            "to": ["to", "recipient"],
            "date": ["date", "timestamp", "sent_at"],
            "content": ["content", "body", "text"],
            "labels": ["labelIds", "labels", "tags"]
        }
        
        normalized = {}
        for target_field, possible_sources in field_mapping.items():
            for source_field in possible_sources:
                if source_field in email_data and email_data[source_field]:
                    normalized[target_field] = email_data[source_field]
                    break
            
            # Set defaults for missing fields
            if target_field not in normalized:
                defaults = {
                    "id": "",
                    "thread_id": "",
                    "subject": "",
                    "from": "",
                    "to": "",
                    "date": "",
                    "content": "",
                    "labels": []
                }
                normalized[target_field] = defaults.get(target_field, "")
        
        # Simple formats rarely have attachments info
        normalized["has_attachments"] = False
        
        return normalized
    
    def _extract_gmail_content(self, payload: Dict[str, Any]) -> str:
        """Extract content from Gmail payload structure."""
        # Try to get plain text first
        content = self._extract_text_from_gmail_payload(payload, "text/plain")
        
        # If no plain text, try HTML
        if not content:
            content = self._extract_text_from_gmail_payload(payload, "text/html")
        
        # If still no content, return fallback
        return content if content else "Content could not be extracted"
    
    def _extract_text_from_gmail_payload(self, payload: Dict[str, Any], mime_type: str) -> str:
        """Extract text from Gmail payload by MIME type."""
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
                text = self._extract_text_from_gmail_payload(part, mime_type)
                if text:
                    return text
        
        return ""
    
    def _check_gmail_attachments(self, payload: Dict[str, Any]) -> bool:
        """Check if Gmail payload has attachments."""
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("filename") and part["filename"].strip():
                    return True
        return False