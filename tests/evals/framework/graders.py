"""
Code-based grading functions for the evaluation framework.

Graders check outcomes after agent execution:
1. Database state - Check tasks, status, tags
2. Tool calls - Check if specific tools were called with expected args
3. Agent behavior - Check message patterns, escalation
4. Negative cases - Check things that should NOT happen

Each grader returns Tuple[bool, str] for (passed, message).
"""

from typing import Any
import json
import logging

logger = logging.getLogger(__name__)


async def check_task_status(
    result: dict[str, Any],
    expected: dict[str, Any],
    db_context: dict[str, Any],
    thread_id: str,
) -> tuple[bool, str]:
    """
    Check if a task has the expected status in the database.

    Expected format:
        expected = {
            "task_id": "uuid-string",  # or use db_context["created_task_ids"][0]
            "expected_status": "needs_review"
        }
    """
    from database.database import db_manager
    from models.models import Task
    from sqlalchemy import select

    task_id = expected.get("task_id")
    if not task_id and db_context.get("created_task_ids"):
        task_id = db_context["created_task_ids"][0]

    if not task_id:
        return False, "No task_id provided and none in db_context"

    expected_status = expected.get("expected_status", "needs_review")

    async with db_manager.get_session() as session:
        result_query = await session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result_query.scalar_one_or_none()

        if not task:
            return False, f"Task {task_id} not found in database"

        actual_status = task.status.value if hasattr(task.status, "value") else str(task.status)

        if actual_status == expected_status:
            return True, f"Task status is '{expected_status}' as expected"
        else:
            return False, f"Expected status '{expected_status}', got '{actual_status}'"


async def check_tool_called(
    result: dict[str, Any],
    expected: dict[str, Any],
    db_context: dict[str, Any],
    thread_id: str,
) -> tuple[bool, str]:
    """
    Check if a specific tool was called during agent execution.

    Expected format:
        expected = {
            "tool_name": "ask_user"
        }
    """
    tool_name = expected.get("tool_name")
    if not tool_name:
        return False, "No tool_name specified in expected outcomes"

    messages = result.get("messages", [])

    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                tc_name = tc.get("name", tc.get("tool", ""))
                if tc_name == tool_name:
                    return True, f"Tool '{tool_name}' was called"

    return False, f"Tool '{tool_name}' was NOT called"


async def check_tool_called_with_args(
    result: dict[str, Any],
    expected: dict[str, Any],
    db_context: dict[str, Any],
    thread_id: str,
) -> tuple[bool, str]:
    """
    Check if a tool was called with specific arguments (partial match).

    Expected format:
        expected = {
            "tool_name": "ask_user",
            "expected_args": {
                "question_contains": "conflict"  # Special key for substring match
            }
        }
    """
    tool_name = expected.get("tool_name")
    expected_args = expected.get("expected_args", {})

    if not tool_name:
        return False, "No tool_name specified in expected outcomes"

    messages = result.get("messages", [])
    tool_calls_found = []

    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                tc_name = tc.get("name", tc.get("tool", ""))
                if tc_name == tool_name:
                    tc_args = tc.get("args", {})
                    # Parse args if string
                    if isinstance(tc_args, str):
                        try:
                            tc_args = json.loads(tc_args)
                        except json.JSONDecodeError:
                            tc_args = {"raw": tc_args}

                    tool_calls_found.append(tc_args)

    if not tool_calls_found:
        return False, f"Tool '{tool_name}' was NOT called"

    # Check if any call matches expected args
    for tc_args in tool_calls_found:
        match = True
        match_details = []

        for key, expected_value in expected_args.items():
            if key == "question_contains":
                # Special case: check if 'question' arg contains substring
                question = tc_args.get("question", "")
                if isinstance(question, str) and expected_value.lower() in question.lower():
                    match_details.append(f"question contains '{expected_value}'")
                else:
                    match = False
                    break
            elif key.endswith("_contains"):
                # Generic substring match for any arg
                actual_key = key.replace("_contains", "")
                actual_value = tc_args.get(actual_key, "")
                if isinstance(actual_value, str) and expected_value.lower() in actual_value.lower():
                    match_details.append(f"{actual_key} contains '{expected_value}'")
                else:
                    match = False
                    break
            else:
                # Exact match
                if tc_args.get(key) == expected_value:
                    match_details.append(f"{key}={expected_value}")
                else:
                    match = False
                    break

        if match:
            details = ", ".join(match_details) if match_details else "matched"
            return True, f"Tool '{tool_name}' called with expected args: {details}"

    return False, f"Tool '{tool_name}' called but args didn't match. Found: {tool_calls_found}"


