"""
Outlook Service - Interface with local Microsoft Outlook on Mac via AppleScript.

Uses the appscript library to communicate with Outlook through AppleScript.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


class OutlookService:
    """
    Service class for interacting with Microsoft Outlook on Mac.

    Uses appscript (Python AppleScript bridge) to control Outlook.
    """

    # Category name used to mark emails as processed by Nova
    NOVA_PROCESSED_CATEGORY = "Nova Processed"

    def __init__(self):
        self._outlook = None
        self._connected = False
        self._category_ensured = False
        # Don't connect at init - defer to first use to avoid blocking startup
        logger.info("OutlookService initialized (lazy connection)")

    def _connect(self, timeout: float = 10.0) -> bool:
        """Establish connection to Outlook via appscript with timeout."""
        import concurrent.futures
        import threading

        def _do_connect():
            from appscript import app, k
            outlook = app('Microsoft Outlook')
            # Test connection by checking if Outlook is running
            outlook.name()
            return outlook

        try:
            # Use ThreadPoolExecutor with timeout to prevent hanging
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_connect)
                self._outlook = future.result(timeout=timeout)
                self._connected = True
                logger.info("Connected to Microsoft Outlook")
                return True
        except concurrent.futures.TimeoutError:
            logger.warning(f"Timeout connecting to Outlook after {timeout}s - is Outlook running?")
            self._connected = False
            return False
        except Exception as e:
            logger.warning(f"Could not connect to Outlook: {e}")
            self._connected = False
            return False

    async def check_outlook_status(self) -> Dict[str, Any]:
        """Check if Outlook is running and accessible."""
        try:
            if self._outlook is None:
                self._connect()
            
            if self._outlook:
                # Try to access Outlook's name to verify connection
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self._outlook.name())
                return {"connected": True}
        except Exception as e:
            self._connected = False
            return {"connected": False, "error": str(e)}
        
        return {"connected": False, "error": "Outlook not initialized"}

    async def list_emails(
        self,
        folder: str = "inbox",
        limit: int = 20,
        unread_only: bool = False,
        exclude_processed: bool = False,
        since_date: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """List emails from the specified folder.

        Args:
            folder: Folder to list emails from (default: inbox)
            limit: Maximum number of emails to return
            unread_only: Only return unread emails
            exclude_processed: Exclude emails marked with Nova Processed category
            since_date: Only return emails received on or after this date (ISO format: YYYY-MM-DD)
        """
        try:
            if not await self._ensure_connected():
                return {"error": "Could not connect to Outlook. Is it running?"}

            loop = asyncio.get_event_loop()
            nova_category = self.NOVA_PROCESSED_CATEGORY

            # Parse since_date if provided
            min_date = None
            if since_date:
                try:
                    min_date = datetime.strptime(since_date, "%Y-%m-%d")
                    logger.info(f"Filtering emails since {since_date}")
                except ValueError:
                    logger.warning(f"Invalid since_date format: {since_date}, expected YYYY-MM-DD")

            def _get_emails():
                # Get the inbox folder
                # In Outlook for Mac, we access the default account's inbox
                inbox = self._outlook.inbox
                messages = inbox.messages()

                results = []
                count = 0

                for msg in messages:
                    if count >= limit:
                        break

                    try:
                        is_read = msg.is_read()

                        # Skip read messages if unread_only is True
                        if unread_only and is_read:
                            continue

                        # Get categories and check if processed
                        categories = []
                        is_nova_processed = False
                        try:
                            msg_categories = msg.categories()
                            categories = [c.name() for c in msg_categories]
                            is_nova_processed = nova_category in categories
                        except Exception as e:
                            logger.debug(f"Error getting categories: {e}")

                        # Skip processed emails if exclude_processed is True
                        if exclude_processed and is_nova_processed:
                            continue

                        # Check date filter if since_date was provided
                        if min_date:
                            try:
                                msg_date = msg.time_received()
                                # msg_date is a datetime object from appscript
                                if hasattr(msg_date, 'date'):
                                    # It's a datetime, compare date portion
                                    if msg_date.date() < min_date.date():
                                        continue
                                elif isinstance(msg_date, datetime):
                                    if msg_date.date() < min_date.date():
                                        continue
                            except Exception as e:
                                logger.debug(f"Error checking date filter: {e}")
                                # If we can't parse the date, include the email anyway

                        # Get sender info safely
                        try:
                            sender = msg.sender()
                            # appscript returns a keyword dict-like object
                            # Access using appscript's k (keyword) notation
                            from appscript import k
                            if isinstance(sender, dict):
                                sender_name = sender.get(k.name, "Unknown")
                                sender_email = sender.get(k.address, "")
                            elif hasattr(sender, '__getitem__'):
                                # Try dict-style access with appscript keywords
                                try:
                                    sender_name = sender[k.name]
                                    sender_email = sender[k.address]
                                except (KeyError, TypeError):
                                    sender_name = str(sender)
                                    sender_email = ""
                            else:
                                sender_name = str(sender)
                                sender_email = ""
                        except Exception as e:
                            logger.debug(f"Error extracting sender: {e}")
                            sender_name = "Unknown"
                            sender_email = ""

                        results.append({
                            "id": str(msg.id()),
                            "subject": msg.subject() or "(No Subject)",
                            "sender_name": sender_name,
                            "sender_email": sender_email,
                            "date": str(msg.time_received()),
                            "is_read": is_read,
                            "is_nova_processed": is_nova_processed,
                            "categories": categories
                        })
                        count += 1
                    except Exception as e:
                        logger.debug(f"Error reading message: {e}")
                        continue

                return results

            emails = await loop.run_in_executor(None, _get_emails)
            return emails

        except Exception as e:
            logger.error(f"Error listing emails: {e}")
            return {"error": f"Failed to list emails: {str(e)}"}

    async def read_email(self, email_id: str) -> Dict[str, Any]:
        """Read the full content of an email by ID."""
        try:
            if not await self._ensure_connected():
                return {"error": "Could not connect to Outlook. Is it running?"}
            
            loop = asyncio.get_event_loop()
            
            def _read_email():
                from appscript import k

                # Find the message by ID
                inbox = self._outlook.inbox
                messages = inbox.messages()

                for msg in messages:
                    try:
                        if str(msg.id()) == email_id:
                            # Get sender info safely (same approach as list_emails)
                            try:
                                sender = msg.sender()
                                # appscript returns a keyword dict-like object
                                if isinstance(sender, dict):
                                    sender_name = sender.get(k.name, "Unknown")
                                    sender_email = sender.get(k.address, "")
                                elif hasattr(sender, '__getitem__'):
                                    # Try dict-style access with appscript keywords
                                    try:
                                        sender_name = sender[k.name]
                                        sender_email = sender[k.address]
                                    except (KeyError, TypeError):
                                        sender_name = str(sender)
                                        sender_email = ""
                                else:
                                    sender_name = str(sender)
                                    sender_email = ""
                            except Exception:
                                sender_name = "Unknown"
                                sender_email = ""
                            
                            # Get recipients
                            try:
                                to_recipients = []
                                for recipient in msg.to_recipients():
                                    rec_email = recipient.email_address.address() if hasattr(recipient, 'email_address') else str(recipient)
                                    to_recipients.append(rec_email)
                            except Exception:
                                to_recipients = []
                            
                            # Get body content
                            try:
                                body = msg.plain_text_content() or msg.content() or ""
                            except Exception:
                                try:
                                    body = msg.content() or ""
                                except Exception:
                                    body = "(Could not retrieve body)"
                            
                            return {
                                "id": email_id,
                                "subject": msg.subject() or "(No Subject)",
                                "sender_name": sender_name,
                                "sender_email": sender_email,
                                "to": to_recipients,
                                "date": str(msg.time_received()),
                                "body": body,
                                "is_read": msg.is_read()
                            }
                    except Exception as e:
                        logger.debug(f"Error reading message: {e}")
                        continue
                
                return {"error": f"Email with ID {email_id} not found"}
            
            result = await loop.run_in_executor(None, _read_email)
            return result
            
        except Exception as e:
            logger.error(f"Error reading email: {e}")
            return {"error": f"Failed to read email: {str(e)}"}

    async def create_draft(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Create a draft email in Outlook."""
        try:
            if not await self._ensure_connected():
                return {"error": "Could not connect to Outlook. Is it running?"}
            
            loop = asyncio.get_event_loop()
            
            def _create_draft():
                from appscript import k

                # Create a new outgoing message using appscript keywords
                msg = self._outlook.make(
                    new=k.outgoing_message,
                    with_properties={
                        k.subject: subject,
                        k.content: body
                    }
                )

                # Add recipients
                for recipient_email in recipients:
                    msg.make(
                        new=k.to_recipient,
                        with_properties={
                            k.email_address: {k.address: recipient_email}
                        }
                    )

                # Add CC recipients if provided
                if cc:
                    for cc_email in cc:
                        msg.make(
                            new=k.cc_recipient,
                            with_properties={
                                k.email_address: {k.address: cc_email}
                            }
                        )

                # Message is automatically saved in Drafts folder upon creation
                # No explicit save() call needed (and it doesn't work for outgoing messages)

                return {
                    "status": "success",
                    "message": f"Draft created with subject: {subject}",
                    "recipients": recipients,
                    "cc": cc or []
                }

            result = await loop.run_in_executor(None, _create_draft)
            return result

        except Exception as e:
            logger.error(f"Error creating draft: {e}")
            return {"error": f"Failed to create draft: {str(e)}"}

    async def send_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None
    ) -> str:
        """Send an email directly via Outlook (requires user approval)."""
        try:
            if not await self._ensure_connected():
                return "Error: Could not connect to Outlook. Is it running?"

            loop = asyncio.get_event_loop()

            def _send_email():
                from appscript import k

                # Create a new outgoing message using appscript keywords
                msg = self._outlook.make(
                    new=k.outgoing_message,
                    with_properties={
                        k.subject: subject,
                        k.content: body
                    }
                )

                # Add recipients
                for recipient_email in recipients:
                    msg.make(
                        new=k.to_recipient,
                        with_properties={
                            k.email_address: {k.address: recipient_email}
                        }
                    )

                # Add CC recipients if provided
                if cc:
                    for cc_email in cc:
                        msg.make(
                            new=k.cc_recipient,
                            with_properties={
                                k.email_address: {k.address: cc_email}
                            }
                        )

                # Send the email
                msg.send()

                # Format recipients as string for clear output
                recipients_str = ", ".join(recipients)
                cc_str = ", ".join(cc) if cc else None

                if cc_str:
                    return f"Email successfully sent to {recipients_str} (CC: {cc_str}) with subject: {subject}"
                else:
                    return f"Email successfully sent to {recipients_str} with subject: {subject}"

            result = await loop.run_in_executor(None, _send_email)
            return result

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return f"Error: Failed to send email: {str(e)}"

    async def list_calendar_events(
        self,
        days_ahead: int = 7,
        limit: int = 50,
        calendar_name: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """List upcoming calendar events from Outlook."""
        try:
            if not await self._ensure_connected():
                return {"error": "Could not connect to Outlook. Is it running?"}
            
            loop = asyncio.get_event_loop()
            
            def _get_events():
                # Get calendar
                if calendar_name:
                    calendars = self._outlook.calendars.filter(
                        self._outlook.calendar.name == calendar_name
                    )
                    if calendars:
                        calendar = calendars[0]
                    else:
                        return {"error": f"Calendar '{calendar_name}' not found"}
                else:
                    # Use the default calendar
                    calendar = self._outlook.default_calendar
                
                # Calculate date range
                now = datetime.now()
                end_date = now + timedelta(days=days_ahead)
                
                # Get events
                events = calendar.calendar_events()
                
                results = []
                count = 0
                
                for event in events:
                    if count >= limit:
                        break
                    
                    try:
                        start_time = event.start_time()
                        end_time = event.end_time()
                        
                        # Filter to events within our date range
                        if start_time and start_time >= now and start_time <= end_date:
                            # Get attendees
                            try:
                                attendees = []
                                for attendee in event.attendees():
                                    att_email = attendee.email_address.address() if hasattr(attendee, 'email_address') else str(attendee)
                                    attendees.append(att_email)
                            except Exception:
                                attendees = []
                            
                            results.append({
                                "id": str(event.id()),
                                "subject": event.subject() or "(No Subject)",
                                "start": str(start_time),
                                "end": str(end_time) if end_time else None,
                                "location": event.location() or "",
                                "attendees": attendees,
                                "is_all_day": event.is_all_day_event() if hasattr(event, 'is_all_day_event') else False
                            })
                            count += 1
                    except Exception as e:
                        logger.debug(f"Error reading event: {e}")
                        continue
                
                # Sort by start time
                results.sort(key=lambda x: x["start"])
                return results
            
            events = await loop.run_in_executor(None, _get_events)
            return events
            
        except Exception as e:
            logger.error(f"Error listing calendar events: {e}")
            return {"error": f"Failed to list calendar events: {str(e)}"}

    async def _ensure_connected(self) -> bool:
        """Ensure we have a connection to Outlook."""
        if not self._connected:
            return self._connect()

        # Verify connection is still alive
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._outlook.name())
            return True
        except Exception:
            self._connected = False
            return self._connect()

    async def _ensure_nova_category_exists(self) -> bool:
        """Ensure the Nova Processed category exists in Outlook."""
        if self._category_ensured:
            return True

        try:
            loop = asyncio.get_event_loop()

            def _create_category():
                from appscript import k

                # Check if category already exists
                try:
                    categories = self._outlook.categories()
                    for cat in categories:
                        if cat.name() == self.NOVA_PROCESSED_CATEGORY:
                            logger.debug(f"Category '{self.NOVA_PROCESSED_CATEGORY}' already exists")
                            return True
                except Exception as e:
                    logger.debug(f"Error checking categories: {e}")

                # Create the category with a distinct color (purple RGB)
                # Outlook for Mac uses RGB color values, not color constants
                try:
                    # Purple color as RGB tuple (matching Manager category style)
                    purple_rgb = (55769, 27242, 47288)
                    self._outlook.make(
                        new=k.category,
                        with_properties={
                            k.name: self.NOVA_PROCESSED_CATEGORY,
                            k.color: purple_rgb
                        }
                    )
                    logger.info(f"Created category '{self.NOVA_PROCESSED_CATEGORY}'")
                    return True
                except Exception as e:
                    # Category might already exist or creation failed
                    logger.warning(f"Could not create category: {e}")
                    return True  # Continue anyway, assignment might still work

            await loop.run_in_executor(None, _create_category)
            self._category_ensured = True
            return True

        except Exception as e:
            logger.error(f"Error ensuring category exists: {e}")
            return False

    async def mark_email_processed(self, email_id: str) -> Dict[str, Any]:
        """
        Mark an email as processed by Nova by adding the Nova category.

        Args:
            email_id: The unique identifier of the email to mark

        Returns:
            Status dict with success/error information
        """
        try:
            if not await self._ensure_connected():
                return {"error": "Could not connect to Outlook. Is it running?"}

            # Ensure category exists first
            await self._ensure_nova_category_exists()

            loop = asyncio.get_event_loop()

            def _mark_processed():
                from appscript import k

                # Find the message by ID
                inbox = self._outlook.inbox
                messages = inbox.messages()

                for msg in messages:
                    try:
                        if str(msg.id()) == email_id:
                            # Get current categories
                            try:
                                current_categories = msg.categories()
                                category_names = [c.name() for c in current_categories]
                            except Exception:
                                category_names = []

                            # Check if already marked
                            if self.NOVA_PROCESSED_CATEGORY in category_names:
                                return {
                                    "status": "already_marked",
                                    "email_id": email_id,
                                    "message": "Email was already marked as processed"
                                }

                            # Find the Nova category object
                            nova_category = None
                            for cat in self._outlook.categories():
                                if cat.name() == self.NOVA_PROCESSED_CATEGORY:
                                    nova_category = cat
                                    break

                            if nova_category:
                                # Add the category to the message
                                # Outlook for Mac uses a different approach - set category directly
                                new_categories = list(current_categories) + [nova_category]
                                msg.categories.set(new_categories)

                                return {
                                    "status": "success",
                                    "email_id": email_id,
                                    "message": f"Email marked as processed with category '{self.NOVA_PROCESSED_CATEGORY}'"
                                }
                            else:
                                return {
                                    "status": "error",
                                    "email_id": email_id,
                                    "error": f"Category '{self.NOVA_PROCESSED_CATEGORY}' not found"
                                }
                    except Exception as e:
                        logger.debug(f"Error processing message: {e}")
                        continue

                return {"error": f"Email with ID {email_id} not found"}

            result = await loop.run_in_executor(None, _mark_processed)
            return result

        except Exception as e:
            logger.error(f"Error marking email as processed: {e}")
            return {"error": f"Failed to mark email as processed: {str(e)}"}

    async def is_email_processed(self, email_id: str) -> bool:
        """
        Check if an email has been marked as processed by Nova.

        Args:
            email_id: The unique identifier of the email to check

        Returns:
            True if email has the Nova Processed category, False otherwise
        """
        try:
            if not await self._ensure_connected():
                return False

            loop = asyncio.get_event_loop()

            def _check_processed():
                inbox = self._outlook.inbox
                messages = inbox.messages()

                for msg in messages:
                    try:
                        if str(msg.id()) == email_id:
                            try:
                                current_categories = msg.categories()
                                category_names = [c.name() for c in current_categories]
                                return self.NOVA_PROCESSED_CATEGORY in category_names
                            except Exception:
                                return False
                    except Exception:
                        continue

                return False

            return await loop.run_in_executor(None, _check_processed)

        except Exception as e:
            logger.error(f"Error checking if email is processed: {e}")
            return False
