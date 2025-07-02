#!/usr/bin/env python3
"""
Comprehensive Test Data Cleanup Script for Nova

This script cleans up all test data from both:
1. Nova's business tables (tasks, comments, chats, etc.)
2. LangGraph checkpointer tables (used by chat and core agent)

Updated for Nova's current schema with memory-based person/project management.
"""

import asyncio
import sys
import os
from typing import List, Tuple

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))

from database.database import db_manager
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError


class TestDataCleaner:
    """Comprehensive test data cleaner for Nova"""
    
    def __init__(self):
        self.cleaned_tables = []
        self.errors = []
    
    async def check_existing_test_data(self) -> None:
        """Check what test data currently exists in the database"""
        print("🔍 Checking existing test data...")
        
        async with db_manager.get_session() as session:
            # Check Nova business data (updated for current schema)
            queries = [
                ("Tasks with 'Test' in title", "SELECT COUNT(*) FROM tasks WHERE title LIKE '%Test%'"),
                ("All tasks", "SELECT COUNT(*) FROM tasks"),
                ("Task comments from core_agent", "SELECT COUNT(*) FROM task_comments WHERE author = 'core_agent'"),
                ("All task comments", "SELECT COUNT(*) FROM task_comments"),
                ("Agent status records", "SELECT COUNT(*) FROM agent_status"),
                ("Chat conversations", "SELECT COUNT(*) FROM chats"),
                ("Chat messages", "SELECT COUNT(*) FROM chat_messages"),
                ("Artifacts", "SELECT COUNT(*) FROM artifacts"),
            ]
            
            # Check LangGraph checkpointer data
            langgraph_queries = [
                ("LangGraph checkpoints", "SELECT COUNT(*) FROM checkpoints"),
                ("LangGraph checkpoint writes", "SELECT COUNT(*) FROM checkpoint_writes"),
                ("LangGraph checkpoint blobs", "SELECT COUNT(*) FROM checkpoint_blobs"),
                ("Core agent checkpoints", "SELECT COUNT(*) FROM checkpoints WHERE thread_id LIKE 'core_agent_%'"),
                ("Chat checkpoints", "SELECT COUNT(*) FROM checkpoints WHERE thread_id LIKE 'chat_%'"),
            ]
            
            print("\n📊 Nova Business Data:")
            for description, query in queries:
                try:
                    result = await session.execute(text(query))
                    count = result.scalar()
                    print(f"  {description}: {count}")
                except Exception as e:
                    print(f"  {description}: Error - {e}")
            
            print("\n📊 LangGraph Checkpointer Data:")
            for description, query in langgraph_queries:
                try:
                    result = await session.execute(text(query))
                    count = result.scalar()
                    print(f"  {description}: {count}")
                except Exception as e:
                    print(f"  {description}: Error - {e}")
    
    async def cleanup_nova_business_data(self) -> None:
        """Clean up Nova's business data tables (updated for current schema)"""
        print("\n🧹 Cleaning Nova business data...")
        
        # Order matters for foreign key constraints - clean child tables first
        cleanup_queries = [
            # Comments first (references tasks)
            ("task_comments", "DELETE FROM task_comments WHERE author = 'core_agent' OR content LIKE '%Test%'"),
            
            # Chat messages (references chats)
            ("chat_messages", "DELETE FROM chat_messages WHERE content LIKE '%Test%' OR content LIKE '%test%'"),
            
            # Task-artifact associations (many-to-many table)
            ("task_artifact", "DELETE FROM task_artifact WHERE task_id IN (SELECT id FROM tasks WHERE title LIKE '%Test%')"),
            
            # Main business entities (after removing foreign key references)
            ("tasks", "DELETE FROM tasks WHERE title LIKE '%Test%' OR title LIKE '%test%' OR description LIKE '%Test%' OR description LIKE '%test%'"),
            ("chats", "DELETE FROM chats WHERE title LIKE '%Test%' OR title LIKE '%test%'"),
            ("artifacts", "DELETE FROM artifacts WHERE title LIKE '%Test%' OR title LIKE '%test%' OR summary LIKE '%Test%' OR summary LIKE '%test%'"),
            
            # Note: agent_status is preserved - it's needed for core agent to function
        ]
        
        # Process each query in a separate transaction to avoid transaction abort issues
        for table_name, query in cleanup_queries:
            async with db_manager.get_session() as session:
                try:
                    result = await session.execute(text(query))
                    rows_affected = result.rowcount
                    await session.commit()
                    print(f"  ✅ {table_name}: {rows_affected} rows deleted")
                    self.cleaned_tables.append(table_name)
                except Exception as e:
                    await session.rollback()
                    error_msg = f"❌ {table_name}: {e}"
                    print(f"  {error_msg}")
                    self.errors.append(error_msg)
    
    async def cleanup_langgraph_data(self) -> None:
        """Clean up LangGraph checkpointer data"""
        print("\n🧹 Cleaning LangGraph checkpointer data...")
        
        # LangGraph checkpointer tables (order matters for foreign keys)
        langgraph_queries = [
            ("checkpoint_writes", "DELETE FROM checkpoint_writes"),
            ("checkpoints", "DELETE FROM checkpoints"),
            ("checkpoint_blobs", "DELETE FROM checkpoint_blobs"),
        ]
        
        # Process each query in a separate transaction to avoid transaction abort issues
        for table_name, query in langgraph_queries:
            async with db_manager.get_session() as session:
                try:
                    result = await session.execute(text(query))
                    rows_affected = result.rowcount
                    await session.commit()
                    print(f"  ✅ {table_name}: {rows_affected} rows deleted")
                    self.cleaned_tables.append(table_name)
                except Exception as e:
                    await session.rollback()
                    error_msg = f"❌ {table_name}: {e}"
                    print(f"  {error_msg}")
                    self.errors.append(error_msg)
    
    async def cleanup_thread_specific_data(self, thread_pattern: str = "core_agent_task_%") -> None:
        """Clean up specific thread data (for core agent tests)"""
        print(f"\n🧹 Cleaning thread-specific data (pattern: {thread_pattern})...")
        
        async with db_manager.get_session() as session:
            # Clean checkpoints for specific thread patterns (proper order for foreign keys)
            queries = [
                ("checkpoint_writes for thread pattern", 
                 f"DELETE FROM checkpoint_writes WHERE task_id IN (SELECT task_id FROM checkpoints WHERE thread_id LIKE '{thread_pattern}')"),
                ("checkpoints for thread pattern", 
                 f"DELETE FROM checkpoints WHERE thread_id LIKE '{thread_pattern}'"),
                # Note: checkpoint_blobs are cleaned separately to avoid foreign key issues
            ]
            
            for description, query in queries:
                try:
                    result = await session.execute(text(query))
                    rows_affected = result.rowcount
                    print(f"  ✅ {description}: {rows_affected} rows deleted")
                except Exception as e:
                    error_msg = f"❌ {description}: {e}"
                    print(f"  {error_msg}")
                    self.errors.append(error_msg)
            
            await session.commit()
    
    async def cleanup_core_agent_data(self) -> None:
        """Comprehensive cleanup of core agent related data"""
        print("\n🤖 Cleaning core agent specific data...")
        
        async with db_manager.get_session() as session:
            # Core agent creates tasks and processes them, so clean up:
            # 1. Test tasks created by core agent
            # 2. All core agent threads from checkpointer
            # 3. Core agent comments and status
            
            queries = [
                # Comments by core agent (usually on tasks it processes)
                ("core agent comments", "DELETE FROM task_comments WHERE author = 'core_agent'"),
                
                # Test tasks that might be created during core agent testing
                ("test tasks processed by core agent", 
                 "DELETE FROM tasks WHERE title LIKE '%Test%' OR title LIKE '%core_agent%'"),
                
                # Core agent checkpointer data
                ("core agent checkpoint writes", 
                 "DELETE FROM checkpoint_writes WHERE task_id IN (SELECT task_id FROM checkpoints WHERE thread_id LIKE 'core_agent_%')"),
                ("core agent checkpoints", 
                 "DELETE FROM checkpoints WHERE thread_id LIKE 'core_agent_%'"),
            ]
            
            for description, query in queries:
                try:
                    result = await session.execute(text(query))
                    rows_affected = result.rowcount
                    print(f"  ✅ {description}: {rows_affected} rows deleted")
                    self.cleaned_tables.append(description)
                except Exception as e:
                    error_msg = f"❌ {description}: {e}"
                    print(f"  {error_msg}")
                    self.errors.append(error_msg)
            
            await session.commit()
    
    async def cleanup_all_tasks(self) -> None:
        """Clean up ALL tasks (for complete reset)"""
        print("\n🗑️ COMPLETE CLEANUP: Removing ALL tasks and related data...")
        
        # This is for when the kanban board is full and we want a complete reset
        cleanup_queries = [
            # Remove all child records first
            ("all_task_comments", "DELETE FROM task_comments"),
            ("all_chat_messages", "DELETE FROM chat_messages"),
            ("all_task_artifacts", "DELETE FROM task_artifact"),
            
            # Remove main entities
            ("all_tasks", "DELETE FROM tasks"),
            ("all_chats", "DELETE FROM chats"),
            ("all_artifacts", "DELETE FROM artifacts"),
            
            # Clean up checkpointer data
            ("all_checkpoint_writes", "DELETE FROM checkpoint_writes"),
            ("all_checkpoints", "DELETE FROM checkpoints"),
            ("all_checkpoint_blobs", "DELETE FROM checkpoint_blobs"),
        ]
        
        for table_name, query in cleanup_queries:
            async with db_manager.get_session() as session:
                try:
                    result = await session.execute(text(query))
                    rows_affected = result.rowcount
                    await session.commit()
                    print(f"  ✅ {table_name}: {rows_affected} rows deleted")
                    self.cleaned_tables.append(table_name)
                except Exception as e:
                    await session.rollback()
                    error_msg = f"❌ {table_name}: {e}"
                    print(f"  {error_msg}")
                    self.errors.append(error_msg)
    
    async def show_remaining_data(self) -> None:
        """Show what data remains after cleanup"""
        print("\n📊 Remaining data after cleanup:")
        await self.check_existing_test_data()
    
    def print_summary(self) -> None:
        """Print cleanup summary"""
        print("\n" + "="*60)
        print("🎯 CLEANUP SUMMARY")
        print("="*60)
        
        if self.cleaned_tables:
            print(f"✅ Successfully cleaned {len(self.cleaned_tables)} tables:")
            for table in self.cleaned_tables:
                print(f"   • {table}")
        
        if self.errors:
            print(f"\n❌ Encountered {len(self.errors)} errors:")
            for error in self.errors:
                print(f"   • {error}")
        
        if not self.errors:
            print(f"\n🎉 Cleanup completed successfully!")
        else:
            print(f"\n⚠️  Cleanup completed with {len(self.errors)} warnings/errors")


