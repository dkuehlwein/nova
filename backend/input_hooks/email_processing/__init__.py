"""
Email processing module for Nova.

This module handles the complete email-to-task pipeline with separated concerns:
- EmailNormalizer: Format detection and normalization
- EmailFetcher: MCP communication and email retrieval
- EmailTaskCreator: Email-to-task conversion
- EmailProcessor: Overall workflow orchestration
"""

from .processor import EmailProcessor
from .normalizer import EmailNormalizer
from .fetcher import EmailFetcher
from .task_creator import EmailTaskCreator

__all__ = ["EmailProcessor", "EmailNormalizer", "EmailFetcher", "EmailTaskCreator"]