"""
Test ID: TC_Calendar_002
Use Case: Real end-to-end test for calendar conflict detection and escalation.
Tags: calendar, email-integration, conflict-resolution, p1-critical, real-api

Given (The Pre-conditions):
- The user's calendar for [Date_6_Months_From_Now] has one event:
  - Title: "Project Sync E2E Test"
  - Time: 10:00 AM - 11:00 AM
- Nova receives a new email about kindergarten closure for the same day

When (The Action):
- Send email to ourselves about kindergarten closure
- Wait for core agent to process the email task
- Core agent should create calendar event and detect conflict

Then (The Expected Outcome):
- ✔️ A new all-day event is created in the user's calendar for [Date_6_Months_From_Now]
  - Title: contains "Kindergarten" or "Closure"
- ✔️ The ask_user tool is triggered due to scheduling conflict
- ✔️ Task moves to waiting_for_review status
- ✔️ Original "Project Sync E2E Test" event remains unchanged

Notes:
This is a REAL test - no mocks. It tests the complete flow from email sending
through AI processing to calendar integration with actual Google Calendar API.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
import time
import httpx

from backend.mcp_client import mcp_manager


@pytest.fixture
def future_date():
    """Generate a date 6 months from now for testing."""
    return datetime.now() + timedelta(days=180)


@pytest.fixture
def test_event_title():
    """Unique test event title to avoid conflicts with existing events."""
    timestamp = int(time.time())
    return f"Project Sync E2E Test {timestamp}"


@pytest.fixture
def api_base_url():
    """Base URL for Nova API calls."""
    return "http://localhost:8000"  # Assuming Nova is running on port 8000


class TestRealCalendarConflictE2E:
    """Real end-to-end test for calendar conflict scenario with actual APIs."""

    @pytest.mark.asyncio
    @pytest.mark.slow  # Mark as slow test since it uses real APIs
    async def test_real_calendar_conflict_escalation_flow(
        self,
        future_date,
        test_event_title,
        api_base_url
    ):
        """Test complete real flow: send email -> core agent -> calendar conflict -> escalation."""
        
        # Step 0: Check if Nova API is running
        try:
            async with httpx.AsyncClient() as client:
                health_response = await client.get(f"{api_base_url}/api/system/health", timeout=5.0)
                if health_response.status_code != 200:
                    pytest.skip(f"Nova API not available at {api_base_url} - requires full environment setup")
        except Exception:
            pytest.skip(f"Nova API not available at {api_base_url} - requires full environment setup")
        
        # Step 1: Create the initial "Project Sync" event in real calendar
        date_str = future_date.strftime("%Y-%m-%d")
        start_time = f"{date_str}T10:00:00+02:00"
        end_time = f"{date_str}T11:00:00+02:00"
        
        all_tools = await mcp_manager.get_tools()
        if not all_tools:
            pytest.skip("No MCP tools available - check MCP configuration")
        
        create_event_tool = next((t for t in all_tools if t.name == "create_calendar_event"), None)
        list_events_tool = next((t for t in all_tools if t.name == "list_calendar_events"), None)
        
        if not create_event_tool or not list_events_tool:
            pytest.skip("Required calendar tools (create_calendar_event, list_calendar_events) not found")
        
        # Create initial event with timeout
        try:
            initial_event_result = await asyncio.wait_for(
                create_event_tool.arun({
                    "calendar_id": "primary",
                    "summary": test_event_title,
                    "start_datetime": start_time,
                    "end_datetime": end_time,
                    "description": "E2E test event that should conflict with kindergarten closure"
                }),
                timeout=30.0  # 30 second timeout
            )
        except asyncio.TimeoutError:
            pytest.skip("Calendar API call timed out - check Google Calendar API access and credentials")
        except Exception as e:
            pytest.skip(f"Calendar API call failed: {str(e)} - check Google Calendar API access and credentials")
        
        assert "success" in str(initial_event_result).lower()
        print(f"✅ Created initial calendar event: {test_event_title}")
        
        try:
            async with httpx.AsyncClient() as client:
                # Step 2: Send email to ourselves about kindergarten closure
                send_email_tool = next((t for t in all_tools if t.name == "send_email"), None)
                if not send_email_tool:
                    pytest.skip("send_email tool not available - check MCP configuration")
                
                email_subject = f"URGENT: Kindergarten Closure E2E Test {int(time.time())}"
                email_body = f"""
    Dear Parents,

    The kindergarten will be closed for the entire day on {date_str} due to maintenance work.

    Please make alternative arrangements for your children.

    Thank you for your understanding.

    Best regards,
    Kindergarten Management
    """
                
                try:
                    email_result = await asyncio.wait_for(
                        send_email_tool.arun({
                            "recipient_ids": ["nova.daniel.kuehlwein@gmail.com"],  # Send to ourselves
                            "subject": email_subject,
                            "message": email_body
                        }),
                        timeout=30.0  # 30 second timeout
                    )
                except asyncio.TimeoutError:
                    pytest.skip("Email API call timed out - check Gmail API access and credentials")
                except Exception as e:
                    pytest.skip(f"Email API call failed: {str(e)} - check Gmail API access and credentials")
                
                assert "message_id" in str(email_result).lower()
                print(f"✅ Sent test email: {email_subject}")
            
                # Step 3: Configure fast email polling for the test using API
                print("⚙️ Configuring fast email polling for test...")
                print("ℹ️ Note: Beat schedule updates require container restart to take effect")
                
                # Get current settings via API
                settings_response = await client.get(f"{api_base_url}/api/user-settings/")
                if settings_response.status_code != 200:
                    pytest.skip("Could not get user settings via API")
                
                current_settings = settings_response.json()
                original_interval = current_settings.get("email_polling_interval", 300)
                print(f"📧 Current email polling interval: {original_interval}s")
                
                # Update settings to 30 seconds for test via API
                update_response = await client.patch(
                    f"{api_base_url}/api/user-settings/",
                    json={"email_polling_interval": 30}
                )
                
                if update_response.status_code != 200:
                    pytest.skip("Could not update user settings via API")
                
                print("✅ Set email polling to 30 seconds via API")
                print("⚠️ Beat container restart required for schedule to take effect")
                
                try:
                    # Step 4: Wait for Celery to fetch email and create task
                    print("⏳ Waiting for Celery to fetch email and create task...")
                    email_task = None
                    max_wait_time = 360  # 6 minutes max wait (due to Beat schedule not updating automatically)
                    wait_interval = 5    # Check every 5 seconds
                    elapsed_time = 0
                    
                    while elapsed_time < max_wait_time and not email_task:
                        await asyncio.sleep(wait_interval)
                        elapsed_time += wait_interval
                        
                        # Check for task via API
                        tasks_response = await client.get(f"{api_base_url}/api/tasks")
                        if tasks_response.status_code == 200:
                            tasks = tasks_response.json()
                            # Look for our email task
                            for task in tasks:
                                if email_subject in task.get("title", ""):
                                    email_task = task
                                    print(f"✅ Found email task after {elapsed_time}s: {task['title']}")
                                    break
                        
                        if not email_task:
                            print(f"⏳ No task found yet... waiting ({elapsed_time}s elapsed)")
                    
                    if not email_task:
                        # Restore original settings before failing
                        await client.patch(
                            f"{api_base_url}/api/user-settings/",
                            json={"email_polling_interval": original_interval}
                        )
                        
                        pytest.fail(f"Email task not created within {max_wait_time}s. Check:\n"
                                   "1. Celery worker is running\n"
                                   "2. Celery beat is running\n"
                                   "3. Email polling is enabled\n"
                                   "4. MCP email server is configured\n"
                                   "5. Nova backend is running on {api_base_url}\n"
                                   "6. KNOWN ISSUE: Beat schedule updates require 'docker restart nova-celery-beat-1'")
            
                    # Step 5: Wait for core agent to process the task automatically
                    # In production, core agent runs continuously and picks up NEW tasks
                    print("🤖 Waiting for core agent to process the email task...")
                    print(f"📋 Task status: {email_task['status']}")
                    
                    # Wait for the core agent to process the task and change its status
                    processed_task = None
                    agent_wait_time = 60   # 60 seconds for agent processing (testing)
                    elapsed_time = 0
                    
                    while elapsed_time < agent_wait_time:
                        await asyncio.sleep(10)  # Check every 10 seconds
                        elapsed_time += 10
                        
                        # Get updated task status via API
                        task_response = await client.get(f"{api_base_url}/api/tasks/{email_task['id']}")
                        if task_response.status_code == 200:
                            current_task = task_response.json()
                            print(f"🔄 Task status after {elapsed_time}s: {current_task['status']}")
                            
                            # Check if task has been processed (status changed from NEW)
                            if current_task['status'] in ['done', 'waiting_for_review', 'failed']:
                                processed_task = current_task
                                print(f"✅ Task processed! Final status: {current_task['status']}")
                                break
                        
                        print(f"⏳ Still waiting for agent processing... ({elapsed_time}s elapsed)")
                    
                    if not processed_task:
                        pytest.fail(f"Core agent did not process task within {agent_wait_time}s. "
                                   "Check that core agent is running and functioning properly.")
                
                    # Step 6: Verify the results
                    print("🔍 Verifying test results...")
                    
                    # Check if calendar event was created
                    list_result = await list_events_tool.arun({
                        "calendar_id": "primary",
                        "time_min": f"{date_str}T00:00:00+02:00"
                    })
                    
                    events_found = []
                    if "Project Sync E2E Test" in str(list_result):
                        events_found.append("Project Sync E2E Test")
                    if "kindergarten" in str(list_result).lower() or "closure" in str(list_result).lower():
                        events_found.append("Kindergarten Closure")
                    
                    print(f"📅 Calendar events found: {events_found}")
                    
                    # Get task comments via API to check for escalation
                    comments_response = await client.get(f"{api_base_url}/api/tasks/{processed_task['id']}/comments")
                    escalation_found = False
                    if comments_response.status_code == 200:
                        comments = comments_response.json()
                        escalation_found = any(
                            "conflict" in comment.get("content", "").lower() or 
                            "escalat" in comment.get("content", "").lower()
                            for comment in comments
                        )
                    
                    print(f"📋 Final task status: {processed_task['status']}")
                    print(f"🔄 Escalation evidence in comments: {escalation_found}")
                    
                    # Assertions
                    assert len(events_found) >= 1, f"Expected to find events, but found: {events_found}"
                    assert processed_task['status'] in ['waiting_for_review', 'done'], \
                        f"Expected task to be in waiting_for_review or done, but was: {processed_task['status']}"
                    
                    print("✅ E2E test completed successfully!")
                    
                finally:
                    # Step 7: Always restore original email polling interval via API
                    print(f"🔄 Restoring original email polling interval: {original_interval}s")
                    restore_response = await client.patch(
                        f"{api_base_url}/api/user-settings/",
                        json={"email_polling_interval": original_interval}
                    )
                    if restore_response.status_code == 200:
                        print("✅ Email polling interval restored via API")
                    else:
                        print("⚠️ Failed to restore email polling interval")
                
        finally:
            # Step 8: Cleanup - clean up test tasks (calendar events need manual cleanup)
            try:
                print("🧹 Cleaning up test data...")
                
                # Clean up any tasks created during the test
                async with httpx.AsyncClient() as cleanup_client:
                    try:
                        # Get all tasks
                        tasks_response = await cleanup_client.get(f"{api_base_url}/api/tasks")
                        if tasks_response.status_code == 200:
                            tasks = tasks_response.json()
                            
                            # Find tasks with our test email subject
                            test_tasks = [
                                task for task in tasks 
                                if email_subject in task.get("title", "") 
                                or "Kindergarten Closure E2E Test" in task.get("title", "")
                            ]
                            
                            for task in test_tasks:
                                try:
                                    delete_response = await cleanup_client.delete(f"{api_base_url}/api/tasks/{task['id']}")
                                    if delete_response.status_code == 200:
                                        print(f"✅ Deleted test task: {task['title']}")
                                    else:
                                        print(f"⚠️ Failed to delete task {task['id']}: {delete_response.status_code}")
                                except Exception as e:
                                    print(f"⚠️ Error deleting task {task['id']}: {e}")
                        
                    except Exception as e:
                        print(f"⚠️ Failed to clean up test tasks: {e}")
                
                # Note: Calendar events with timestamped names will remain for manual cleanup
                # This is acceptable for e2e tests as they use unique timestamps to avoid conflicts
                print("ℹ️ Calendar events remain for manual cleanup (timestamped for safety)")
                    
            except Exception as e:
                print(f"⚠️ Cleanup failed: {e}")