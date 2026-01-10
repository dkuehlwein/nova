"""
Test ID: TC_Calendar_002
Use Case: Real end-to-end test for calendar conflict detection and escalation.
Tags: calendar, email-integration, conflict-resolution, p1-critical, real-api

Given (The Pre-conditions):
- The user's calendar for [Tomorrow] has one event:
  - Title: "Project Sync E2E Test"
  - Time: 10:00 AM - 11:00 AM
- Nova receives a new task about kindergarten closure for the same day

When (The Action):
- Create task about kindergarten closure (fast mode) OR send email (slow mode)
- Wait for core agent to process the task
- Core agent should create calendar event, detect conflict, and call ask_user tool

Then (The Expected Outcome):
- ✔️ The ask_user tool is triggered due to scheduling conflict (verified in chat logs)
- ✔️ Task moves to needs_review status
- ✔️ Original "Project Sync E2E Test" event remains unchanged

Notes:
This is a REAL test - no mocks. It tests the complete flow with actual APIs.

PREREQUISITE: Calendar tools MUST be in the allow list in configs/tool_permissions.yaml:
  - gcal_create_event
  - gcal_list_events
  - gcal_delete_event
  - gcal_update_event

Otherwise, tool approval will intercept the calendar tool call BEFORE conflict
detection can occur, causing the test to fail.

There are two modes:
- FAST (default): Creates task directly via API, bypasses email entirely
- SLOW (with email): Sends email, waits for Celery/ADR-019 staleness (15+ minutes)
"""

import asyncio
import os
import pytest
from datetime import datetime, timedelta
import time
import httpx
import yaml

from backend.mcp_client import mcp_manager


@pytest.fixture
def test_date():
    """Generate tomorrow's date for testing."""
    return datetime.now() + timedelta(days=1)


@pytest.fixture
def test_event_title():
    """Unique test event title to avoid conflicts with existing events."""
    timestamp = int(time.time())
    return f"Project Sync E2E Test {timestamp}"


@pytest.fixture
def api_base_url():
    """Base URL for Nova API calls."""
    return "http://localhost:8000"  # Assuming Nova is running on port 8000


def check_calendar_tools_allowed():
    """
    Check if calendar tools are in the allow list.

    Returns tuple (all_allowed: bool, missing_tools: list)
    """
    required_tools = ["gcal_create_event", "gcal_list_events", "gcal_delete_event"]

    try:
        config_path = os.path.join(
            os.path.dirname(__file__),
            "../../configs/tool_permissions.yaml"
        )
        with open(config_path) as f:
            config = yaml.safe_load(f)

        allowed = config.get("permissions", {}).get("allow", [])
        missing = [t for t in required_tools if t not in allowed]
        return len(missing) == 0, missing
    except Exception as e:
        return False, [f"Error reading config: {e}"]