async def main():
    """Main cleanup function"""
    print("🚀 Starting comprehensive test data cleanup for Nova...")
    print("="*60)
    
    cleaner = TestDataCleaner()
    
    # Check current data
    await cleaner.check_existing_test_data()
    
    # Ask user what type of cleanup to perform
    print("\n" + "="*60)
    print("🔧 CLEANUP OPTIONS:")
    print("1. Clean test data only (recommended)")
    print("2. Clean ALL data (complete reset - WARNING: removes everything!)")
    print("3. Clean core agent data only")
    print("4. Just show current data (no cleanup)")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == "1":
        # Standard test cleanup
        await cleaner.cleanup_nova_business_data()
        await cleaner.cleanup_core_agent_data()
        await cleaner.cleanup_langgraph_data()
        await cleaner.cleanup_thread_specific_data()
    elif choice == "2":
        # Complete reset (dangerous!)
        confirm = input("⚠️  This will delete ALL data! Type 'YES' to confirm: ").strip()
        if confirm == "YES":
            await cleaner.cleanup_all_tasks()
        else:
            print("❌ Cleanup cancelled.")
            return
    elif choice == "3":
        # Core agent only
        await cleaner.cleanup_core_agent_data()
    elif choice == "4":
        # Just show data
        print("📊 Current data shown above.")
    else:
        print("❌ Invalid choice. Exiting.")
        return
    
    # Show results
    if choice in ["1", "2", "3"]:
        await cleaner.show_remaining_data()
        cleaner.print_summary()


if __name__ == "__main__":
    asyncio.run(main()) 