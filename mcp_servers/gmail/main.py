from typing import Any, List, Dict, Optional, Union 
import argparse
import os
import asyncio
import logging
import base64
from email.message import EmailMessage
from email.header import decode_header
from base64 import urlsafe_b64decode
from email import message_from_bytes
import webbrowser
from datetime import datetime

from fastmcp import FastMCP 

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- GmailService Class (largely unchanged, ensure async for tool calls) ---
def decode_mime_header(header: str) -> str:
    """Helper function to decode encoded email headers"""
    decoded_parts = decode_header(header)
    decoded_string = ''
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_string += part.decode(encoding or 'utf-8')
        else:
            decoded_string += part
    return decoded_string

class GmailService:
    def __init__(self,
                 creds_file_path: str,
                 token_path: str,
                 scopes: list[str] = None,
                 oauth_port: int = 9000): # Default scopes handled in _get_token
        logger.info(f"Initializing GmailService with creds file: {creds_file_path}")
        self.creds_file_path = creds_file_path
        self.token_path = token_path
        self.scopes = scopes if scopes is not None else ['https://www.googleapis.com/auth/gmail.modify']
        self.oauth_port = oauth_port
        self.token = self._get_token()
        logger.info("Token retrieved successfully")
        self.service = self._get_service()
        logger.info("Gmail service initialized")
        self.user_email = self._get_user_email()
        logger.info(f"User email retrieved: {self.user_email}")

    def _get_token(self) -> Credentials:
        token = None
        if os.path.exists(self.token_path):
            logger.info('Loading token from file')
            token = Credentials.from_authorized_user_file(self.token_path, self.scopes)
        if not token or not token.valid:
            if token and token.expired and token.refresh_token:
                logger.info('Refreshing token')
                token.refresh(Request())
            else:
                logger.info('Fetching new token')
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_file_path, self.scopes)
                
                # Get WSL2 IP for troubleshooting
                import subprocess
                try:
                    wsl_ip = subprocess.check_output(
                        ["hostname", "-I"], text=True
                    ).strip().split()[0]
                    logger.info(f"WSL2 IP detected: {wsl_ip}")
                except Exception:
                    wsl_ip = "Unable to detect"
                
                try:
                    # Try with the specified OAuth port
                    logger.info(f'Attempting OAuth flow on port {self.oauth_port}')
                    logger.info(f'OAuth callback URL will be: http://localhost:{self.oauth_port}/')
                    logger.info('If this fails in WSL2, try these solutions:')
                    logger.info('1. From Windows PowerShell (as Admin): wsl --shutdown')
                    logger.info('2. Restart your WSL2 instance')
                    logger.info(f'3. Try opening: http://{wsl_ip}:{self.oauth_port}/ instead of localhost')
                    logger.info('4. Check Windows Firewall settings')
                    logger.info('5. Consider disabling IP Helper service temporarily')
                    
                    token = flow.run_local_server(port=self.oauth_port)
                except Exception as e:
                    logger.error(f'OAuth flow failed on port {self.oauth_port}: {e}')
                    logger.error('WSL2 Networking Troubleshooting:')
                    logger.error('=' * 50)
                    logger.error('This is a common WSL2 networking issue. Try these solutions:')
                    logger.error('')
                    logger.error('SOLUTION 1 - Restart WSL2:')
                    logger.error('  From Windows PowerShell (as Administrator):')
                    logger.error('  > wsl --shutdown')
                    logger.error('  Then restart your WSL2 terminal')
                    logger.error('')
                    logger.error('SOLUTION 2 - Use WSL2 IP address:')
                    logger.error(f'  Instead of localhost:{self.oauth_port}, try:')
                    logger.error(f'  http://{wsl_ip}:{self.oauth_port}/')
                    logger.error('')
                    logger.error('SOLUTION 3 - Windows Firewall:')
                    logger.error('  From Windows PowerShell (as Administrator):')
                    logger.error('  > New-NetFirewallRule -DisplayName "WSL" -Direction Inbound -InterfaceAlias "vEthernet (WSL)" -Action Allow')
                    logger.error('')
                    logger.error('SOLUTION 4 - Disable IP Helper (temporary):')
                    logger.error('  1. Open Services.msc in Windows')
                    logger.error('  2. Find "IP Helper" service')
                    logger.error('  3. Stop and disable it temporarily')
                    logger.error('  4. Reboot Windows')
                    logger.error('')
                    raise ValueError(f'OAuth flow failed. See troubleshooting steps above. Error: {e}')
            with open(self.token_path, 'w') as token_file:
                token_file.write(token.to_json())
                logger.info(f'Token saved to {self.token_path}')
        return token

    def _get_service(self) -> Any:
        try:
            service = build('gmail', 'v1', credentials=self.token)
            return service
        except HttpError as error:
            logger.error(f'An error occurred building Gmail service: {error}')
            raise ValueError(f'An error occurred building Gmail service: {error}')

    def _get_user_email(self) -> str:
        profile = self.service.users().getProfile(userId='me').execute()
        return profile.get('emailAddress', '')

    async def send_email(self, recipient_id: str, subject: str, message: str) -> dict:
        try:
            message_obj = EmailMessage()
            message_obj.set_content(message)
            message_obj['To'] = recipient_id
            message_obj['From'] = self.user_email
            message_obj['Subject'] = subject
            encoded_message = base64.urlsafe_b64encode(message_obj.as_bytes()).decode()
            create_message = {'raw': encoded_message}
            send_message = await asyncio.to_thread(
                self.service.users().messages().send(userId="me", body=create_message).execute
            )
            logger.info(f"Message sent: {send_message['id']}")
            return {"status": "success", "message_id": send_message["id"]}
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
            return f"An error occurred opening email in browser: {str(e)}"

    async def get_unread_emails(self) -> Union[List[Dict[str, str]], str]:
        try:
            user_id = 'me'
            query = 'in:inbox is:unread category:primary'
            response = await asyncio.to_thread(
                self.service.users().messages().list(userId=user_id, q=query).execute
            )
            messages = []
            if 'messages' in response:
                messages.extend(response['messages'])
            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = await asyncio.to_thread(
                    self.service.users().messages().list(userId=user_id, q=query, pageToken=page_token).execute
                )
                if 'messages' in response: # check again for messages key
                    messages.extend(response['messages'])
            return messages
        except HttpError as error:
            logger.error(f"Error getting unread emails: {error}")
            return f"An HttpError occurred: {str(error)}"

    async def read_email(self, email_id: str) -> Union[Dict[str, str], str]:
        try:
            msg = await asyncio.to_thread(
                self.service.users().messages().get(userId="me", id=email_id, format='raw').execute
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
            return f"An HttpError occurred reading email {email_id}: {str(error)}"

    async def trash_email(self, email_id: str) -> str:
        try:
            await asyncio.to_thread(
                self.service.users().messages().trash(userId="me", id=email_id).execute
            )
            logger.info(f"Email moved to trash: {email_id}")
            return "Email moved to trash successfully."
        except HttpError as error:
            logger.error(f"Error trashing email {email_id}: {error}")
            return f"An HttpError occurred trashing email {email_id}: {str(error)}"

    async def mark_email_as_read(self, email_id: str) -> str:
        try:
            await asyncio.to_thread(
                self.service.users().messages().modify(userId="me", id=email_id, body={'removeLabelIds': ['UNREAD']}).execute
            )
            logger.info(f"Email marked as read: {email_id}")
            return "Email marked as read."
        except HttpError as error:
            logger.error(f"Error marking email {email_id} as read: {error}")
            return f"An HttpError occurred marking email {email_id} as read: {str(error)}"

    async def create_draft(self, recipient_id: str, subject: str, message: str) -> dict:
        try:
            message_obj = EmailMessage()
            message_obj.set_content(message)
            message_obj['To'] = recipient_id
            message_obj['From'] = self.user_email
            message_obj['Subject'] = subject
            encoded_message = base64.urlsafe_b64encode(message_obj.as_bytes()).decode()
            create_message = {'message': {'raw': encoded_message}} # Gmail API expects 'message' key for draft
            draft = await asyncio.to_thread(
                self.service.users().drafts().create(userId="me", body=create_message).execute
            )
            logger.info(f"Draft created: {draft['id']}")
            return {"status": "success", "draft_id": draft["id"]}
        except HttpError as error:
            logger.error(f"Error creating draft: {error}")
            return {"status": "error", "error_message": str(error)}

    async def list_drafts(self) -> Union[List[Dict[str, str]], str]:
        try:
            results = await asyncio.to_thread(
                self.service.users().drafts().list(userId="me").execute
            )
            drafts_info = results.get('drafts', [])
            draft_list = []
            for draft_summary in drafts_info:
                draft_id = draft_summary['id']
                draft_data = await asyncio.to_thread(
                    self.service.users().drafts().get(userId="me", id=draft_id, format='metadata').execute
                )
                message = draft_data.get('message', {})
                headers = message.get('payload', {}).get('headers', [])
                subject = next((decode_mime_header(h['value']) for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                to = next((decode_mime_header(h['value']) for h in headers if h['name'].lower() == 'to'), 'No Recipient')
                draft_list.append({'id': draft_id, 'subject': subject, 'to': to})
            return draft_list
        except HttpError as error:
            logger.error(f"Error listing drafts: {error}")
            return f"An HttpError occurred listing drafts: {str(error)}"

    async def list_labels(self) -> Union[List[Dict[str, str]], str]:
        try:
            results = await asyncio.to_thread(
                self.service.users().labels().list(userId="me").execute
            )
            return results.get('labels', [])
        except HttpError as error:
            logger.error(f"Error listing labels: {error}")
            return f"An HttpError occurred listing labels: {str(error)}"

    async def create_label(self, name: str) -> dict:
        try:
            label_object = {'name': name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
            created_label = await asyncio.to_thread(
                self.service.users().labels().create(userId="me", body=label_object).execute
            )
            logger.info(f"Label created: {created_label['id']}")
            return {'status': 'success', 'label_id': created_label['id'], 'name': created_label['name']}
        except HttpError as error:
            logger.error(f"Error creating label '{name}': {error}")
            return {"status": "error", "error_message": str(error)}

    async def apply_label(self, email_id: str, label_id: str) -> str:
        try:
            await asyncio.to_thread(
                self.service.users().messages().modify(userId="me", id=email_id, body={'addLabelIds': [label_id]}).execute
            )
            logger.info(f"Label {label_id} applied to email {email_id}")
            return f"Label {label_id} applied successfully to email {email_id}."
        except HttpError as error:
            logger.error(f"Error applying label {label_id} to email {email_id}: {error}")
            return f"An HttpError occurred applying label: {str(error)}"

    async def remove_label(self, email_id: str, label_id: str) -> str:
        try:
            await asyncio.to_thread(
                self.service.users().messages().modify(userId="me", id=email_id, body={'removeLabelIds': [label_id]}).execute
            )
            logger.info(f"Label {label_id} removed from email {email_id}")
            return f"Label {label_id} removed successfully from email {email_id}."
        except HttpError as error:
            logger.error(f"Error removing label {label_id} from email {email_id}: {error}")
            return f"An HttpError occurred removing label: {str(error)}"

    async def rename_label(self, label_id: str, new_name: str) -> dict:
        try:
            label_patch = {'name': new_name} # Only send fields to update for patch
            updated_label = await asyncio.to_thread(
                self.service.users().labels().patch(userId="me", id=label_id, body=label_patch).execute
            )
            logger.info(f"Label renamed: {label_id} to {new_name}")
            return {'status': 'success', 'label_id': updated_label['id'], 'name': updated_label['name']}
        except HttpError as error:
            logger.error(f"Error renaming label {label_id} to '{new_name}': {error}")
            return {"status": "error", "error_message": str(error)}

    async def delete_label(self, label_id: str) -> str:
        try:
            await asyncio.to_thread(
                self.service.users().labels().delete(userId="me", id=label_id).execute
            )
            logger.info(f"Label deleted: {label_id}")
            return f"Label {label_id} deleted successfully."
        except HttpError as error:
            logger.error(f"Error deleting label {label_id}: {error}")
            return f"An HttpError occurred deleting label {label_id}: {str(error)}"

    async def search_by_label(self, label_id: str) -> Union[List[Dict[str, str]], str]:
        try:
            query = f"label:{label_id}"
            response = await asyncio.to_thread(
                self.service.users().messages().list(userId="me", q=query).execute
            )
            messages = []
            if 'messages' in response:
                messages.extend(response['messages'])
            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = await asyncio.to_thread(
                    self.service.users().messages().list(userId="me", q=query, pageToken=page_token).execute
                )
                if 'messages' in response:
                     messages.extend(response['messages'])
            return messages
        except HttpError as error:
            logger.error(f"Error searching by label {label_id}: {error}")
            return f"An HttpError occurred searching by label {label_id}: {str(error)}"

    async def list_filters(self) -> Union[List[Dict[str, Any]], str]:
        try:
            results = await asyncio.to_thread(
                self.service.users().settings().filters().list(userId="me").execute
            )
            return results.get('filter', []) # API uses 'filter' not 'filters'
        except HttpError as error:
            logger.error(f"Error listing filters: {error}")
            return f"An HttpError occurred listing filters: {str(error)}"

    async def get_filter(self, filter_id: str) -> Union[Dict[str, Any], str]:
        try:
            return await asyncio.to_thread(
                self.service.users().settings().filters().get(userId="me", id=filter_id).execute
            )
        except HttpError as error:
            logger.error(f"Error getting filter {filter_id}: {error}")
            return f"An HttpError occurred getting filter {filter_id}: {str(error)}"

    async def create_filter(self,
                           from_email: Optional[str] = None, to_email: Optional[str] = None,
                           subject: Optional[str] = None, query: Optional[str] = None,
                           has_attachment: Optional[bool] = None, exclude_chats: Optional[bool] = None,
                           size_comparison: Optional[str] = None, size: Optional[int] = None,
                           add_label_ids: Optional[List[str]] = None, remove_label_ids: Optional[List[str]] = None,
                           forward_to: Optional[str] = None) -> dict:
        try:
            criteria = {k: v for k, v in {
                'from': from_email, 'to': to_email, 'subject': subject, 'query': query,
                'hasAttachment': has_attachment, 'excludeChats': exclude_chats,
                'sizeComparison': size_comparison, 'size': size
            }.items() if v is not None}
            action = {k: v for k, v in {
                'addLabelIds': add_label_ids, 'removeLabelIds': remove_label_ids, 'forward': forward_to
            }.items() if v is not None}
            if not criteria or not action: # Filter must have criteria and action
                 return {"status": "error", "error_message": "Filter must have both criteria and action."}

            filter_object = {'criteria': criteria, 'action': action}
            created_filter = await asyncio.to_thread(
                self.service.users().settings().filters().create(userId="me", body=filter_object).execute
            )
            logger.info(f"Filter created: {created_filter['id']}")
            return {'status': 'success', 'filter_id': created_filter['id'], 'filter': created_filter}
        except HttpError as error:
            logger.error(f"Error creating filter: {error}")
            return {"status": "error", "error_message": str(error)}

    async def delete_filter(self, filter_id: str) -> str:
        try:
            await asyncio.to_thread(
                self.service.users().settings().filters().delete(userId="me", id=filter_id).execute
            )
            logger.info(f"Filter deleted: {filter_id}")
            return f"Filter {filter_id} deleted successfully."
        except HttpError as error:
            logger.error(f"Error deleting filter {filter_id}: {error}")
            return f"An HttpError occurred deleting filter {filter_id}: {str(error)}"

    async def search_emails(self, query: str, max_results: int = 50) -> Union[List[Dict[str, Any]], str]:
        try:
            user_id = 'me'
            all_messages_summary = []
            page_token = None
            while True:
                remaining_results = max_results - len(all_messages_summary)
                if remaining_results <= 0:
                    break
                
                response = await asyncio.to_thread(
                    self.service.users().messages().list(
                        userId=user_id, q=query, maxResults=min(remaining_results, 100), # API max is often 100 or 500
                        pageToken=page_token
                    ).execute
                )
                if 'messages' in response:
                    all_messages_summary.extend(response['messages'])
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            result_messages = []
            for msg_summary in all_messages_summary:
                msg_data = await asyncio.to_thread(
                    self.service.users().messages().get(
                        userId=user_id, id=msg_summary['id'], format='metadata',
                        metadataHeaders=['Subject', 'From', 'Date']
                    ).execute
                )
                headers = msg_data.get('payload', {}).get('headers', [])
                subject = next((decode_mime_header(h['value']) for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                sender = next((decode_mime_header(h['value']) for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
                result_messages.append({
                    'id': msg_summary['id'], 'threadId': msg_summary.get('threadId'),
                    'subject': subject, 'from': sender, 'date': date,
                    'snippet': msg_data.get('snippet', '')
                })
            return result_messages
        except HttpError as error:
            logger.error(f"Error searching emails with query '{query}': {error}")
            return f"An HttpError occurred searching emails: {str(error)}"

    async def create_folder(self, name: str) -> dict:
        # In Gmail, folders are essentially labels.
        return await self.create_label(name) # Reuse create_label logic

    async def move_to_folder(self, email_id: str, folder_id: str) -> str:
        try:
            # Apply the folder label and remove from inbox
            await asyncio.to_thread(
                self.service.users().messages().modify(
                    userId="me", id=email_id, body={'addLabelIds': [folder_id], 'removeLabelIds': ['INBOX']}
                ).execute
            )
            logger.info(f"Email {email_id} moved to folder {folder_id}")
            return f"Email {email_id} moved to folder {folder_id} successfully."
        except HttpError as error:
            logger.error(f"Error moving email {email_id} to folder {folder_id}: {error}")
            return f"An HttpError occurred moving email to folder: {str(error)}"

    async def list_folders(self) -> Union[List[Dict[str, str]], str]:
        try:
            all_labels = await self.list_labels()
            if isinstance(all_labels, str): # Error case
                return all_labels
            # Filter for user-created labels, which are typically used as folders
            user_folders = [lbl for lbl in all_labels if lbl.get('type') == 'user']
            return user_folders
        except Exception as e: # Catch any exception during filtering
            logger.error(f"Error listing folders (processing labels): {e}")
            return f"An error occurred while processing labels for folders: {str(e)}"

    async def archive_email(self, email_id: str) -> str:
        try:
            await asyncio.to_thread(
                self.service.users().messages().modify(userId="me", id=email_id, body={'removeLabelIds': ['INBOX']}).execute
            )
            logger.info(f"Email archived: {email_id}")
            return f"Email {email_id} archived successfully."
        except HttpError as error:
            logger.error(f"Error archiving email {email_id}: {error}")
            return f"An HttpError occurred archiving email {email_id}: {str(error)}"

    async def batch_archive(self, query: str, max_emails: int = 100) -> dict:
        try:
            user_id = 'me'
            messages_to_archive_ids = []
            page_token = None
            while len(messages_to_archive_ids) < max_emails:
                response = await asyncio.to_thread(
                    self.service.users().messages().list(
                        userId=user_id, q=query + " is:inboxed", # only archive what's in inbox
                        maxResults=min(max_emails - len(messages_to_archive_ids), 100),
                        pageToken=page_token
                    ).execute
                )
                if 'messages' in response:
                    messages_to_archive_ids.extend([m['id'] for m in response['messages']])
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            if not messages_to_archive_ids:
                return {'status': 'success', 'archived_count': 0, 'message': 'No emails found in inbox matching the query.'}

            # Gmail API supports batchModify for messages
            batch_modify_request_body = {
                'ids': messages_to_archive_ids,
                'removeLabelIds': ['INBOX']
            }
            await asyncio.to_thread(
                 self.service.users().messages().batchModify(userId="me", body=batch_modify_request_body).execute
            )
            archived_count = len(messages_to_archive_ids)
            logger.info(f"Batch archived {archived_count} emails")
            return {'status': 'success', 'archived_count': archived_count, 'message': f"Successfully archived {archived_count} emails."}
        except HttpError as error:
            logger.error(f"Error batch archiving emails with query '{query}': {error}")
            return {'status': 'error', 'error_message': str(error)}

    async def list_archived(self, max_results: int = 50) -> Union[List[Dict[str, Any]], str]:
        try:
            # Archived emails are those not in INBOX but typically in ALL MAIL
            # A simple query for '-in:inbox' can work.
            return await self.search_emails(query="-in:inbox", max_results=max_results)
        except Exception as error: # Catch any general error
            logger.error(f"Error listing archived emails: {error}")
            return f"An error occurred listing archived emails: {str(error)}"

    async def restore_to_inbox(self, email_id: str) -> str:
        try:
            await asyncio.to_thread(
                self.service.users().messages().modify(userId="me", id=email_id, body={'addLabelIds': ['INBOX']}).execute
            )
            logger.info(f"Email restored to inbox: {email_id}")
            return f"Email {email_id} restored to inbox successfully."
        except HttpError as error:
            logger.error(f"Error restoring email {email_id} to inbox: {error}")
            return f"An HttpError occurred restoring email {email_id} to inbox: {str(error)}"


# --- FastMCP Server Setup ---
mcp = FastMCP(name="GmailToolsServer", description="A FastMCP server for managing Gmail.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Gmail API FastMCP Server')
    parser.add_argument('--creds-file-path', required=True, help='OAuth 2.0 credentials file path (e.g., credentials.json)')
    parser.add_argument('--token-path', required=True, help='File location to store/retrieve access and refresh tokens (e.g., token.json)')
    parser.add_argument('--host', default="127.0.0.1", help='Host to run the server on')
    parser.add_argument('--port', type=int, default=8002, help='Port to run the server on')
    parser.add_argument('--oauth-port', type=int, default=9000, help='Port for OAuth callback server (default: 9000)')
    
    args = parser.parse_args()

    # Initialize GmailService (which handles auth and core logic)
    gmail_service = GmailService(args.creds_file_path, args.token_path, oauth_port=args.oauth_port)

    # --- Tool Definitions (thin wrappers around GmailService instance methods) ---

    @mcp.tool()
    async def send_email(recipient_id: str, subject: str, message: str) -> Dict[str, str]:
        """Sends an email. Subject and message are distinct."""
        logger.info(f"🔧 send_email tool called: {recipient_id}, subject='{subject}', message='{message[:50]}...'")
        result = await gmail_service.send_email(recipient_id, subject, message)
        logger.info(f"🔧 send_email tool result: {result}")
        return result

    @mcp.tool()
    async def get_unread_emails() -> Union[List[Dict[str, str]], str]:
        """Retrieves a list of unread emails from the primary inbox category."""
        return await gmail_service.get_unread_emails()

    @mcp.tool()
    async def read_email_content(email_id: str) -> Union[Dict[str, str], str]:
        """Retrieves the full content of a specific email and marks it as read."""
        return await gmail_service.read_email(email_id)

    @mcp.tool()
    async def open_email_in_browser(email_id: str) -> str:
        """Attempts to open the specified email in the default web browser (on server)."""
        return await gmail_service.open_email(email_id)

    @mcp.tool()
    async def trash_email(email_id: str) -> str: 
        """Moves the specified email to the trash."""
        return await gmail_service.trash_email(email_id) 

    @mcp.tool()
    async def mark_email_as_read(email_id: str) -> str:
        """Marks the specified email as read."""
        return await gmail_service.mark_email_as_read(email_id)

    @mcp.tool()
    async def create_draft_email(recipient_id: str, subject: str, message: str) -> Dict[str, str]:
        """Creates a draft email message."""
        return await gmail_service.create_draft(recipient_id, subject, message)

    @mcp.tool()
    async def list_draft_emails() -> Union[List[Dict[str, str]], str]:
        """Lists all draft emails with their ID, subject, and recipient."""
        return await gmail_service.list_drafts()

    @mcp.tool()
    async def list_gmail_labels() -> Union[List[Dict[str, str]], str]:
        """Lists all labels in the user's mailbox."""
        return await gmail_service.list_labels()

    @mcp.tool()
    async def create_new_label(label_name: str) -> Dict[str, str]:
        """Creates a new label in Gmail."""
        return await gmail_service.create_label(label_name)

    @mcp.tool()
    async def apply_label_to_email(email_id: str, label_id: str) -> str:
        """Applies an existing label to a specific email."""
        return await gmail_service.apply_label(email_id, label_id)

    @mcp.tool()
    async def remove_label_from_email(email_id: str, label_id: str) -> str:
        """Removes a label from a specific email."""
        return await gmail_service.remove_label(email_id, label_id)

    @mcp.tool()
    async def rename_gmail_label(label_id: str, new_name: str) -> Dict[str, str]:
        """Renames an existing label."""
        return await gmail_service.rename_label(label_id, new_name)

    @mcp.tool()
    async def delete_gmail_label(label_id: str) -> str:
        """Permanently deletes a label."""
        return await gmail_service.delete_label(label_id)

    @mcp.tool()
    async def search_emails_by_label(label_id: str) -> Union[List[Dict[str, str]], str]:
        """Searches for all emails that have a specific label applied."""
        return await gmail_service.search_by_label(label_id)

    @mcp.tool()
    async def list_email_filters() -> Union[List[Dict[str, Any]], str]:
        """Lists all email filters set up in the user's Gmail account."""
        return await gmail_service.list_filters()

    @mcp.tool()
    async def get_email_filter_details(filter_id: str) -> Union[Dict[str, Any], str]:
        """Gets the detailed configuration of a specific email filter by its ID."""
        return await gmail_service.get_filter(filter_id)

    @mcp.tool()
    async def create_new_email_filter(
            criteria_from: Optional[str] = None, criteria_to: Optional[str] = None,
            criteria_subject: Optional[str] = None, criteria_query: Optional[str] = None,
            criteria_has_attachment: Optional[bool] = None, criteria_exclude_chats: Optional[bool] = None,
            criteria_size_comparison: Optional[str] = None, criteria_size_bytes: Optional[int] = None,
            action_add_label_ids: Optional[List[str]] = None, action_remove_label_ids: Optional[List[str]] = None,
            action_forward_to_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a new email filter with specified criteria and actions."""
        return await gmail_service.create_filter(
            from_email=criteria_from, to_email=criteria_to, subject=criteria_subject, query=criteria_query,
            has_attachment=criteria_has_attachment, exclude_chats=criteria_exclude_chats,
            size_comparison=criteria_size_comparison, size=criteria_size_bytes,
            add_label_ids=action_add_label_ids, remove_label_ids=action_remove_label_ids,
            forward_to=action_forward_to_email
        )

    @mcp.tool()
    async def delete_email_filter(filter_id: str) -> str:
        """Deletes a specific email filter by its ID."""
        return await gmail_service.delete_filter(filter_id)

    @mcp.tool()
    async def search_all_emails(query: str, max_results: Optional[int] = 50) -> Union[List[Dict[str, Any]], str]:
        """Searches all emails using Gmail's search syntax. Returns basic message info."""
        return await gmail_service.search_emails(query, max_results)

    @mcp.tool()
    async def create_new_folder(folder_name: str) -> Dict[str, str]:
        """Creates a new folder (which is a label in Gmail)."""
        return await gmail_service.create_folder(folder_name)

    @mcp.tool()
    async def move_email_to_folder(email_id: str, folder_id: str) -> str:
        """Moves an email to a specified folder (applies label, removes from inbox)."""
        return await gmail_service.move_to_folder(email_id, folder_id)

    @mcp.tool()
    async def list_email_folders() -> Union[List[Dict[str, str]], str]:
        """Lists all user-created folders (user-defined labels)."""
        return await gmail_service.list_folders()

    @mcp.tool()
    async def archive_email(email_id: str) -> str: 
        """Archives an email (removes 'INBOX' label)."""
        return await gmail_service.archive_email(email_id)

    @mcp.tool()
    async def batch_archive_emails(query: str, max_emails_to_archive: Optional[int] = 100) -> Dict[str, Any]:
        """Archives multiple emails from inbox matching a search query."""
        return await gmail_service.batch_archive(query, max_emails_to_archive)

    @mcp.tool()
    async def list_archived_emails(max_results_to_list: Optional[int] = 50) -> Union[List[Dict[str, Any]], str]:
        """Lists emails that have been archived (not in inbox)."""
        return await gmail_service.list_archived(max_results_to_list)

    @mcp.tool()
    async def restore_email_to_inbox(email_id: str) -> str:
        """Restores an archived email back to the inbox."""
        return await gmail_service.restore_to_inbox(email_id)

    # Health endpoint for server monitoring
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        """Health check endpoint for monitoring server status."""
        from starlette.responses import JSONResponse
        return JSONResponse({
            "status": "healthy",
            "service": "gmail-mcp-server", 
            "version": "1.0.0",
            "timestamp": str(datetime.now()),
            "mcp_endpoint": "/mcp/",
            "gmail_user": gmail_service.user_email
        })

    # --- Run FastMCP Server ---
    try:
        logger.info(f"Starting Gmail FastMCP server on http://{args.host}:{args.port}")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested.")
    except Exception as e:
        logger.error(f"An unexpected error running FastMCP server: {e}", exc_info=True)