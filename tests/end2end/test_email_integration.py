#!/usr/bin/env python3
"""
Manual test script for email integration with real Google MCP server.

This script tests the basic email integration functionality:
1. Connects to the configured MCP server
2. Fetches a small number of emails  
3. Shows metadata extraction works
4. Doesn't create actual tasks (safer for testing)
"""

import asyncio
import os
import sys
import traceback

# Add backend to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from tasks.email_processor import EmailProcessor
from config import settings
from utils.logging import get_logger

logger = get_logger("email_integration_test")


async def test_email_connection():
    """Test basic email MCP connection."""
    print("🔍 Testing Email MCP Connection...")
    
    processor = EmailProcessor()
    
    try:
        # Test getting email tools
        tools = await processor._get_email_tools()
        print(f"✅ Found {len(tools)} email tools: {list(tools.keys())}")
        
        # Test basic health check
        if "list_labels" in tools:
            await processor._call_email_tool("list_labels")
            print("✅ Email API health check passed")
        else:
            print("⚠️  list_labels tool not available")
        
        return True
        
    except Exception as e:
        print(f"❌ Email connection failed: {e}")
        traceback.print_exc()
        return False
    
    finally:
        await processor.close()


async def test_email_fetching():
    """Test fetching emails (without creating tasks)."""
    print("\n📧 Testing Email Fetching...")
    
    # Temporarily override settings for safe testing
    original_email_enabled = settings.EMAIL_ENABLED
    original_create_tasks = settings.EMAIL_CREATE_TASKS
    original_max_fetch = settings.EMAIL_MAX_PER_FETCH
    
    try:
        # Enable email processing but disable task creation for safety
        settings.EMAIL_ENABLED = True
        settings.EMAIL_CREATE_TASKS = False  # Don't create tasks during test
        settings.EMAIL_MAX_PER_FETCH = 3     # Limit to 3 emails for testing
        
        processor = EmailProcessor()
        
        print(f"📬 Fetching max {settings.EMAIL_MAX_PER_FETCH} emails from {settings.EMAIL_LABEL_FILTER}...")
        emails = await processor.fetch_new_emails()
        
        print(f"✅ Successfully fetched {len(emails)} emails")
        
        if emails:
            print("\n📋 Email samples:")
            for i, email in enumerate(emails[:2]):  # Show first 2 emails
                try:
                    metadata = processor._extract_email_metadata(email)
                    body_preview = processor._extract_email_body(email)[:100]
                    
                    print(f"\n  Email {i+1}:")
                    print(f"    ID: {metadata.email_id}")
                    print(f"    Subject: {metadata.subject}")
                    print(f"    From: {metadata.sender}")
                    print(f"    To: {metadata.recipient}")
                    print(f"    Labels: {metadata.labels}")
                    print(f"    Has Attachments: {metadata.has_attachments}")
                    print(f"    Body Preview: {body_preview}...")
                    
                except Exception as e:
                    print(f"    ❌ Error processing email {i+1}: {e}")
        
        await processor.close()
        return True
        
    except Exception as e:
        print(f"❌ Email fetching failed: {e}")
        traceback.print_exc()
        return False
    
    finally:
        # Restore original settings
        settings.EMAIL_ENABLED = original_email_enabled
        settings.EMAIL_CREATE_TASKS = original_create_tasks
        settings.EMAIL_MAX_PER_FETCH = original_max_fetch


async def test_task_creation_simulation():
    """Test task creation simulation (without actually creating tasks)."""
    print("\n🏗️  Testing Task Creation Simulation...")
    
    processor = EmailProcessor()
    
    try:
        # Create a fake email for testing
        fake_email = {
            "id": "test_email_simulation",
            "threadId": "test_thread_simulation", 
            "labelIds": ["INBOX"],
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Integration Email"},
                    {"name": "From", "value": "test@example.com"},
                    {"name": "To", "value": "nova@example.com"},
                    {"name": "Date", "value": "Wed, 06 Jun 2025 10:00:00 +0000"}
                ],
                "mimeType": "text/plain",
                "body": {
                    "data": "VGVzdCBlbWFpbCBmb3IgaW50ZWdyYXRpb24="  # Base64 "Test email for integration"
                }
            }
        }
        
        # Test metadata extraction
        metadata = processor._extract_email_metadata(fake_email)
        print(f"✅ Metadata extraction: {metadata.subject} from {metadata.sender}")
        
        # Test body extraction
        body = processor._extract_email_body(fake_email)
        print(f"✅ Body extraction: {body}")
        
        # Test task description formatting
        description = processor._format_task_description(metadata, body)
        print(f"✅ Task description generated ({len(description)} chars)")
        
        await processor.close()
        return True
        
    except Exception as e:
        print(f"❌ Task creation simulation failed: {e}")
        traceback.print_exc()
        return False


async def main():
    """Run all email integration tests."""
    print("🚀 Nova Email Integration Test")
    print("=" * 50)
    
    print(f"📝 Configuration:")
    print(f"   Email Enabled: {settings.EMAIL_ENABLED}")
    print(f"   Create Tasks: {settings.EMAIL_CREATE_TASKS}")
    print(f"   MCP Server: {settings.EMAIL_MCP_SERVER}")
    print(f"   Label Filter: {settings.EMAIL_LABEL_FILTER}")
    print(f"   Max Per Fetch: {settings.EMAIL_MAX_PER_FETCH}")
    
    results = []
    
    # Test 1: Basic connection
    results.append(await test_email_connection())
    
    # Test 2: Email fetching
    results.append(await test_email_fetching())
    
    # Test 3: Task creation simulation
    results.append(await test_task_creation_simulation())
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("🎉 All email integration tests passed!")
        print("✨ The email integration is working correctly with the Google MCP server.")
    else:
        print("❌ Some tests failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 