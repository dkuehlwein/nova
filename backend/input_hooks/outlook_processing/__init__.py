"""
Outlook email processing module for Nova input hooks.

Provides components for fetching emails from Outlook via MCP,
normalizing them, and creating Nova tasks.
"""

from .fetcher import OutlookFetcher
from .processor import OutlookProcessor

__all__ = [
    "OutlookFetcher",
    "OutlookProcessor",
]
