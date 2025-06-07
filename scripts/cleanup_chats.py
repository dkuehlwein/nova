#!/usr/bin/env python3
"""
Chat Cleanup Script for Nova

This script provides comprehensive cleanup of chat conversations:
1. Removes all thread data from PostgreSQL checkpointer (LangGraph state)
2. Removes all chat records from Nova database tables
3. Provides utilities for ongoing maintenance

Usage:
  python scripts/cleanup_chats.py --all              # Clean everything
  python scripts/cleanup_chats.py --checkpointer     # Clean only checkpointer data
  python scripts/cleanup_chats.py --database         # Clean only Nova database tables
  python scripts/cleanup_chats.py --list             # List current data counts
  python scripts/cleanup_chats.py --thread <id>      # Clean specific thread
"""

import asyncio
import argparse
import logging
import os
import sys
from typing import List, Optional

# Add backend to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from database.database import db_manager
from models.models import Chat, ChatMessage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ChatCleaner:
    """Comprehensive chat data cleanup utility."""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova_kanban'
        )
        self.engine = create_async_engine(self.database_url)
        
    async def get_checkpointer_stats(self) -> dict:
        """Get statistics about checkpointer data."""
        try:
            # Create connection pool for checkpointer
            pool = AsyncConnectionPool(
                self.database_url.replace('+asyncpg', ''),
                open=False
            )
            await pool.open()
            
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                
                # Count total checkpoints
                checkpoint_count = 0
                thread_ids = set()
                
                async for checkpoint_tuple in checkpointer.alist(None):
                    checkpoint_count += 1
                    if checkpoint_tuple.config and checkpoint_tuple.config.get("configurable", {}).get("thread_id"):
                        thread_id = checkpoint_tuple.config["configurable"]["thread_id"]
                        if thread_id:
                            thread_ids.add(thread_id)
                
            await pool.close()
            
            return {
                'total_checkpoints': checkpoint_count,
                'unique_threads': len(thread_ids),
                'thread_ids': sorted(list(thread_ids))
            }
            
        except Exception as e:
            logger.error(f"Error getting checkpointer stats: {e}")
            return {'total_checkpoints': 0, 'unique_threads': 0, 'thread_ids': []}
    
    async def get_database_stats(self) -> dict:
        """Get statistics about Nova database chat data."""
        try:
            async with self.engine.begin() as conn:
                # Count chats
                result = await conn.execute(text("SELECT COUNT(*) FROM chats"))
                chat_count = result.scalar()
                
                # Count chat messages
                result = await conn.execute(text("SELECT COUNT(*) FROM chat_messages"))
                message_count = result.scalar()
                
                # Get chat IDs
                result = await conn.execute(text("SELECT id FROM chats ORDER BY created_at"))
                chat_ids = [str(row[0]) for row in result.fetchall()]
                
                return {
                    'total_chats': chat_count,
                    'total_messages': message_count,
                    'chat_ids': chat_ids
                }
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {'total_chats': 0, 'total_messages': 0, 'chat_ids': []}
    
    async def clean_checkpointer_data(self, thread_id: Optional[str] = None) -> bool:
        """Clean checkpointer data for specific thread or all threads."""
        try:
            # Create connection pool for checkpointer
            pool = AsyncConnectionPool(
                self.database_url.replace('+asyncpg', ''),
                open=False
            )
            await pool.open()
            
            async with pool.connection() as conn:
                checkpointer = AsyncPostgresSaver(conn)
                
                if thread_id:
                    # Delete specific thread
                    logger.info(f"Deleting checkpointer data for thread: {thread_id}")
                    await checkpointer.adelete_thread(thread_id)
                    logger.info(f"✅ Deleted thread {thread_id} from checkpointer")
                else:
                    # Get all thread IDs first
                    thread_ids = set()
                    async for checkpoint_tuple in checkpointer.alist(None):
                        if checkpoint_tuple.config and checkpoint_tuple.config.get("configurable", {}).get("thread_id"):
                            tid = checkpoint_tuple.config["configurable"]["thread_id"]
                            if tid:
                                thread_ids.add(tid)
                    
                    # Delete all threads
                    logger.info(f"Found {len(thread_ids)} threads to delete from checkpointer")
                    for tid in thread_ids:
                        try:
                            await checkpointer.adelete_thread(tid)
                            logger.debug(f"Deleted thread {tid}")
                        except Exception as e:
                            logger.warning(f"Failed to delete thread {tid}: {e}")
                    
                    logger.info(f"✅ Deleted {len(thread_ids)} threads from checkpointer")
            
            await pool.close()
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning checkpointer data: {e}")
            return False
    
    async def clean_database_data(self, chat_id: Optional[str] = None) -> bool:
        """Clean Nova database chat data for specific chat or all chats."""
        try:
            async with db_manager.get_session() as session:
                if chat_id:
                    # Delete specific chat
                    logger.info(f"Deleting database data for chat: {chat_id}")
                    
                    # Delete chat messages first (foreign key constraint)
                    result = await session.execute(
                        text("DELETE FROM chat_messages WHERE chat_id = :chat_id"),
                        {"chat_id": chat_id}
                    )
                    message_count = result.rowcount
                    
                    # Delete chat
                    result = await session.execute(
                        text("DELETE FROM chats WHERE id = :chat_id"),
                        {"chat_id": chat_id}
                    )
                    chat_count = result.rowcount
                    
                    logger.info(f"✅ Deleted chat {chat_id}: {message_count} messages, {chat_count} chat record")
                else:
                    # Delete all chats and messages
                    logger.info("Deleting all database chat data")
                    
                    # Delete all chat messages first
                    result = await session.execute(text("DELETE FROM chat_messages"))
                    message_count = result.rowcount
                    
                    # Delete all chats
                    result = await session.execute(text("DELETE FROM chats"))
                    chat_count = result.rowcount
                    
                    logger.info(f"✅ Deleted all database chat data: {message_count} messages, {chat_count} chats")
                
                await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning database data: {e}")
            return False
    
    async def print_stats(self):
        """Print current statistics."""
        logger.info("📊 Current Chat Data Statistics")
        logger.info("=" * 50)
        
        # Checkpointer stats
        checkpointer_stats = await self.get_checkpointer_stats()
        logger.info(f"📋 Checkpointer (LangGraph State):")
        logger.info(f"   - Total checkpoints: {checkpointer_stats['total_checkpoints']}")
        logger.info(f"   - Unique threads: {checkpointer_stats['unique_threads']}")
        if checkpointer_stats['thread_ids']:
            logger.info(f"   - Thread IDs: {', '.join(checkpointer_stats['thread_ids'][:5])}{'...' if len(checkpointer_stats['thread_ids']) > 5 else ''}")
        
        # Database stats  
        database_stats = await self.get_database_stats()
        logger.info(f"🗄️  Nova Database:")
        logger.info(f"   - Total chats: {database_stats['total_chats']}")
        logger.info(f"   - Total messages: {database_stats['total_messages']}")
        if database_stats['chat_ids']:
            logger.info(f"   - Chat IDs: {', '.join(database_stats['chat_ids'][:3])}{'...' if len(database_stats['chat_ids']) > 3 else ''}")
        
        # Check for checkpointer tables
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT table_name, 
                           (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
                    FROM information_schema.tables t 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('checkpoints', 'checkpoint_writes', 'checkpoint_blobs')
                    ORDER BY table_name
                """))
                checkpoint_tables = result.fetchall()
                
                if checkpoint_tables:
                    logger.info(f"🔧 Checkpointer Tables:")
                    for table_name, col_count in checkpoint_tables:
                        row_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                        row_count = row_result.scalar()
                        logger.info(f"   - {table_name}: {row_count} rows ({col_count} columns)")
        except Exception as e:
            logger.warning(f"Could not check checkpointer tables: {e}")
        
        logger.info("=" * 50)
    
    async def clean_all(self) -> bool:
        """Clean all chat data from both checkpointer and database."""
        logger.info("🧹 Starting comprehensive chat cleanup...")
        
        success = True
        
        # Clean checkpointer data
        if not await self.clean_checkpointer_data():
            success = False
        
        # Clean database data
        if not await self.clean_database_data():
            success = False
        
        if success:
            logger.info("✅ All chat data cleaned successfully!")
        else:
            logger.error("❌ Some cleanup operations failed")
        
        return success
    
    async def close(self):
        """Close database connections."""
        await self.engine.dispose()


async def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description='Nova Chat Cleanup Utility')
    parser.add_argument('--all', action='store_true', help='Clean all chat data (checkpointer + database)')
    parser.add_argument('--checkpointer', action='store_true', help='Clean only checkpointer data')
    parser.add_argument('--database', action='store_true', help='Clean only Nova database data')
    parser.add_argument('--list', action='store_true', help='List current data statistics')
    parser.add_argument('--thread', type=str, help='Clean specific thread ID')
    parser.add_argument('--chat', type=str, help='Clean specific chat ID from database')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not any([args.all, args.checkpointer, args.database, args.list, args.thread, args.chat]):
        parser.print_help()
        return
    
    cleaner = ChatCleaner()
    
    try:
        if args.list:
            await cleaner.print_stats()
        
        elif args.all:
            await cleaner.print_stats()
            if input("\n⚠️  This will delete ALL chat data. Continue? (y/N): ").lower() == 'y':
                await cleaner.clean_all()
                await cleaner.print_stats()
            else:
                logger.info("Cleanup cancelled")
        
        elif args.checkpointer:
            stats = await cleaner.get_checkpointer_stats()
            logger.info(f"Found {stats['unique_threads']} threads in checkpointer")
            if stats['unique_threads'] > 0:
                if input(f"\n⚠️  Delete all {stats['unique_threads']} threads from checkpointer? (y/N): ").lower() == 'y':
                    await cleaner.clean_checkpointer_data()
                else:
                    logger.info("Cleanup cancelled")
        
        elif args.database:
            stats = await cleaner.get_database_stats()
            logger.info(f"Found {stats['total_chats']} chats in database")
            if stats['total_chats'] > 0:
                if input(f"\n⚠️  Delete all {stats['total_chats']} chats from database? (y/N): ").lower() == 'y':
                    await cleaner.clean_database_data()
                else:
                    logger.info("Cleanup cancelled")
        
        elif args.thread:
            logger.info(f"Cleaning thread: {args.thread}")
            await cleaner.clean_checkpointer_data(args.thread)
        
        elif args.chat:
            logger.info(f"Cleaning chat: {args.chat}")
            await cleaner.clean_database_data(args.chat)
            
    finally:
        await cleaner.close()


if __name__ == "__main__":
    asyncio.run(main()) 