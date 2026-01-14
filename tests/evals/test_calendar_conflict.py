"""
Eval: Calendar Conflict Detection

Tests that Nova's core agent correctly:
1. Detects calendar conflicts when processing tasks
2. Calls ask_user to escalate the conflict to the user
3. Moves the task to needs_review status

This is a migration of tests/end2end/test_real_calendar_conflict_e2e.py
to the evaluation framework.

Original test: TC_Calendar_002
Tags: calendar, conflict, escalation, p1-critical
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import Any

from tests.evals.framework.eval_case import EvalCase
from tests.evals.framework.eval_runner import EvalRunner, calculate_pass_at_k
from tests.evals.framework.graders import (
    check_task_status,
    check_ask_user_for_conflict,
    check_calendar_event_created,
)


# Mark all tests in this module as evals
pytestmark = [pytest.mark.eval, pytest.mark.calendar, pytest.mark.asyncio]


async def setup_calendar_conflict_scenario(
    mcp_tools: list,
    test_date: datetime,
) -> dict[str, Any]:
    """
    Set up the calendar conflict scenario:
    1. Create a calendar event for tomorrow 10:00-11:00
    2. Return context for cleanup

    Returns:
        Dict with event_id and other context for cleanup
        Returns None if calendar tools are not available
    """
    date_str = test_date.strftime("%Y-%m-%d")
    start_time = f"{date_str}T10:00:00+02:00"
    end_time = f"{date_str}T11:00:00+02:00"

    timestamp = int(time.time())
    event_title = f"Project Sync Eval Test {timestamp}"

    # Find calendar create tools (support multiple providers)
    calendar_create_tools = [
        "google_workspace-create_event",
        "gcal_create_event",
        "outlook_mac-create_calendar_event",
        "outlook-create_event",
    ]
    create_tool = next(
        (t for t in mcp_tools if t.name in calendar_create_tools),
        None
    )

    if not create_tool:
        return None  # Signal that calendar tools aren't available

    # Create the conflicting event
    result = await asyncio.wait_for(
        create_tool.ainvoke({
            "calendar_id": "primary",
            "summary": event_title,
            "start_datetime": start_time,
            "end_datetime": end_time,
            "description": "Eval test event for conflict detection"
        }),
        timeout=30.0
    )

    # Extract event ID for cleanup
    event_id = None
    if isinstance(result, dict):
        event_id = result.get("event_id") or result.get("id")
    elif isinstance(result, str):
        import json
        try:
            parsed = json.loads(result)
            event_id = parsed.get("event_id") or parsed.get("id")
        except json.JSONDecodeError:
            pass

    return {
        "event_id": event_id,
        "event_title": event_title,
        "test_date": test_date,
        "date_str": date_str,
    }


async def cleanup_calendar_event(mcp_tools: list, event_id: str):
    """Clean up a calendar event after test."""
    if not event_id:
        return

    delete_tool = next(
        (t for t in mcp_tools if t.name in ["google_workspace-delete_event", "gcal_delete_event"]),
        None
    )

    if delete_tool:
        try:
            await asyncio.wait_for(
                delete_tool.ainvoke({
                    "calendar_id": "primary",
                    "event_id": event_id
                }),
                timeout=10.0
            )
        except Exception:
            pass  # Best effort cleanup


def create_kindergarten_closure_task(date_str: str) -> dict[str, Any]:
    """Create the task data that triggers calendar conflict detection."""
    timestamp = int(time.time())
    return {
        "title": f"Kindergarten Closure Eval - {date_str} - {timestamp}",
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


class TestCalendarConflictEval:
    """
    Evaluation tests for calendar conflict detection.

    These tests verify that Nova correctly identifies scheduling
    conflicts and escalates them to the user via ask_user.
    """

    @pytest.mark.slow
    async def test_calendar_conflict_detection_eval(
        self,
        test_data_cleaner,
    ):
        """
        Full calendar conflict detection evaluation.

        Scenario:
        1. Create a calendar event for tomorrow 10:00-11:00
        2. Create a task about kindergarten closure (full day tomorrow)
        3. Process the task with the core agent
        4. Verify: ask_user called with "conflict" in question
        5. Verify: task moved to needs_review status

        This uses real MCP tools and real LLM.
        """
        import httpx
        from mcp_client import mcp_manager

        # Check prerequisites
        api_base_url = "http://localhost:8000"
        core_agent_url = "http://localhost:8001"

        async with httpx.AsyncClient() as client:
            try:
                health = await client.get(f"{api_base_url}/health", timeout=5.0)
                if health.status_code != 200:
                    pytest.skip("Nova API not available")
            except Exception:
                pytest.skip("Nova API not available")

            try:
                core_health = await client.get(f"{core_agent_url}/health", timeout=5.0)
                if core_health.status_code != 200:
                    pytest.skip("Core Agent not available")
            except Exception:
                pytest.skip("Core Agent not available")

        # Get MCP tools
        mcp_tools = await mcp_manager.get_tools()
        if not mcp_tools:
            pytest.skip("No MCP tools available")

        # Setup: Create conflicting calendar event
        test_date = datetime.now() + timedelta(days=1)
        calendar_context = None
        task_id = None

        try:
            calendar_context = await setup_calendar_conflict_scenario(
                mcp_tools, test_date
            )
            if calendar_context is None:
                pytest.skip("No calendar create tool available (need Google Workspace or Outlook)")
            date_str = calendar_context["date_str"]

            # Create the task that should trigger conflict detection
            task_data = create_kindergarten_closure_task(date_str)

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{api_base_url}/api/tasks",
                    json=task_data
                )
                if response.status_code != 200:
                    pytest.fail(f"Failed to create task: {response.status_code}")

                task = response.json()
                task_id = task["id"]

            # Wait for core agent to process
            max_wait = 300  # 5 minutes
            poll_interval = 10
            processed_task = None

            async with httpx.AsyncClient() as client:
                for i in range(max_wait // poll_interval):
                    await asyncio.sleep(poll_interval)

                    task_resp = await client.get(f"{api_base_url}/api/tasks/{task_id}")
                    if task_resp.status_code != 200:
                        continue

                    current_task = task_resp.json()
                    status = current_task["status"]

                    if status == "needs_review":
                        processed_task = current_task
                        break
                    elif status in ["completed", "failed"]:
                        pytest.fail(f"Task ended with unexpected status: {status}")

            if not processed_task:
                pytest.fail(f"Task not processed within {max_wait}s")

            # Verify ask_user was called with conflict message
            async with httpx.AsyncClient() as client:
                conv_resp = await client.get(
                    f"{api_base_url}/chat/conversations/core_agent_task_{task_id}/task-data"
                )

                if conv_resp.status_code != 200:
                    pytest.fail(f"Could not get conversation: {conv_resp.status_code}")

                data = conv_resp.json()
                messages = data.get("messages", [])

                ask_user_called = False
                conflict_mentioned = False
                question_text = ""

                for msg in messages:
                    if msg.get("tool_calls"):
                        for tc in msg["tool_calls"]:
                            tool_name = tc.get("tool", tc.get("name", ""))
                            if tool_name == "ask_user":
                                ask_user_called = True
                                args = tc.get("args", {})
                                if isinstance(args, str):
                                    import json
                                    try:
                                        args = json.loads(args)
                                    except:
                                        pass
                                question_text = args.get("question", str(args)) if isinstance(args, dict) else str(args)
                                if "conflict" in question_text.lower():
                                    conflict_mentioned = True

                # Also check pending_escalation
                if data.get("pending_escalation"):
                    ask_user_called = True
                    question_text = data["pending_escalation"].get("question", "")
                    if "conflict" in question_text.lower():
                        conflict_mentioned = True

            # Assertions (these are the grading criteria)
            assert processed_task["status"] == "needs_review", \
                f"Expected needs_review, got {processed_task['status']}"

            assert ask_user_called, (
                "CRITICAL: ask_user was NOT called! "
                "The agent MUST call ask_user when there's a calendar conflict."
            )

            assert conflict_mentioned, (
                f"ask_user was called but 'conflict' not in question. "
                f"Question was: {question_text[:200]}"
            )

        finally:
            # Cleanup
            if calendar_context and calendar_context.get("event_id"):
                await cleanup_calendar_event(mcp_tools, calendar_context["event_id"])

            if task_id:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.delete(f"{api_base_url}/api/tasks/{task_id}")
                except Exception:
                    pass

    @pytest.mark.slow
    async def test_calendar_conflict_with_eval_framework(
        self,
        eval_pg_pool,
        eval_runner,
        test_data_cleaner,
    ):
        """
        Same test but using the EvalCase/EvalRunner framework.

        This demonstrates how to define the eval as an EvalCase
        for integration with the eval framework.
        """
        # For now, skip this until we have the full framework wired up
        # The test above is the direct migration; this shows the target pattern
        pytest.skip("EvalCase-based test - framework integration in progress")

        eval_case = EvalCase(
            name="calendar_conflict_detection",
            description="Detect calendar conflict and escalate via ask_user",
            tags=["calendar", "conflict", "escalation", "p1-critical"],
            grading_functions=[
                check_task_status,
                check_ask_user_for_conflict,
            ],
            expected_outcomes={
                "expected_status": "needs_review",
            },
            initial_db_state={
                "tasks": [
                    {
                        "title": "Kindergarten Closure - Full Day",
                        "description": "Kindergarten closed all day tomorrow",
                        "status": "new",
                    }
                ]
            },
            agent_type="core",
            use_real_mcp=True,
            num_trials=3,
            timeout_seconds=300,
        )

        results = await eval_runner.run_eval(eval_case)

        # Check pass@k
        pass_rate = calculate_pass_at_k(results)
        assert pass_rate > 0, "At least one trial should pass"

        # Log results for debugging
        for result in results:
            print(f"Trial {result.trial_number}: {'PASS' if result.passed else 'FAIL'}")
            for gr in result.grade_results:
                print(f"  - {gr.grader_name}: {'✓' if gr.passed else '✗'} {gr.message}")
