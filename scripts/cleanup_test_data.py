#!/usr/bin/env python3
"""
Comprehensive Test Data Cleanup Script for Nova

This script cleans up all test data from both:
1. Nova's business tables (tasks, persons, projects, comments, etc.)
2. LangGraph checkpointer tables (used by chat and core agent)

It can be run manually or as part of test automation.
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
            # Check Nova business data
            queries = [
                ("Tasks with 'Test' in title", "SELECT COUNT(*) FROM tasks WHERE title LIKE '%Test%'"),
                ("Persons with test emails", "SELECT COUNT(*) FROM persons WHERE email LIKE '%test%'"),
                ("Projects with 'Test' in name", "SELECT COUNT(*) FROM projects WHERE name LIKE '%Test%'"),
                ("Task comments from core_agent", "SELECT COUNT(*) FROM task_comments WHERE author = 'core_agent'"),
                ("Agent status records", "SELECT COUNT(*) FROM agent_status"),
            ]
            
            # Check LangGraph checkpointer data
            langgraph_queries = [
                ("LangGraph checkpoints", "SELECT COUNT(*) FROM checkpoints"),
                ("LangGraph checkpoint writes", "SELECT COUNT(*) FROM checkpoint_writes"),
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
        """Clean up Nova's business data tables"""
        print("\n🧹 Cleaning Nova business data...")
        
        # Order matters for foreign key constraints - clean child tables first
        cleanup_queries = [
            # Comments first (references tasks)
            ("task_comments", "DELETE FROM task_comments WHERE author = 'core_agent' OR content LIKE '%Test%'"),
            
            # Many-to-many relationships (correct table names)
            ("task_person", "DELETE FROM task_person WHERE task_id IN (SELECT id FROM tasks WHERE title LIKE '%Test%')"),
            ("task_project", "DELETE FROM task_project WHERE task_id IN (SELECT id FROM tasks WHERE title LIKE '%Test%')"),
            
            # Main business entities (after removing foreign key references)
            ("tasks", "DELETE FROM tasks WHERE title LIKE '%Test%'"),
            ("persons", "DELETE FROM persons WHERE email LIKE '%test%'"),
            ("projects", "DELETE FROM projects WHERE name LIKE '%Test%'"),
            
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
            # Clean checkpoints for specific thread patterns
            queries = [
                ("checkpoint_writes for thread pattern", 
                 f"DELETE FROM checkpoint_writes WHERE task_id IN (SELECT task_id FROM checkpoints WHERE thread_id LIKE '{thread_pattern}')"),
                ("checkpoints for thread pattern", 
                 f"DELETE FROM checkpoints WHERE thread_id LIKE '{thread_pattern}'"),
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
            print("\n🎉 All test data cleaned successfully!")
        else:
            print(f"\n⚠️  Cleanup completed with {len(self.errors)} warnings/errors")


async def main():
    """Main cleanup function"""
    print("🚀 Starting comprehensive test data cleanup for Nova...")
    print("="*60)
    
    cleaner = TestDataCleaner()
    
    try:
        # Step 1: Check existing data
        await cleaner.check_existing_test_data()
        
        # Step 2: Clean Nova business data
        await cleaner.cleanup_nova_business_data()
        
        # Step 3: Clean LangGraph checkpointer data
        await cleaner.cleanup_langgraph_data()
        
        # Step 4: Clean specific core agent thread data
        await cleaner.cleanup_thread_specific_data()
        
        # Step 5: Show remaining data
        await cleaner.show_remaining_data()
        
        # Step 6: Print summary
        cleaner.print_summary()
        
    except Exception as e:
        print(f"\n💥 Fatal error during cleanup: {e}")
        return 1
    
    finally:
        # Clean up database connections
        try:
            if hasattr(db_manager, 'engine') and db_manager.engine:
                await db_manager.engine.dispose()
        except Exception as e:
            print(f"Warning: Error disposing database engine: {e}")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 