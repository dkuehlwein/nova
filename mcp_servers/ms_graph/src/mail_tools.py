"""
Mail Tools - Email operations via MS Graph API.

Provides tools matching outlook-mac signatures for consistency.
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .service import MSGraphService

logger = logging.getLogger(__name__)


class MailTools:
    """Email operations via MS Graph API."""

    # Signature appended to all emails sent by Nova
    NOVA_EMAIL_SIGNATURE = "\n\n---\nThis email was sent by Nova, an AI assistant."

    def __init__(self, service: "MSGraphService"):
        """
        Initialize mail tools.

        Args:
            service: MSGraphService instance for API access
        """
        self.service = service

    async def list_emails(
        self,
        folder: str = "inbox",
        limit: int = 20,
        unread_only: bool = False,
        since_date: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        List emails from the specified folder.

        Args:
            folder: Folder name to list emails from (default: inbox)
            limit: Maximum number of emails to return (default: 20)
            unread_only: If True, only return unread emails
            since_date: Only return emails received on or after this date (format: YYYY-MM-DD)

        Returns:
            List of email summaries with id, subject, sender, date, read status
        """
        try:
            client = await self.service.ensure_client()

            # Build query parameters
            params = {
                "$top": limit,
                "$select": "id,subject,from,receivedDateTime,isRead,categories",
                "$orderby": "receivedDateTime desc",
            }

            # Build filter conditions
            filters = []
            if unread_only:
                filters.append("isRead eq false")
            if since_date:
                filters.append(f"receivedDateTime ge {since_date}T00:00:00Z")

            if filters:
                params["$filter"] = " and ".join(filters)

            # Map folder name to MS Graph folder path
            folder_path = self._get_folder_path(folder)

            response = await client.get(folder_path, params=params)
            response.raise_for_status()
            data = response.json()

            # Transform to match outlook-mac format
            results = []
            for msg in data.get("value", []):
                sender = msg.get("from", {}).get("emailAddress", {})
                results.append({
                    "id": msg["id"],
                    "subject": msg.get("subject") or "(No Subject)",
                    "sender_name": sender.get("name", "Unknown"),
                    "sender_email": sender.get("address", ""),
                    "date": msg.get("receivedDateTime", ""),
                    "is_read": msg.get("isRead", False),
                    "categories": msg.get("categories", []),
                })

            return results

        except Exception as e:
            logger.error(f"Error listing emails: {e}")
            return {"error": f"Failed to list emails: {str(e)}"}

    async def read_email(self, email_id: str) -> Dict[str, Any]:
        """
        Read the full content of an email by its ID.

        Args:
            email_id: The unique identifier of the email to read

        Returns:
            Full email content including subject, sender, recipients, date, and body
        """
        try:
            client = await self.service.ensure_client()

            # Get the email with full body
            response = await client.get(
                f"/me/messages/{email_id}",
                params={"$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,isRead,body,categories"}
            )
            response.raise_for_status()
            msg = response.json()

            # Mark as read if not already
            if not msg.get("isRead", False):
                await self._mark_as_read(email_id)

            # Extract sender info
            sender = msg.get("from", {}).get("emailAddress", {})

            # Extract recipients
            to_recipients = [
                r.get("emailAddress", {}).get("address", "")
                for r in msg.get("toRecipients", [])
            ]
            cc_recipients = [
                r.get("emailAddress", {}).get("address", "")
                for r in msg.get("ccRecipients", [])
            ]

            # Get body content (prefer text, fall back to HTML)
            body_data = msg.get("body", {})
            body_content = body_data.get("content", "")
            body_type = body_data.get("contentType", "text")

            return {
                "id": msg["id"],
                "subject": msg.get("subject") or "(No Subject)",
                "sender_name": sender.get("name", "Unknown"),
                "sender_email": sender.get("address", ""),
                "to": to_recipients,
                "cc": cc_recipients,
                "date": msg.get("receivedDateTime", ""),
                "body": body_content,
                "body_type": body_type,
                "is_read": True,  # We just marked it as read
                "categories": msg.get("categories", []),
            }

        except Exception as e:
            logger.error(f"Error reading email: {e}")
            return {"error": f"Failed to read email: {str(e)}"}

    async def create_draft(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a draft email. Does not send the email.

        NOTE: Requires Mail.ReadWrite permission which may need admin consent.

        Args:
            recipients: List of recipient email addresses
            subject: Email subject line
            body: Email body content (plain text)
            cc: Optional list of CC recipient email addresses

        Returns:
            Confirmation with draft ID
        """
        try:
            client = await self.service.ensure_client()

            # Append Nova signature
            signed_body = body + self.NOVA_EMAIL_SIGNATURE

            # Build message payload
            message = {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": signed_body,
                },
                "toRecipients": [
                    {"emailAddress": {"address": email}} for email in recipients
                ],
                "isDraft": True,
            }

            if cc:
                message["ccRecipients"] = [
                    {"emailAddress": {"address": email}} for email in cc
                ]

            # Create the draft (POST to /me/messages)
            response = await client.post("/me/messages", json=message)
            response.raise_for_status()
            draft = response.json()

            return {
                "status": "success",
                "message": f"Draft created with subject: {subject}",
                "draft_id": draft.get("id"),
                "recipients": recipients,
                "cc": cc or [],
            }

        except Exception as e:
            logger.error(f"Error creating draft: {e}")
            return {"error": f"Failed to create draft: {str(e)}"}

    async def send_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send an email directly. REQUIRES USER APPROVAL.

        NOTE: Requires Mail.Send permission which may need admin consent.

        This tool sends the email immediately without saving as draft first.
        Use create_draft if you want to prepare an email for user review before sending.

        Args:
            recipients: List of recipient email addresses
            subject: Email subject line
            body: Email body content (plain text)
            cc: Optional list of CC recipient email addresses

        Returns:
            Confirmation with send status
        """
        try:
            client = await self.service.ensure_client()

            # Append Nova signature
            signed_body = body + self.NOVA_EMAIL_SIGNATURE

            # Build sendMail payload
            payload = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "Text",
                        "content": signed_body,
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": email}} for email in recipients
                    ],
                },
                "saveToSentItems": True,
            }

            if cc:
                payload["message"]["ccRecipients"] = [
                    {"emailAddress": {"address": email}} for email in cc
                ]

            # Send the email
            response = await client.post("/me/sendMail", json=payload)
            response.raise_for_status()

            return {
                "status": "success",
                "message": f"Email sent to {', '.join(recipients)} with subject: {subject}",
                "recipients": recipients,
                "cc": cc or [],
                "subject": subject,
            }

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return {"error": f"Failed to send email: {str(e)}"}

    async def _mark_as_read(self, email_id: str) -> bool:
        """Mark an email as read."""
        try:
            client = await self.service.ensure_client()
            response = await client.patch(
                f"/me/messages/{email_id}",
                json={"isRead": True}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Could not mark email as read: {e}")
            return False

    def _get_folder_path(self, folder: str) -> str:
        """
        Map folder name to MS Graph API path.

        Args:
            folder: Folder name (inbox, drafts, sent, etc.)

        Returns:
            MS Graph API path for the folder
        """
        folder_lower = folder.lower()

        # Well-known folders
        well_known = {
            "inbox": "/me/mailFolders/inbox/messages",
            "drafts": "/me/mailFolders/drafts/messages",
            "sent": "/me/mailFolders/sentItems/messages",
            "sentitems": "/me/mailFolders/sentItems/messages",
            "deleted": "/me/mailFolders/deletedItems/messages",
            "deleteditems": "/me/mailFolders/deletedItems/messages",
            "archive": "/me/mailFolders/archive/messages",
            "junk": "/me/mailFolders/junkemail/messages",
            "junkemail": "/me/mailFolders/junkemail/messages",
        }

        if folder_lower in well_known:
            return well_known[folder_lower]

        # Default to inbox for unknown folders
        logger.warning(f"Unknown folder '{folder}', using inbox")
        return "/me/mailFolders/inbox/messages"