class TestRealCalendarConflictE2E:
    """Real end-to-end test for calendar conflict scenario with actual APIs."""

    @pytest.mark.asyncio
    async def test_calendar_conflict_fast(
        self,
        test_date,
        test_event_title,
        api_base_url
    ):
        """
        FAST test: Calendar conflict detection with direct task creation.

        This test bypasses email entirely for faster execution (~2-5 minutes).
        Creates a task directly via API and verifies the agent:
        1. Creates a calendar event
        2. Detects conflict with existing events
        3. Calls ask_user with conflict message
        4. Moves task to needs_review status
        """
        # =============================================================================
        # PREREQUISITE CHECK: Calendar tools must be allowed
        # =============================================================================
        tools_allowed, missing = check_calendar_tools_allowed()
        if not tools_allowed:
            pytest.fail(
                f"Calendar tools not in allow list! Missing: {missing}\n"
                "Add these to configs/tool_permissions.yaml under permissions.allow:\n"
                "  - gcal_create_event\n"
                "  - gcal_list_events\n"
                "  - gcal_delete_event\n"
                "\n"
                "Without this, tool approval will intercept before conflict detection!"
            )

        # =============================================================================
        # STEP 0: ENVIRONMENT SETUP
        # =============================================================================
        try:
            async with httpx.AsyncClient() as client:
                health_response = await client.get(f"{api_base_url}/health", timeout=5.0)
                if health_response.status_code != 200:
                    pytest.skip(f"Nova API not available at {api_base_url}")
        except Exception:
            pytest.skip(f"Nova API not available at {api_base_url}")

        # Check Core Agent is running
        try:
            async with httpx.AsyncClient() as client:
                core_health = await client.get("http://localhost:8001/health", timeout=5.0)
                if core_health.status_code != 200:
                    pytest.skip("Core Agent not available at http://localhost:8001")
                core_status = core_health.json()
                print(f"Core Agent status: {core_status.get('agent_status', 'unknown')}")
        except Exception:
            pytest.skip("Core Agent not available at http://localhost:8001")

        # =============================================================================
        # STEP 1: CALENDAR SETUP - Create initial event to conflict with
        # =============================================================================
        date_str = test_date.strftime("%Y-%m-%d")
        start_time = f"{date_str}T10:00:00+02:00"
        end_time = f"{date_str}T11:00:00+02:00"

        all_tools = await mcp_manager.get_tools()
        if not all_tools:
            pytest.skip("No MCP tools available")

        create_event_tool = next((t for t in all_tools if t.name == "gcal_create_event"), None)
        list_events_tool = next((t for t in all_tools if t.name == "gcal_list_events"), None)
        delete_event_tool = next((t for t in all_tools if t.name == "gcal_delete_event"), None)

        if not create_event_tool or not list_events_tool:
            pytest.skip("Required calendar tools not found")

        # Create initial event
        try:
            initial_event_result = await asyncio.wait_for(
                create_event_tool.arun({
                    "calendar_id": "primary",
                    "summary": test_event_title,
                    "start_datetime": start_time,
                    "end_datetime": end_time,
                    "description": "E2E test event for conflict detection"
                }),
                timeout=30.0
            )
            print(f"Created initial event: {test_event_title}")
        except Exception as e:
            pytest.skip(f"Calendar API failed: {e}")

        # Extract event ID for cleanup
        initial_event_id = None
        if hasattr(initial_event_result, 'get'):
            initial_event_id = initial_event_result.get('id')

        task_id = None
        timestamp = int(time.time())

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # =============================================================================
                # STEP 2: CREATE TASK DIRECTLY (bypasses email and ADR-019 staleness)
                # =============================================================================
                task_data = {
                    "title": f"Kindergarten Closure E2E - {date_str} - {timestamp}",
                    "description": f"""URGENT: Kindergarten Closure Notice

Dear Parents,

IMPORTANT NOTICE: The kindergarten will be CLOSED ALL DAY on {date_str}.

This is a FULL DAY closure from 8:00 AM until 6:00 PM due to emergency maintenance.
Please make alternative childcare arrangements for your children.

Date: {date_str}
Duration: Full day (8:00 AM - 6:00 PM)
Reason: Emergency maintenance

Best regards,
Kindergarten Management""",
                    "status": "new"
                }

                response = await client.post(f"{api_base_url}/api/tasks", json=task_data)
                if response.status_code != 200:
                    pytest.fail(f"Failed to create task: {response.status_code} - {response.text}")

                task = response.json()
                task_id = task['id']
                print(f"Created task: {task['title']} (ID: {task_id[:8]}...)")

                # =============================================================================
                # STEP 3: WAIT FOR CORE AGENT TO PROCESS
                # =============================================================================
                print("Waiting for Core Agent to process task...")
                max_wait = 300  # 5 minutes
                poll_interval = 10

                processed_task = None
                for i in range(max_wait // poll_interval):
                    await asyncio.sleep(poll_interval)
                    elapsed = (i + 1) * poll_interval

                    task_resp = await client.get(f"{api_base_url}/api/tasks/{task_id}")
                    if task_resp.status_code != 200:
                        continue

                    current_task = task_resp.json()
                    status = current_task['status']
                    print(f"[{elapsed:3d}s] Task status: {status}")

                    if status == 'needs_review':
                        processed_task = current_task
                        print(f"Task processed! Final status: {status}")
                        break
                    elif status in ['completed', 'failed']:
                        pytest.fail(f"Task ended with unexpected status: {status}")

                if not processed_task:
                    pytest.fail(
                        f"Task not processed within {max_wait}s. "
                        "Check Core Agent is running and not stuck."
                    )

                # =============================================================================
                # STEP 4: VERIFY ask_user WAS CALLED WITH CONFLICT MESSAGE
                # =============================================================================
                print("Verifying ask_user was called with conflict message...")

                conv_resp = await client.get(
                    f"{api_base_url}/chat/conversations/core_agent_task_{task_id}/task-data"
                )

                if conv_resp.status_code != 200:
                    pytest.fail(f"Could not get conversation: {conv_resp.status_code}")

                data = conv_resp.json()
                messages = data.get('messages', [])

                ask_user_called = False
                conflict_mentioned = False
                question_text = ""

                for msg in messages:
                    if msg.get('tool_calls'):
                        for tc in msg['tool_calls']:
                            tool_name = tc.get('tool', tc.get('name', ''))
                            if tool_name == 'ask_user':
                                ask_user_called = True
                                args = tc.get('args', {})
                                if isinstance(args, str):
                                    import json
                                    try:
                                        args = json.loads(args)
                                    except:
                                        pass
                                question_text = args.get('question', str(args)) if isinstance(args, dict) else str(args)
                                if 'conflict' in question_text.lower():
                                    conflict_mentioned = True

                # Also check pending_escalation
                if data.get('pending_escalation'):
                    ask_user_called = True
                    question_text = data['pending_escalation'].get('question', '')
                    if 'conflict' in question_text.lower():
                        conflict_mentioned = True

                print(f"ask_user called: {ask_user_called}")
                print(f"Conflict mentioned: {conflict_mentioned}")
                if question_text:
                    print(f"Question: {question_text[:200]}...")

                # =============================================================================
                # ASSERTIONS
                # =============================================================================
                assert processed_task['status'] == 'needs_review', \
                    f"Expected needs_review, got {processed_task['status']}"

                assert ask_user_called, (
                    "CRITICAL FAILURE: ask_user was NOT called!\n"
                    "The agent MUST call ask_user when there's a calendar conflict.\n"
                    "Check:\n"
                    "1. Calendar tools are in allow list (tool_permissions.yaml)\n"
                    "2. Agent prompt instructs to check for conflicts\n"
                    "3. Calendar API returned conflict information"
                )

                assert conflict_mentioned, (
                    f"ask_user was called but 'conflict' not in question.\n"
                    f"Question was: {question_text[:300]}"
                )

                print("All assertions passed!")

        finally:
            # =============================================================================
            # CLEANUP
            # =============================================================================
            print("Cleaning up test data...")

            # Delete initial calendar event
            if initial_event_id and delete_event_tool:
                try:
                    await delete_event_tool.arun({
                        "calendar_id": "primary",
                        "event_id": initial_event_id
                    })
                    print(f"Deleted initial event: {test_event_title}")
                except Exception as e:
                    print(f"Warning: Could not delete initial event: {e}")

            # Delete test task
            if task_id:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.delete(f"{api_base_url}/api/tasks/{task_id}")
                        print(f"Deleted test task: {task_id[:8]}...")
                except Exception as e:
                    print(f"Warning: Could not delete task: {e}")

    @pytest.mark.asyncio
    @pytest.mark.slow  # Mark as slow test since it uses email path
    async def test_calendar_conflict_with_email(
        self,
        test_date,
        test_event_title,
        api_base_url
    ):
        """
        SLOW test: Full flow including email path.

        This test uses the complete email -> Celery -> task -> agent flow.
        Takes 15-20+ minutes due to ADR-019 email staleness waiting period.

        Use test_calendar_conflict_fast for quicker feedback.
        """
        # =============================================================================
        # PREREQUISITE CHECK: Calendar tools must be allowed
        # =============================================================================
        tools_allowed, missing = check_calendar_tools_allowed()
        if not tools_allowed:
            pytest.fail(
                f"Calendar tools not in allow list! Missing: {missing}\n"
                "Add these to configs/tool_permissions.yaml under permissions.allow"
            )

        # =============================================================================
        # STEP 0: ENVIRONMENT SETUP - Check if Nova API is running
        # =============================================================================
        try:
            async with httpx.AsyncClient() as client:
                health_response = await client.get(f"{api_base_url}/health", timeout=5.0)
                if health_response.status_code != 200:
                    pytest.skip(f"Nova API not available at {api_base_url} - requires full environment setup")
        except Exception:
            pytest.skip(f"Nova API not available at {api_base_url} - requires full environment setup")
        
        # =============================================================================
        # STEP 1: CALENDAR SETUP - Create initial "Project Sync" event
        # =============================================================================
        date_str = test_date.strftime("%Y-%m-%d")
        start_time = f"{date_str}T10:00:00+02:00"
        end_time = f"{date_str}T11:00:00+02:00"
        
        all_tools = await mcp_manager.get_tools()
        if not all_tools:
            pytest.skip("No MCP tools available - check MCP configuration")
        
        # Use prefixed tool names per ADR-019
        create_event_tool = next((t for t in all_tools if t.name == "gcal_create_event"), None)
        list_events_tool = next((t for t in all_tools if t.name == "gcal_list_events"), None)

        if not create_event_tool or not list_events_tool:
            pytest.skip("Required calendar tools (gcal_create_event, gcal_list_events) not found")
        
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
        
        # Store event ID for cleanup
        initial_event_id = None
        if hasattr(initial_event_result, 'get') and 'id' in initial_event_result:
            initial_event_id = initial_event_result.get('id')
        
        try:
            async with httpx.AsyncClient() as client:
                # =============================================================================
                # STEP 2: EMAIL TRIGGER - Send kindergarten closure email
                # =============================================================================
                # Use prefixed tool name per ADR-019
                send_email_tool = next((t for t in all_tools if t.name == "gmail_send_email"), None)
                if not send_email_tool:
                    pytest.skip("gmail_send_email tool not available - check MCP configuration")
                
                email_subject = f"URGENT: Kindergarten Closure E2E Test {int(time.time())}"
                email_body = f"""
Dear Parents,

IMPORTANT NOTICE: The kindergarten will be CLOSED ALL DAY on {date_str} due to maintenance work.

This is a FULL DAY closure from morning until evening. Please make alternative arrangements for your children for the entire day.

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
                
                # =============================================================================
                # STEP 3: TASK CREATION - Wait for email processing and task creation
                # =============================================================================
                print("⏳ Waiting for Celery to fetch email and create task...")
                email_task = None
                max_wait_time = 400  # 3 minutes max wait
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
                    pytest.fail(f"Email task not created within {max_wait_time}s. Check:\n"
                               "1. Celery worker is running\n"
                               "2. Celery beat is running\n"
                               "3. Email polling is enabled\n"
                               "4. MCP email server is configured\n"
                               f"5. Nova backend is running on {api_base_url}")
            
                # =============================================================================
                # STEP 4: CORE AGENT PROCESSING - Wait for agent to process the task
                # =============================================================================
                # Core agent runs continuously and picks up NEW tasks
                print("🤖 Waiting for core agent to process the email task...")
                print(f"📋 Task status: {email_task['status']}")
                
                # Wait for the core agent to process the task and change its status
                processed_task = None
                agent_wait_time = 360  # 5 minutes for agent processing
                elapsed_time = 0
                
                while elapsed_time < agent_wait_time:
                    await asyncio.sleep(10)  # Check every 10 seconds
                    elapsed_time += 10
                    
                    # Get updated task status via API
                    task_response = await client.get(f"{api_base_url}/api/tasks/{email_task['id']}")
                    if task_response.status_code == 200:
                        current_task = task_response.json()
                        print(f"🔄 Task status after {elapsed_time}s: {current_task['status']}")
                        
                        # Check if task has been processed (status changed to needs_review)
                        if current_task['status'] in ['needs_review']:
                            processed_task = current_task
                            print(f"✅ Task processed! Final status: {current_task['status']}")
                            break
                    
                    print(f"⏳ Still waiting for agent processing... ({elapsed_time}s elapsed)")
                
                if not processed_task:
                    pytest.fail(f"Core agent did not process task within {agent_wait_time}s. "
                               "Check that core agent is running and functioning properly.")
                
                # =============================================================================
                # STEP 5: VERIFICATION - Check results and ask_user tool usage
                # =============================================================================
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
                    
                # Check for ask_user tool usage in task chat
                print("🔍 Checking for ask_user tool usage in task chat...")
                task_chat_response = await client.get(f"{api_base_url}/chat/conversations/core_agent_task_{processed_task['id']}/task-data")
                ask_user_called = False
                escalation_found = False
                if task_chat_response.status_code == 200:
                    task_chat_data = task_chat_response.json()
                    messages = task_chat_data.get('messages', [])
                    # Look for ask_user tool calls in the conversation
                    for message in messages:
                        if message.get('tool_calls'):
                            for tool_call in message['tool_calls']:
                                if tool_call.get('tool') == 'ask_user' and 'conflict' in tool_call.get('args', {}).get('question', '').lower():
                                    ask_user_called = True
                                    break
                        if ask_user_called:
                            break
                    
                    # Check if there's a pending escalation
                    if task_chat_data.get('pending_escalation'):
                        escalation_found = True
                        ask_user_called = True  # If there's pending escalation, ask_user was definitely called
                
                # Note: escalation_found is now set above when checking task chat
                
                # Check memory entries for conflict information
                # Search by date to find memories created during task processing
                await asyncio.sleep(60)
                memory_response = await client.post(f"{api_base_url}/api/memory/search", 
                                                  json={"query": date_str})
                memory_entry_found = False
                if memory_response.status_code == 200:
                    memory_results = memory_response.json()
                    results = memory_results.get('results', [])
                    memory_entry_found = len(results) > 0
                    
                    if memory_entry_found:
                        print(f"🧠 Found {len(results)} memories for date {date_str}")
                        for result in results[:3]:  # Show first 3 results
                            print(f"  - {result.get('fact', result)}")
                    else:
                        print(f"🧠 No memory entries found for date {date_str}")
                else:
                    print(f"🧠 Memory search failed with status {memory_response.status_code}")
                    
                print(f"📋 Final task status: {processed_task['status']}")
                print(f"🎆 Ask_user tool called: {ask_user_called}")
                print(f"🔄 Escalation evidence in comments: {escalation_found}")
                print(f"🧠 Memory entry created: {memory_entry_found}")
                
                # Assertions
                assert len(events_found) >= 1, f"Expected to find events, but found: {events_found}"
                assert processed_task['status'] == 'needs_review', \
                    f"Expected task to be in needs_review, but was: {processed_task['status']}"
                assert ask_user_called, "Expected ask_user tool to be called due to calendar conflict"
                assert memory_entry_found, f"Expected memory entry to be created about the conflict for date {date_str}"
                
                # Test completed successfully
                print("✅ All verifications passed!")
  
        finally:
            # =============================================================================
            # STEP 6: CLEANUP - Clean up test data
            # =============================================================================
            #"""
            try:
                print("🧹 Cleaning up test data...")
                
                # Clean up calendar events first
                if initial_event_id:
                    try:
                        delete_tool = next((t for t in all_tools if t.name == "gcal_delete_event"), None)
                        if delete_tool:
                            await delete_tool.arun({
                                "calendar_id": "primary",
                                "event_id": initial_event_id
                            })
                            print(f"✅ Deleted initial calendar event: {test_event_title}")
                    except Exception as e:
                        print(f"⚠️ Failed to delete initial calendar event: {e}")
                
                # Try to find and delete kindergarten event
                try:
                    list_result = await list_events_tool.arun({
                        "calendar_id": "primary",
                        "time_min": f"{date_str}T00:00:00+02:00"
                    })
                    
                    # Parse the result to find kindergarten event ID
                    kindergarten_event_id = None
                    if hasattr(list_result, 'get') and 'items' in list_result:
                        for event in list_result.get('items', []):
                            summary = event.get('summary', '').lower()
                            if 'kindergarten' in summary or 'closure' in summary:
                                kindergarten_event_id = event.get('id')
                                break
                    
                    if kindergarten_event_id:
                        try:
                            delete_tool = next((t for t in all_tools if t.name == "gcal_delete_event"), None)
                            if delete_tool:
                                await delete_tool.arun({
                                    "calendar_id": "primary",
                                    "event_id": kindergarten_event_id
                                })
                                print(f"✅ Deleted kindergarten event: {kindergarten_event_id}")
                            else:
                                print("⚠️ delete_calendar_event tool not found")
                        except Exception as e:
                            print(f"⚠️ Failed to delete kindergarten event: {e}")
                    else:
                        print("🔍 No kindergarten event found to delete")
                        
                except Exception as e:
                    print(f"⚠️ Failed to check for kindergarten event: {e}")
                
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
                
                print("✅ Cleanup completed")
                    
            except Exception as e:
                print(f"⚠️ Cleanup failed: {e}")
            #"""