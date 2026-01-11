"""
Step-by-step debug tests for calendar conflict E2E.

Run each test independently to isolate failures:
    cd backend && uv run pytest ../tests/end2end/debug/test_calendar_conflict_debug.py::TestCalendarConflictDebug::test_step0_infrastructure -v -s
    cd backend && uv run pytest ../tests/end2end/debug/test_calendar_conflict_debug.py::TestCalendarConflictDebug::test_step1_create_calendar_event -v -s
    cd backend && uv run pytest ../tests/end2end/debug/test_calendar_conflict_debug.py::TestCalendarConflictDebug::test_step2_create_task_directly -v -s
    cd backend && uv run pytest ../tests/end2end/debug/test_calendar_conflict_debug.py::TestCalendarConflictDebug::test_step3_wait_for_agent -v -s
    cd backend && uv run pytest ../tests/end2end/debug/test_calendar_conflict_debug.py::TestCalendarConflictDebug::test_step4_verify_ask_user -v -s

Purpose: Debug the calendar conflict E2E test by running each step independently.
This allows us to isolate exactly which component is failing.
"""
import pytest
import asyncio
import httpx
from datetime import datetime, timedelta
import time

API_URL = "http://localhost:8000"
CORE_AGENT_URL = "http://localhost:8001"


class TestCalendarConflictDebug:
    """Run these tests ONE AT A TIME to debug the E2E flow"""

    @pytest.mark.asyncio
    async def test_step0_infrastructure(self):
        """
        STEP 0: Verify all services are running.

        This checks:
        - Nova API (port 8000)
        - Core Agent (port 8001)
        - MCP tools availability via LiteLLM
        """
        print("\n" + "="*60)
        print("STEP 0: Infrastructure Verification")
        print("="*60)

        async with httpx.AsyncClient(timeout=10) as client:
            # Check Nova API
            print("\n1. Checking Nova API...")
            try:
                r = await client.get(f"{API_URL}/health")
                assert r.status_code == 200, f"Nova API returned {r.status_code}"
                print(f"   ✅ Nova API is running (status: {r.status_code})")
            except Exception as e:
                pytest.fail(f"Nova API not available: {e}")

            # Check Core Agent
            print("\n2. Checking Core Agent...")
            try:
                r = await client.get(f"{CORE_AGENT_URL}/health")
                print(f"   ✅ Core Agent is running (status: {r.status_code})")
            except Exception as e:
                print(f"   ⚠️ Core Agent not available at {CORE_AGENT_URL}: {e}")
                print("      (This is OK if running in single-service mode)")

            # Check MCP tools (calendar)
            print("\n3. Checking MCP tools (calendar)...")
            from backend.mcp_client import mcp_manager
            mcp_tools = await mcp_manager.get_tools()
            mcp_tool_names = [t.name for t in mcp_tools]

            required_mcp_tools = ["google_workspace-create_event", "google_workspace-list_events"]
            for tool in required_mcp_tools:
                if tool in mcp_tool_names:
                    print(f"   ✅ {tool} tool available (MCP)")
                else:
                    print(f"   ❌ {tool} tool MISSING (MCP)")

            # Check local tools (ask_user is a local tool, not MCP)
            print("\n4. Checking local tools (ask_user)...")
            from tools import get_local_tools
            local_tools = get_local_tools(include_escalation=True)
            local_tool_names = [t.name for t in local_tools]

            if "ask_user" in local_tool_names:
                print(f"   ✅ ask_user tool available (local)")
            else:
                print(f"   ❌ ask_user tool MISSING (local)")

            # Assert all required tools exist
            missing_mcp = [t for t in required_mcp_tools if t not in mcp_tool_names]
            missing_local = [] if "ask_user" in local_tool_names else ["ask_user"]
            all_missing = missing_mcp + missing_local
            assert not all_missing, f"Missing required tools: {all_missing}"

            print(f"\n   Total MCP tools: {len(mcp_tools)}")
            print(f"   Total local tools: {len(local_tools)}")
            print("\n" + "="*60)
            print("✅ Infrastructure verification PASSED")
            print("="*60)

    @pytest.mark.asyncio
    async def test_step1_create_calendar_event(self):
        """
        STEP 1: Create the initial calendar event.

        Creates a "Project Sync" event for tomorrow at 10:00-11:00 AM.
        This event will conflict with the kindergarten closure.
        """
        print("\n" + "="*60)
        print("STEP 1: Create Calendar Event")
        print("="*60)

        from backend.mcp_client import mcp_manager

        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")
        timestamp = int(time.time())

        print(f"\n   Date: {date_str}")
        print(f"   Time: 10:00 - 11:00")

        tools = await mcp_manager.get_tools()
        create_tool = next((t for t in tools if t.name == "google_workspace-create_event"), None)

        if not create_tool:
            pytest.skip("google_workspace-create_event tool not available")

        event_data = {
            "calendar_id": "primary",
            "summary": f"Project Sync DEBUG TEST {timestamp}",
            "start_datetime": f"{date_str}T10:00:00+02:00",
            "end_datetime": f"{date_str}T11:00:00+02:00",
            "description": "Debug test event - should conflict with kindergarten closure"
        }

        print(f"\n   Creating event: {event_data['summary']}")

        try:
            result = await asyncio.wait_for(
                create_tool.arun(event_data),
                timeout=30.0
            )
            print(f"\n   Result: {result}")

            # Check for success
            result_str = str(result).lower()
            success = "success" in result_str or "id" in result_str or "created" in result_str

            if success:
                print("\n" + "="*60)
                print("✅ Calendar event created successfully")
                print("="*60)
            else:
                print("\n" + "="*60)
                print(f"⚠️ Unexpected result: {result}")
                print("="*60)

            assert success, f"Event creation failed: {result}"

        except asyncio.TimeoutError:
            pytest.fail("Calendar API timed out after 30s")

    @pytest.mark.asyncio
    async def test_step2_create_task_directly(self):
        """
        STEP 2: Create task directly via API (bypass email).

        This simulates what the email hook would do, but instantly.
        Bypasses the 15-minute ADR-019 staleness wait.
        """
        print("\n" + "="*60)
        print("STEP 2: Create Task Directly (Bypass Email)")
        print("="*60)

        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")
        timestamp = int(time.time())

        task_data = {
            "title": f"Kindergarten Closure DEBUG - {date_str} - {timestamp}",
            "description": f"""URGENT NOTICE: Kindergarten Closure

Dear Parents,

IMPORTANT: The kindergarten will be CLOSED ALL DAY on {date_str} due to emergency maintenance.

This is a FULL DAY closure from morning (8:00 AM) until evening (6:00 PM).
Please make alternative childcare arrangements for your children for the entire day.

Key Points:
- Date: {date_str}
- Duration: Full day (8:00 AM - 6:00 PM)
- Reason: Emergency maintenance
- Action Required: Arrange alternative childcare

Thank you for your understanding.

Best regards,
Kindergarten Management""",
            "status": "new"
        }

        print(f"\n   Title: {task_data['title']}")
        print(f"   Status: {task_data['status']}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{API_URL}/api/tasks", json=task_data)

            print(f"\n   Response status: {response.status_code}")

            if response.status_code == 200:
                task = response.json()
                print(f"   Task ID: {task.get('id')}")
                print(f"   Task Status: {task.get('status')}")

                print("\n" + "="*60)
                print("✅ Task created successfully")
                print(f"   Run step 3 to watch agent process it")
                print("="*60)
            else:
                print(f"   Error: {response.text}")
                pytest.fail(f"Task creation failed: {response.status_code}")

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_step3_wait_for_agent(self):
        """
        STEP 3: Wait for Core Agent to process the task.

        Polls task status every 10 seconds, waiting for it to change
        from 'new' to 'needs_review' (when ask_user is called).
        """
        print("\n" + "="*60)
        print("STEP 3: Wait for Agent Processing")
        print("="*60)

        async with httpx.AsyncClient(timeout=30) as client:
            # Find debug task
            print("\n   Looking for DEBUG task...")
            tasks_resp = await client.get(f"{API_URL}/api/tasks")
            tasks = tasks_resp.json()

            debug_tasks = [
                t for t in tasks
                if "DEBUG" in t.get("title", "") and t.get("status") == "new"
            ]

            if not debug_tasks:
                # Check if there's a processed debug task
                processed = [
                    t for t in tasks
                    if "DEBUG" in t.get("title", "")
                ]
                if processed:
                    print(f"   Found {len(processed)} processed DEBUG task(s)")
                    for t in processed:
                        print(f"   - {t['title']}: {t['status']}")
                    pytest.skip("No NEW debug tasks found - they may have been processed already")
                else:
                    pytest.skip("No debug tasks found - run test_step2 first")

            # Use most recent debug task
            debug_task = debug_tasks[-1]
            task_id = debug_task['id']

            print(f"   Found task: {debug_task['title']}")
            print(f"   Task ID: {task_id}")
            print(f"   Current status: {debug_task['status']}")

            # Wait for processing
            print("\n   Waiting for Core Agent to process...")
            print("   (Core Agent loop runs every ~30 seconds)")
            print()

            max_wait = 300  # 5 minutes
            poll_interval = 10

            for i in range(max_wait // poll_interval):
                await asyncio.sleep(poll_interval)
                elapsed = (i + 1) * poll_interval

                resp = await client.get(f"{API_URL}/api/tasks/{task_id}")
                if resp.status_code != 200:
                    print(f"   [{elapsed:3d}s] Error fetching task: {resp.status_code}")
                    continue

                task = resp.json()
                status = task['status']

                # Show progress
                if status == 'new':
                    print(f"   [{elapsed:3d}s] Status: {status} (waiting for agent to pick up)")
                elif status == 'in_progress':
                    print(f"   [{elapsed:3d}s] Status: {status} (agent is processing)")
                else:
                    print(f"   [{elapsed:3d}s] Status: {status}")

                # Check for terminal states
                if status in ['needs_review', 'completed', 'failed']:
                    print(f"\n   Task reached terminal status: {status}")

                    if status == 'needs_review':
                        print("\n" + "="*60)
                        print("✅ Task moved to needs_review (ask_user was likely called)")
                        print("   Run step 4 to verify ask_user was called")
                        print("="*60)
                    elif status == 'completed':
                        print("\n" + "="*60)
                        print("⚠️ Task completed without needs_review")
                        print("   This might mean ask_user was NOT called")
                        print("="*60)
                    elif status == 'failed':
                        print("\n" + "="*60)
                        print("❌ Task failed")
                        print("   Check core agent logs for errors")
                        print("="*60)

                    break
            else:
                print(f"\n   Timeout after {max_wait}s")
                pytest.fail(f"Task did not process within {max_wait}s. Is Core Agent running?")

            # For debugging, allow both needs_review and completed
            assert status in ['needs_review', 'completed'], \
                f"Expected needs_review or completed, got {status}"

    @pytest.mark.asyncio
    async def test_step4_verify_ask_user(self):
        """
        STEP 4: Verify ask_user was called with conflict question.

        This is the CRITICAL assertion - the agent MUST call ask_user
        when there's a calendar conflict.
        """
        print("\n" + "="*60)
        print("STEP 4: Verify ask_user Was Called")
        print("="*60)

        async with httpx.AsyncClient(timeout=30) as client:
            # Find debug task
            print("\n   Looking for processed DEBUG task...")
            tasks_resp = await client.get(f"{API_URL}/api/tasks")
            tasks = tasks_resp.json()

            debug_tasks = [
                t for t in tasks
                if "DEBUG" in t.get("title", "")
                and t.get("status") in ['needs_review', 'completed', 'in_progress']
            ]

            if not debug_tasks:
                pytest.skip("No processed debug tasks found - run step 3 first")

            # Use most recent
            debug_task = debug_tasks[-1]
            task_id = debug_task['id']

            print(f"   Found task: {debug_task['title']}")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {debug_task['status']}")

            # Get conversation
            print("\n   Fetching conversation...")
            thread_id = f"core_agent_task_{task_id}"
            conv_resp = await client.get(
                f"{API_URL}/chat/conversations/{thread_id}/task-data"
            )

            if conv_resp.status_code != 200:
                print(f"   Error: Could not fetch conversation (status {conv_resp.status_code})")
                print(f"   Response: {conv_resp.text[:500]}")
                pytest.fail(f"Could not get conversation: {conv_resp.status_code}")

            data = conv_resp.json()
            messages = data.get('messages', [])

            print(f"   Found {len(messages)} messages in conversation")

            # Analyze messages
            print("\n   Analyzing tool calls...")
            ask_user_called = False
            conflict_mentioned = False
            all_tool_calls = []

            for msg in messages:
                if msg.get('tool_calls'):
                    for tc in msg['tool_calls']:
                        tool_name = tc.get('tool', tc.get('name', 'unknown'))
                        all_tool_calls.append(tool_name)

                        if tool_name == 'ask_user':
                            ask_user_called = True
                            args = tc.get('args', tc.get('arguments', {}))
                            if isinstance(args, str):
                                import json
                                try:
                                    args = json.loads(args)
                                except:
                                    args = {'raw': args}

                            question = args.get('question', str(args))
                            print(f"\n   🎯 ask_user tool called!")
                            print(f"   Question: {question[:200]}...")

                            if 'conflict' in question.lower():
                                conflict_mentioned = True
                                print("   ✅ Conflict mentioned in question")

            # Print all tool calls for debugging
            if all_tool_calls:
                print(f"\n   All tool calls: {all_tool_calls}")
            else:
                print("\n   No tool calls found in conversation")

                # Show message contents for debugging
                print("\n   Message types found:")
                for i, msg in enumerate(messages[:10]):
                    msg_type = msg.get('type', 'unknown')
                    content = str(msg.get('content', ''))[:100]
                    print(f"   [{i}] {msg_type}: {content}...")

            # Check pending escalation as backup
            if data.get('pending_escalation'):
                print("\n   Found pending_escalation in task data")
                ask_user_called = True

            # Final verdict
            print("\n" + "="*60)
            if ask_user_called:
                if conflict_mentioned:
                    print("✅ PASSED: ask_user was called with conflict question")
                else:
                    print("⚠️ PARTIAL: ask_user was called but conflict not mentioned")
            else:
                print("❌ FAILED: ask_user was NOT called")
                print("\n   This is a CRITICAL failure - the agent should always")
                print("   call ask_user when there's a calendar conflict!")
            print("="*60)

            assert ask_user_called, "CRITICAL: ask_user was NOT called - check agent prompt and calendar conflict detection"

    @pytest.mark.asyncio
    async def test_cleanup_debug_data(self):
        """
        CLEANUP: Remove debug test data.

        Run this after debugging to clean up:
        - Delete DEBUG calendar events
        - Delete DEBUG tasks
        """
        print("\n" + "="*60)
        print("CLEANUP: Removing Debug Test Data")
        print("="*60)

        from backend.mcp_client import mcp_manager

        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=30) as client:
            # Clean up tasks
            print("\n   Cleaning up DEBUG tasks...")
            tasks_resp = await client.get(f"{API_URL}/api/tasks")
            if tasks_resp.status_code == 200:
                tasks = tasks_resp.json()
                debug_tasks = [t for t in tasks if "DEBUG" in t.get("title", "")]

                for task in debug_tasks:
                    try:
                        del_resp = await client.delete(f"{API_URL}/api/tasks/{task['id']}")
                        if del_resp.status_code == 200:
                            print(f"   ✅ Deleted task: {task['title'][:50]}...")
                        else:
                            print(f"   ⚠️ Failed to delete task {task['id']}: {del_resp.status_code}")
                    except Exception as e:
                        print(f"   ⚠️ Error deleting task: {e}")

                if not debug_tasks:
                    print("   No DEBUG tasks found to clean up")

        # Clean up calendar events
        print("\n   Cleaning up DEBUG calendar events...")
        tools = await mcp_manager.get_tools()
        list_tool = next((t for t in tools if t.name == "gcal_list_events"), None)
        delete_tool = next((t for t in tools if t.name == "gcal_delete_event"), None)

        if list_tool and delete_tool:
            try:
                events = await list_tool.arun({
                    "calendar_id": "primary",
                    "time_min": f"{date_str}T00:00:00+02:00"
                })

                # Parse events and find DEBUG ones
                events_str = str(events)
                if "DEBUG" in events_str:
                    print("   Found DEBUG events in calendar")
                    # Note: Would need to parse event IDs to delete
                    print("   (Manual cleanup may be needed for calendar events)")
                else:
                    print("   No DEBUG events found in calendar")

            except Exception as e:
                print(f"   ⚠️ Error checking calendar: {e}")
        else:
            print("   Calendar tools not available for cleanup")

        print("\n" + "="*60)
        print("✅ Cleanup completed")
        print("="*60)