async def check_task_not_created(
    result: dict[str, Any],
    expected: dict[str, Any],
    db_context: dict[str, Any],
    thread_id: str,
) -> tuple[bool, str]:
    """
    Negative case: Check that a task was NOT created.

    Expected format:
        expected = {
            "task_title_pattern": "some pattern"  # Optional
        }
    """
    from database.database import db_manager
    from models.models import Task
    from sqlalchemy import select

    title_pattern = expected.get("task_title_pattern")

    async with db_manager.get_session() as session:
        query = select(Task)
        if title_pattern:
            query = query.where(Task.title.ilike(f"%{title_pattern}%"))

        result_query = await session.execute(query)
        tasks = result_query.scalars().all()

        # Filter to only tasks created after db_context was set up
        created_ids = set(db_context.get("created_task_ids", []))
        new_tasks = [t for t in tasks if str(t.id) not in created_ids]

        if not new_tasks:
            return True, "No unexpected tasks were created"
        else:
            task_titles = [t.title for t in new_tasks[:3]]
            return False, f"Unexpected tasks created: {task_titles}"


async def check_ask_user_for_conflict(
    result: dict[str, Any],
    expected: dict[str, Any],
    db_context: dict[str, Any],
    thread_id: str,
) -> tuple[bool, str]:
    """
    Specialized grader for calendar conflict detection.

    Checks that:
    1. ask_user tool was called
    2. The question mentions "conflict" (case-insensitive)

    Expected format:
        expected = {}  # No special config needed
    """
    messages = result.get("messages", [])

    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                tc_name = tc.get("name", tc.get("tool", ""))
                if tc_name == "ask_user":
                    tc_args = tc.get("args", {})
                    # Parse args if string
                    if isinstance(tc_args, str):
                        try:
                            tc_args = json.loads(tc_args)
                        except json.JSONDecodeError:
                            tc_args = {"raw": tc_args}

                    question = tc_args.get("question", str(tc_args))
                    if "conflict" in question.lower():
                        return True, f"ask_user called with conflict question: '{question[:100]}...'"

    # Check for any ask_user calls without conflict
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                tc_name = tc.get("name", tc.get("tool", ""))
                if tc_name == "ask_user":
                    tc_args = tc.get("args", {})
                    if isinstance(tc_args, str):
                        try:
                            tc_args = json.loads(tc_args)
                        except json.JSONDecodeError:
                            tc_args = {"raw": tc_args}
                    question = tc_args.get("question", str(tc_args))
                    return False, f"ask_user called but 'conflict' not in question: '{question[:100]}...'"

    return False, "ask_user tool was NOT called"


async def check_calendar_event_created(
    result: dict[str, Any],
    expected: dict[str, Any],
    db_context: dict[str, Any],
    thread_id: str,
) -> tuple[bool, str]:
    """
    Check if a calendar event creation tool was called.

    Expected format:
        expected = {
            "event_title_contains": "kindergarten"  # Optional
        }
    """
    messages = result.get("messages", [])
    title_pattern = expected.get("event_title_contains", "").lower()

    calendar_tools = [
        "google_workspace-create_event",
        "gcal_create_event",
        "create_calendar_event",
    ]

    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                tc_name = tc.get("name", tc.get("tool", ""))
                if tc_name in calendar_tools:
                    tc_args = tc.get("args", {})
                    if isinstance(tc_args, str):
                        try:
                            tc_args = json.loads(tc_args)
                        except json.JSONDecodeError:
                            tc_args = {}

                    summary = tc_args.get("summary", "")
                    if not title_pattern or title_pattern in summary.lower():
                        return True, f"Calendar event creation called: '{summary}'"

    return False, "No calendar event creation tool was called"
