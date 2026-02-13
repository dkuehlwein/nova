"""
Gmail tools for Google Workspace MCP Server.
Contains all Gmail-related functionality for email operations.
"""

import asyncio
import base64
import webbrowser
from base64 import urlsafe_b64decode
from email import message_from_bytes
from email.message import EmailMessage
from typing import List, Dict, Union, Optional, Any
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)

def decode_mime_header(header: str) -> str:
    """Decodes MIME-encoded header values."""
    from email.header import decode_header
    decoded_pieces = decode_header(header)
    return ''.join([
        piece.decode(encoding or 'utf-8') if isinstance(piece, bytes) else piece
        for piece, encoding in decoded_pieces
    ])

class GmailTools:
    """Gmail tools for the Google Workspace MCP server."""
    
    def __init__(self, gmail_service, user_email: str):
        self.gmail_service = gmail_service
        self.user_email = user_email
    
    async def send_email(self, recipients: List[str], subject: str, body: str) -> dict:
        try:
            message_obj = EmailMessage()
            message_obj.set_content(body)
            message_obj['To'] = ", ".join(recipients)
            message_obj['From'] = self.user_email
            message_obj['Subject'] = subject
            encoded_message = base64.urlsafe_b64encode(message_obj.as_bytes()).decode()
            create_message = {'raw': encoded_message}
            send_message = await asyncio.to_thread(
                self.gmail_service.users().messages().send(userId="me", body=create_message).execute
            )
            logger.info(f"Message sent: {send_message['id']}")
            return {"message_id": send_message["id"]}
        except HttpError as error:
            logger.error(f"Error sending email: {error}")
            return {"status": "error", "error_message": str(error)}

    async def open_email(self, email_id: str) -> str:
        try:
            url = f"https://mail.google.com/#all/{email_id}"
            # webbrowser.open is blocking, run in thread if truly async needed
            # For a server, opening a browser on the server machine is usually not desired.
            # This tool might need rethinking for a server context.
            # For now, let's assume it's a local server for a single user.
            await asyncio.to_thread(webbrowser.open, url, new=0, autoraise=True)
            return f"Attempted to open email {email_id} in browser."
        except Exception as e: # Catch generic exception for webbrowser
            logger.error(f"Error opening email in browser: {e}")
            return {"status": "error", "error_message": f"An error occurred opening email in browser: {str(e)}"}

    async def get_unread_emails(self) -> Union[List[Dict[str, str]], Dict[str, str]]:
        try:
            user_id = 'me'
            query = 'in:inbox is:unread category:primary'
            response = await asyncio.to_thread(
                self.gmail_service.users().messages().list(userId=user_id, q=query).execute
            )
            messages = []
            if 'messages' in response:
                messages.extend(response['messages'])
            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = await asyncio.to_thread(
                    self.gmail_service.users().messages().list(userId=user_id, q=query, pageToken=page_token).execute
                )
                if 'messages' in response:
                    messages.extend(response['messages'])
            return messages
        except HttpError as error:
            logger.error(f"Error getting unread emails: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred: {str(error)}"}

    async def read_email(self, email_id: str) -> Union[Dict[str, str], Dict[str, str]]:
        try:
            msg = await asyncio.to_thread(
                self.gmail_service.users().messages().get(userId="me", id=email_id, format='raw').execute
            )
            email_metadata = {}
            raw_data = msg['raw']
            decoded_data = urlsafe_b64decode(raw_data)
            mime_message = message_from_bytes(decoded_data)
            body = None
            if mime_message.is_multipart():
                for part in mime_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                        break
            else:
                body = mime_message.get_payload(decode=True).decode(mime_message.get_content_charset() or 'utf-8')
            email_metadata['id'] = email_id  # Preserve original Gmail message ID
            email_metadata['content'] = body
            email_metadata['subject'] = decode_mime_header(mime_message.get('subject', ''))
            email_metadata['from'] = decode_mime_header(mime_message.get('from', '')) # decode from
            email_metadata['to'] = decode_mime_header(mime_message.get('to', '')) # decode to
            email_metadata['date'] = mime_message.get('date', '')
            logger.info(f"Email read: {email_id}")
            await self.mark_email_as_read(email_id)
            return email_metadata
        except HttpError as error:
            logger.error(f"Error reading email {email_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred reading email {email_id}: {str(error)}"}

    async def trash_email(self, email_id: str) -> Union[str, Dict[str, str]]:
        try:
            await asyncio.to_thread(
                self.gmail_service.users().messages().trash(userId="me", id=email_id).execute
            )
            logger.info(f"Email moved to trash: {email_id}")
            return "Email moved to trash successfully."
        except HttpError as error:
            logger.error(f"Error trashing email {email_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred trashing email {email_id}: {str(error)}"}

    async def mark_email_as_read(self, email_id: str) -> Union[str, Dict[str, str]]:
        try:
            await asyncio.to_thread(
                self.gmail_service.users().messages().modify(userId="me", id=email_id, body={'removeLabelIds': ['UNREAD']}).execute
            )
            logger.info(f"Email marked as read: {email_id}")
            return "Email marked as read."
        except HttpError as error:
            logger.error(f"Error marking email {email_id} as read: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred marking email {email_id} as read: {str(error)}"}

    async def create_draft(self, recipients: List[str], subject: str, body: str) -> Dict[str, str]:
        try:
            message_obj = EmailMessage()
            message_obj.set_content(body)
            message_obj['To'] = ", ".join(recipients)
            message_obj['From'] = self.user_email
            message_obj['Subject'] = subject
            encoded_message = base64.urlsafe_b64encode(message_obj.as_bytes()).decode()
            create_message = {'message': {'raw': encoded_message}} # Gmail API expects 'message' key for draft
            draft = await asyncio.to_thread(
                self.gmail_service.users().drafts().create(userId="me", body=create_message).execute
            )
            logger.info(f"Draft created: {draft['id']}")
            return {"draft_id": draft["id"]}
        except HttpError as error:
            logger.error(f"Error creating draft: {error}")
            return {"status": "error", "error_message": str(error)}

    async def list_drafts(self) -> Union[List[Dict[str, str]], Dict[str, str]]:
        try:
            results = await asyncio.to_thread(
                self.gmail_service.users().drafts().list(userId="me").execute
            )
            drafts_info = results.get('drafts', [])
            draft_list = []
            for draft_summary in drafts_info:
                draft_id = draft_summary['id']
                draft_data = await asyncio.to_thread(
                    self.gmail_service.users().drafts().get(userId="me", id=draft_id, format='metadata').execute
                )
                message = draft_data.get('message', {})
                headers = message.get('payload', {}).get('headers', [])
                subject = next((decode_mime_header(h['value']) for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                to = next((decode_mime_header(h['value']) for h in headers if h['name'].lower() == 'to'), 'No Recipient')
                draft_list.append({'id': draft_id, 'subject': subject, 'to': to})
            return draft_list
        except HttpError as error:
            logger.error(f"Error listing drafts: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred listing drafts: {str(error)}"}

    async def list_labels(self) -> Union[List[Dict[str, str]], Dict[str, str]]:
        try:
            results = await asyncio.to_thread(
                self.gmail_service.users().labels().list(userId="me").execute
            )
            return results.get('labels', [])
        except HttpError as error:
            logger.error(f"Error listing labels: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred listing labels: {str(error)}"}

    async def create_label(self, name: str) -> Dict[str, str]:
        try:
            label_object = {'name': name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
            created_label = await asyncio.to_thread(
                self.gmail_service.users().labels().create(userId="me", body=label_object).execute
            )
            logger.info(f"Label created: {created_label['id']}")
            return {'label_id': created_label['id'], 'name': created_label['name']}
        except HttpError as error:
            logger.error(f"Error creating label '{name}': {error}")
            return {"status": "error", "error_message": str(error)}

    async def apply_label(self, email_id: str, label_id: str) -> Union[str, Dict[str, str]]:
        try:
            await asyncio.to_thread(
                self.gmail_service.users().messages().modify(userId="me", id=email_id, body={'addLabelIds': [label_id]}).execute
            )
            logger.info(f"Label {label_id} applied to email {email_id}")
            return f"Label {label_id} applied successfully to email {email_id}."
        except HttpError as error:
            logger.error(f"Error applying label {label_id} to email {email_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred applying label: {str(error)}"}

    async def remove_label(self, email_id: str, label_id: str) -> Union[str, Dict[str, str]]:
        try:
            await asyncio.to_thread(
                self.gmail_service.users().messages().modify(userId="me", id=email_id, body={'removeLabelIds': [label_id]}).execute
            )
            logger.info(f"Label {label_id} removed from email {email_id}")
            return f"Label {label_id} removed successfully from email {email_id}."
        except HttpError as error:
            logger.error(f"Error removing label {label_id} from email {email_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred removing label: {str(error)}"}

    async def rename_label(self, label_id: str, new_name: str) -> Dict[str, str]:
        try:
            label_patch = {'name': new_name} # Only send fields to update for patch
            updated_label = await asyncio.to_thread(
                self.gmail_service.users().labels().patch(userId="me", id=label_id, body=label_patch).execute
            )
            logger.info(f"Label renamed: {label_id} to {new_name}")
            return {'label_id': updated_label['id'], 'name': updated_label['name']}
        except HttpError as error:
            logger.error(f"Error renaming label {label_id} to '{new_name}': {error}")
            return {"status": "error", "error_message": str(error)}

    async def delete_label(self, label_id: str) -> Union[str, Dict[str, str]]:
        try:
            await asyncio.to_thread(
                self.gmail_service.users().labels().delete(userId="me", id=label_id).execute
            )
            logger.info(f"Label deleted: {label_id}")
            return f"Label {label_id} deleted successfully."
        except HttpError as error:
            logger.error(f"Error deleting label {label_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred deleting label: {str(error)}"}

    async def search_by_label(self, label_id: str) -> Union[List[Dict[str, str]], Dict[str, str]]:
        try:
            query = f"label:{label_id}"
            response = await asyncio.to_thread(
                self.gmail_service.users().messages().list(userId="me", q=query).execute
            )
            messages = []
            if 'messages' in response:
                messages.extend(response['messages'])
            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = await asyncio.to_thread(
                    self.gmail_service.users().messages().list(userId="me", q=query, pageToken=page_token).execute
                )
                if 'messages' in response:
                    messages.extend(response['messages'])
            return messages
        except HttpError as error:
            logger.error(f"Error searching emails by label {label_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred searching by label: {str(error)}"}

    async def list_filters(self) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        try:
            results = await asyncio.to_thread(
                self.gmail_service.users().settings().filters().list(userId="me").execute
            )
            return results.get('filter', []) # API uses 'filter' not 'filters'
        except HttpError as error:
            logger.error(f"Error listing filters: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred listing filters: {str(error)}"}

    async def get_filter(self, filter_id: str) -> Union[Dict[str, Any], Dict[str, str]]:
        try:
            return await asyncio.to_thread(
                self.gmail_service.users().settings().filters().get(userId="me", id=filter_id).execute
            )
        except HttpError as error:
            logger.error(f"Error getting filter {filter_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred getting filter: {str(error)}"}

    async def create_filter(self,
                          from_email: Optional[str] = None, to_email: Optional[str] = None,
                          subject: Optional[str] = None, query: Optional[str] = None,
                          has_attachment: Optional[bool] = None, exclude_chats: Optional[bool] = None,
                          size_comparison: Optional[str] = None, size: Optional[int] = None,
                          add_label_ids: Optional[List[str]] = None, remove_label_ids: Optional[List[str]] = None,
                          forward_to: Optional[str] = None) -> Dict[str, Any]:
        try:
            criteria = {}
            if from_email:
                criteria['from'] = from_email
            if to_email:
                criteria['to'] = to_email
            if subject:
                criteria['subject'] = subject
            if query:
                criteria['query'] = query
            if has_attachment is not None:
                criteria['hasAttachment'] = has_attachment
            if exclude_chats is not None:
                criteria['excludeChats'] = exclude_chats
            if size_comparison and size:
                criteria['sizeComparison'] = size_comparison
                criteria['size'] = size

            action = {}
            if add_label_ids:
                action['addLabelIds'] = add_label_ids
            if remove_label_ids:
                action['removeLabelIds'] = remove_label_ids
            if forward_to:
                action['forward'] = forward_to

            filter_object = {'criteria': criteria, 'action': action}
            created_filter = await asyncio.to_thread(
                self.gmail_service.users().settings().filters().create(userId="me", body=filter_object).execute
            )
            logger.info(f"Filter created: {created_filter['id']}")
            return created_filter
        except HttpError as error:
            logger.error(f"Error creating filter: {error}")
            return {"status": "error", "error_message": str(error)}

    async def delete_filter(self, filter_id: str) -> Union[str, Dict[str, str]]:
        try:
            await asyncio.to_thread(
                self.gmail_service.users().settings().filters().delete(userId="me", id=filter_id).execute
            )
            logger.info(f"Filter deleted: {filter_id}")
            return f"Filter {filter_id} deleted successfully."
        except HttpError as error:
            logger.error(f"Error deleting filter {filter_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred deleting filter: {str(error)}"}

    async def search_emails(self, query: str, max_results: int = 50) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        try:
            user_id = 'me'
            all_messages_summary = []
            page_token = None
            remaining_results = max_results

            while remaining_results > 0:
                
                response = await asyncio.to_thread(
                    self.gmail_service.users().messages().list(
                        userId=user_id, q=query, maxResults=min(remaining_results, 100), # API max is often 100 or 500
                        pageToken=page_token
                    ).execute
                )
                
                messages = response.get('messages', [])
                all_messages_summary.extend(messages)
                remaining_results -= len(messages)
                
                if 'nextPageToken' not in response or len(messages) == 0:
                    break
                page_token = response['nextPageToken']
            
            # Get basic details for each message
            detailed_messages = []
            for msg_summary in all_messages_summary:
                msg_data = await asyncio.to_thread(
                    self.gmail_service.users().messages().get(
                        userId=user_id, id=msg_summary['id'], format='metadata',
                        metadataHeaders=['Subject', 'From', 'Date']
                    ).execute
                )
                
                headers = msg_data.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                from_addr = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                date = next((h['value'] for h in headers if h['name'].lower() == 'date'), 'Unknown Date')
                
                detailed_messages.append({
                    'id': msg_summary['id'],
                    'threadId': msg_data.get('threadId', ''),
                    'subject': subject,
                    'from': from_addr,
                    'date': date,
                    'snippet': msg_data.get('snippet', '')
                })
            
            return detailed_messages
        except HttpError as error:
            logger.error(f"Error searching emails with query '{query}': {error}")
            return {"status": "error", "error_message": f"An HttpError occurred searching emails: {str(error)}"}

    # Folder operations (Gmail uses labels as folders)
    async def create_folder(self, name: str) -> Dict[str, str]: # Return type matches create_label
        # In Gmail, folders are essentially labels.
        return await self.create_label(name)

    async def move_to_folder(self, email_id: str, folder_id: str) -> Union[str, Dict[str, str]]:
        try:
            # Apply the folder label and remove from inbox
            await asyncio.to_thread(
                self.gmail_service.users().messages().modify(
                    userId="me", id=email_id, body={'addLabelIds': [folder_id], 'removeLabelIds': ['INBOX']}
                ).execute
            )
            logger.info(f"Email {email_id} moved to folder {folder_id}")
            return f"Email moved to folder {folder_id} successfully."
        except HttpError as error:
            logger.error(f"Error moving email {email_id} to folder {folder_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred moving email to folder: {str(error)}"}

    async def list_folders(self) -> Union[List[Dict[str, str]], Dict[str, str]]:
        try:
            all_labels = await self.list_labels()
            if isinstance(all_labels, dict) and 'status' in all_labels:
                return all_labels # Error from list_labels
            
            # Filter for user-created labels (folders)
            folders = [label for label in all_labels if not label.get('type') == 'system']
            return folders
        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return {"status": "error", "error_message": f"An error occurred listing folders: {str(e)}"}

    async def archive_email(self, email_id: str) -> Union[str, Dict[str, str]]:
        try:
            await asyncio.to_thread(
                self.gmail_service.users().messages().modify(userId="me", id=email_id, body={'removeLabelIds': ['INBOX']}).execute
            )
            logger.info(f"Email archived: {email_id}")
            return f"Email {email_id} archived successfully."
        except HttpError as error:
            logger.error(f"Error archiving email {email_id}: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred archiving email: {str(error)}"}

    async def batch_archive(self, query: str, max_emails: int = 100) -> Dict[str, Any]:
        try:
            user_id = 'me'
            messages_to_archive_ids = []
            page_token = None
            
            while len(messages_to_archive_ids) < max_emails:
                response = await asyncio.to_thread(
                    self.gmail_service.users().messages().list(
                        userId=user_id, q=query + " is:inboxed", # only archive what's in inbox
                        maxResults=min(max_emails - len(messages_to_archive_ids), 100),
                        pageToken=page_token
                    ).execute
                )
                
                messages = response.get('messages', [])
                messages_to_archive_ids.extend([msg['id'] for msg in messages])
                
                if 'nextPageToken' not in response or len(messages) == 0:
                    break
                page_token = response['nextPageToken']
            
            # Limit to the exact number requested
            messages_to_archive_ids = messages_to_archive_ids[:max_emails]
            
            if not messages_to_archive_ids:
                return {"archived_count": 0, "message": "No emails found matching the query."}
            
            # Batch modify to remove INBOX label
            batch_modify_request_body = {
                "ids": messages_to_archive_ids,
                "removeLabelIds": ["INBOX"]
            }
            await asyncio.to_thread(
                 self.gmail_service.users().messages().batchModify(userId="me", body=batch_modify_request_body).execute
            )
            archived_count = len(messages_to_archive_ids)
            logger.info(f"Batch archived {archived_count} emails")
            return {"archived_count": archived_count, "message": f"Successfully archived {archived_count} emails."}
        except HttpError as error:
            logger.error(f"Error batch archiving emails with query '{query}': {error}")
            return {"status": "error", "error_message": f"An HttpError occurred batch archiving: {str(error)}"}

    async def list_archived(self, max_results: int = 50) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        # Archived emails are those not in inbox but not in trash
        query = "-in:inbox -in:trash"
        return await self.search_emails(query, max_results)

    async def restore_to_inbox(self, email_id: str) -> Union[str, Dict[str, str]]:
        try:
            await asyncio.to_thread(
                self.gmail_service.users().messages().modify(userId="me", id=email_id, body={'addLabelIds': ['INBOX']}).execute
            )
            logger.info(f"Email restored to inbox: {email_id}")
            return f"Email {email_id} restored to inbox successfully."
        except HttpError as error:
            logger.error(f"Error restoring email {email_id} to inbox: {error}")
            return {"status": "error", "error_message": f"An HttpError occurred restoring email: {str(error)}"} 