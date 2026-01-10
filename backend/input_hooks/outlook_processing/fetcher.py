"""
Outlook email fetching and MCP communication for Nova.

Handles all MCP tool interactions for Outlook email retrieval via LiteLLM.
"""
import os
import httpx
from typing import List, Dict, Any, Optional
from mcp_client import mcp_manager
from utils.logging import get_logger
from utils.phoenix_integration import disable_phoenix_tracing

logger = get_logger(__name__)


class OutlookFetcher:
    """Handles Outlook email fetching via MCP tools."""

    # Outlook MCP server name (as registered in LiteLLM)
    MCP_SERVER_NAME = "outlook_mac"

    # Outlook MCP tool names (prefixed per ADR-019)
    TOOL_LIST_EMAILS = "outlook_list_emails"
    TOOL_READ_EMAIL = "outlook_read_email"

    # Internal REST endpoint for marking emails (not an MCP tool)
    OUTLOOK_SERVER_URL = os.environ.get("OUTLOOK_MCP_URL", "http://localhost:9000")

    def __init__(self):
        self._tools_cache: Optional[Dict[str, Any]] = None

    async def fetch_unprocessed_emails(
        self,
        max_emails: int = 50,
        folder: str = "inbox",
        since_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch unprocessed emails from Outlook.

        Uses the exclude_processed parameter to only get emails that haven't
        been marked with the "Nova Processed" category.

        Args:
            max_emails: Maximum number of emails to fetch
            folder: Folder to fetch from (default: inbox)
            since_date: Only fetch emails from this date onwards (YYYY-MM-DD)

        Returns:
            List of email dictionaries with full content (empty if tools unavailable)
        """
        try:
            # Check if required tools are available first
            tools = await self._get_outlook_tools()
            if not tools or self.TOOL_LIST_EMAILS not in tools:
                logger.warning(
                    "Outlook email hook skipped - required MCP tools not available",
                    extra={"data": {
                        "required_tool": self.TOOL_LIST_EMAILS,
                        "available_tools": list(tools.keys()) if tools else []
                    }}
                )
                return []

            logger.info(
                "Fetching unprocessed Outlook emails",
                extra={"data": {"max_emails": max_emails, "folder": folder, "since_date": since_date}}
            )

            # Build tool arguments
            tool_args = {
                "folder": folder,
                "limit": max_emails,
                "unread_only": False,
                "exclude_processed": True
            }
            if since_date:
                tool_args["since_date"] = since_date

            # Call list_emails with exclude_processed=True
            result = await self._call_outlook_tool(
                self.TOOL_LIST_EMAILS,
                **tool_args
            )

            if not result:
                logger.info("No unprocessed emails found in Outlook")
                return []

            # Handle response - could be list or dict with error
            if isinstance(result, dict) and "error" in result:
                logger.warning(
                    "Error from Outlook MCP - returning empty results",
                    extra={"data": {"error": result["error"]}}
                )
                return []

            # Parse the email list
            emails = self._parse_email_list(result)

            logger.info(
                f"Found {len(emails)} unprocessed Outlook emails",
                extra={"data": {"count": len(emails)}}
            )

            # Fetch full content for each email
            full_emails = []
            for email_summary in emails:
                try:
                    email_id = email_summary.get("id")
                    if not email_id:
                        continue

                    full_email = await self._call_outlook_tool(
                        self.TOOL_READ_EMAIL,
                        email_id=email_id
                    )

                    if full_email and not isinstance(full_email, dict) or "error" not in full_email:
                        # Merge summary info with full content
                        merged = {**email_summary, **full_email} if isinstance(full_email, dict) else email_summary
                        full_emails.append(merged)
                    else:
                        # Use summary if full fetch fails
                        full_emails.append(email_summary)

                except Exception as e:
                    logger.warning(
                        f"Failed to fetch full email content, using summary",
                        extra={"data": {"email_id": email_summary.get("id"), "error": str(e)}}
                    )
                    full_emails.append(email_summary)

            logger.info(
                f"Fetched {len(full_emails)} Outlook emails with content",
                extra={"data": {"count": len(full_emails)}}
            )

            return full_emails

        except Exception as e:
            logger.warning(
                "Failed to fetch Outlook emails - returning empty results",
                extra={"data": {"error": str(e)}}
            )
            return []

    async def mark_email_processed(self, email_id: str) -> bool:
        """
        Mark an email as processed in Outlook.

        Adds the "Nova Processed" category to the email so it won't be
        fetched again in future polling cycles.

        Calls the internal REST endpoint (not an MCP tool) to keep the
        LLM tool context clean.

        Args:
            email_id: The Outlook email ID

        Returns:
            True if successfully marked, False otherwise
        """
        try:
            url = f"{self.OUTLOOK_SERVER_URL}/internal/mark-processed/{email_id}"

            async with httpx.AsyncClient() as client:
                response = await client.post(url, timeout=10.0)
                response.raise_for_status()
                result = response.json()

            if result.get("status") in ("success", "already_marked"):
                logger.info(
                    "Marked email as processed in Outlook",
                    extra={"data": {"email_id": email_id, "status": result.get("status")}}
                )
                return True
            elif "error" in result:
                logger.error(
                    "Failed to mark email as processed",
                    extra={"data": {"email_id": email_id, "error": result["error"]}}
                )
                return False

            return True

        except Exception as e:
            logger.error(
                "Error marking email as processed",
                extra={"data": {"email_id": email_id, "error": str(e)}}
            )
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Check if Outlook MCP is accessible and working.

        Returns:
            Health status dict with connected status and any errors
        """
        try:
            tools = await self._get_outlook_tools()

            if not tools:
                return {
                    "healthy": False,
                    "error": "No Outlook MCP tools available",
                    "tools_available": []
                }

            if self.TOOL_LIST_EMAILS not in tools:
                return {
                    "healthy": False,
                    "error": f"Required tool {self.TOOL_LIST_EMAILS} not available",
                    "tools_available": list(tools.keys())
                }

            # Try a simple list call with limit=1 to verify connectivity
            result = await self._call_outlook_tool(
                self.TOOL_LIST_EMAILS,
                folder="inbox",
                limit=1,
                exclude_processed=False
            )

            if result is None:
                return {
                    "healthy": False,
                    "error": "Failed to call list_emails tool",
                    "tools_available": list(tools.keys())
                }

            if isinstance(result, dict) and "error" in result:
                return {
                    "healthy": False,
                    "error": result["error"],
                    "tools_available": list(tools.keys())
                }

            return {
                "healthy": True,
                "tools_available": list(tools.keys())
            }

        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "tools_available": []
            }

    async def _get_outlook_tools(self) -> Dict[str, Any]:
        """Get Outlook-related MCP tools."""
        if self._tools_cache is None:
            all_tools = await mcp_manager.get_tools()

            self._tools_cache = {}
            for tool in all_tools:
                tool_name = getattr(tool, 'name', '')
                # LangChain tools have description prefixed with server name
                tool_description = getattr(tool, 'description', '')

                # Only cache Outlook tools - check if description starts with [outlook_mac]
                if f"[{self.MCP_SERVER_NAME}]" in tool_description:
                    self._tools_cache[tool_name] = tool

            logger.info(
                f"Found {len(self._tools_cache)} Outlook MCP tools",
                extra={"data": {"tools": list(self._tools_cache.keys())}}
            )

        return self._tools_cache

    async def _call_outlook_tool(self, tool_name: str, **kwargs) -> Optional[Any]:
        """
        Call an Outlook MCP tool with the given parameters.

        Returns:
            Tool result, or None if tool not available
        """
        tools = await self._get_outlook_tools()

        if tool_name not in tools:
            available = list(tools.keys())
            logger.warning(
                f"Outlook tool '{tool_name}' not available",
                extra={"data": {"tool_name": tool_name, "available_tools": available}}
            )
            return None

        tool = tools[tool_name]

        try:
            # Call with tracing disabled
            with disable_phoenix_tracing():
                result = await tool.arun(kwargs)

            # Parse JSON string responses
            if isinstance(result, str):
                import json
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    pass

            return result

        except Exception as e:
            logger.error(
                f"Failed to call Outlook tool {tool_name}",
                extra={"data": {"tool": tool_name, "kwargs": kwargs, "error": str(e)}}
            )
            raise

    def _parse_email_list(self, result: Any) -> List[Dict[str, Any]]:
        """Parse email list from MCP response."""
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            if "emails" in result:
                return result["emails"]
            elif "messages" in result:
                return result["messages"]
            elif "data" in result and isinstance(result["data"], list):
                return result["data"]
        return []

    def clear_cache(self):
        """Clear the tools cache."""
        self._tools_cache = None
