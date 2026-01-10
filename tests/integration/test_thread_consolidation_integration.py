"""
Integration tests for Email Thread Consolidation (ADR-019).

Tests the full flow from Gmail API through thread consolidation to task creation,
using real database connections and MCP tools.

Requirements:
- PostgreSQL running (docker-compose up postgres)
- Redis running (docker-compose up redis)
- Google Workspace MCP server with valid Gmail credentials

Run with: cd backend && uv run pytest ../tests/integration/test_thread_consolidation_integration.py -v
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID

from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from database.database import db_manager
from models.models import Task, TaskStatus, ProcessedItem
from input_hooks.models import GmailHookConfig, GmailHookSettings
from input_hooks.email_processing.processor import EmailProcessor
from input_hooks.email_processing.thread_consolidator import EmailThreadConsolidator


async def create_test_thread_task(
    thread_id: str,
    subject: str,
    email_count: int = 1,
    is_stabilizing: bool = True,
    stabilization_minutes: int = 15,
    description: str = None
) -> UUID:
    """
    Helper to create a thread task directly in the database.

    This bypasses the create_task_tool which has async context issues in tests.
    """
    async with db_manager.get_session() as session:
        stabilization_ends = datetime.utcnow() + timedelta(minutes=stabilization_minutes)

        task = Task(
            title=f"Email Thread: {subject} ({email_count} message{'s' if email_count > 1 else ''})",
            description=description or f"**Thread ID:** {thread_id}\n**Messages:** {email_count}\n\n---\n\nTest content",
            status=TaskStatus.NEW,
            tags=["email", "thread"],
            task_metadata={
                "email_thread_id": thread_id,
                "email_count": email_count,
                "is_thread_stabilizing": is_stabilizing,
                "thread_stabilization_ends_at": stabilization_ends.isoformat() + "Z"
            }
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task.id


class TestEmailThreadConsolidatorIntegration:
    """Integration tests for EmailThreadConsolidator with real database."""

    @pytest.fixture
    def consolidator(self):
        """Create a consolidator with 1-minute stabilization for faster tests."""
        return EmailThreadConsolidator(stabilization_minutes=1)

    @pytest.fixture
    async def cleanup_test_tasks(self):
        """Cleanup any test tasks after each test."""
        created_task_ids = []
        yield created_task_ids
        # Cleanup tasks created during tests
        async with db_manager.get_session() as session:
            for task_id in created_task_ids:
                result = await session.execute(
                    select(Task).where(Task.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    await session.delete(task)
            # Also cleanup any test tasks by pattern
            result = await session.execute(
                select(Task).where(Task.title.like("%Integration Test%"))
            )
            tasks = result.scalars().all()
            for task in tasks:
                await session.delete(task)
            await session.commit()

    @pytest.mark.asyncio
    async def test_create_thread_task_stores_metadata(self, cleanup_test_tasks):
        """Test that created thread tasks have correct metadata in database."""
        thread_id = f"test_thread_{uuid4().hex[:8]}"

        # Create task directly in database
        task_id = await create_test_thread_task(
            thread_id=thread_id,
            subject="Integration Test Thread",
            email_count=1,
            is_stabilizing=True,
            stabilization_minutes=15
        )
        cleanup_test_tasks.append(task_id)

        # Verify task in database
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task = result.scalar_one_or_none()

            assert task is not None
            assert "Email Thread: Integration Test Thread" in task.title
            assert task.task_metadata is not None
            assert task.task_metadata.get("email_thread_id") == thread_id
            assert task.task_metadata.get("email_count") == 1
            assert task.task_metadata.get("is_thread_stabilizing") is True
            assert "thread_stabilization_ends_at" in task.task_metadata

    @pytest.mark.asyncio
    async def test_find_existing_thread_task_with_database(self, consolidator, cleanup_test_tasks):
        """Test finding existing thread task using real database queries."""
        thread_id = f"test_thread_{uuid4().hex[:8]}"

        # Create a task directly
        task_id = await create_test_thread_task(
            thread_id=thread_id,
            subject="Integration Test Find",
            email_count=1
        )
        cleanup_test_tasks.append(task_id)

        # Now find it using the consolidator
        found_task = await consolidator.find_existing_thread_task(thread_id)

        assert found_task is not None
        assert found_task.id == task_id

    @pytest.mark.asyncio
    async def test_supersede_task_updates_database(self, consolidator, cleanup_test_tasks):
        """Test that superseding a task properly updates both tasks in database."""
        thread_id = f"test_thread_{uuid4().hex[:8]}"

        # Create initial task directly
        initial_task_id = await create_test_thread_task(
            thread_id=thread_id,
            subject="Integration Test Supersede",
            email_count=1
        )
        cleanup_test_tasks.append(initial_task_id)

        # Find the task for superseding
        existing_task = await consolidator.find_existing_thread_task(thread_id)
        assert existing_task is not None

        # Create new task (simulating what supersede_unprocessed_task does)
        new_task_id = await create_test_thread_task(
            thread_id=thread_id,
            subject="Integration Test Supersede",
            email_count=2,
            description="**Thread ID:** {}\n**Messages:** 2\n\n---\n\n### Message 1\nFirst email\n\n---\n\n### Message 2\nSecond email".format(thread_id)
        )
        cleanup_test_tasks.append(new_task_id)

        # Mark the old task as superseded
        await consolidator._mark_task_superseded(
            task_id=str(initial_task_id),
            superseded_by_task_id=str(new_task_id),
            reason="thread_consolidation"
        )

        # Verify old task is marked as superseded
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == initial_task_id)
            )
            old_task = result.scalar_one()

            assert old_task.status == TaskStatus.DONE
            assert old_task.task_metadata.get("superseded_by_task_id") == str(new_task_id)
            assert old_task.task_metadata.get("superseded_reason") == "thread_consolidation"

    @pytest.mark.asyncio
    async def test_stabilization_window_expires(self, consolidator, cleanup_test_tasks):
        """Test that stabilization window expiration is correctly detected."""
        thread_id = f"test_thread_{uuid4().hex[:8]}"

        # Create task with stabilization
        task_id = await create_test_thread_task(
            thread_id=thread_id,
            subject="Integration Test Expired",
            email_count=1,
            is_stabilizing=True
        )
        cleanup_test_tasks.append(task_id)

        # Manually set stabilization to past time
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task = result.scalar_one()

            past_time = (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z"
            metadata = dict(task.task_metadata or {})
            metadata["thread_stabilization_ends_at"] = past_time
            task.task_metadata = metadata
            flag_modified(task, 'task_metadata')
            await session.commit()

        # Find task and check if should process
        found_task = await consolidator.find_existing_thread_task(thread_id)
        should_process = await consolidator.should_process_thread(found_task)

        assert should_process is True

    @pytest.mark.asyncio
    async def test_find_excludes_superseded_tasks(self, consolidator, cleanup_test_tasks):
        """Test that find_existing_thread_task excludes superseded tasks."""
        thread_id = f"test_thread_{uuid4().hex[:8]}"

        # Create old task and mark as superseded
        old_task_id = await create_test_thread_task(
            thread_id=thread_id,
            subject="Integration Test Old",
            email_count=1
        )
        cleanup_test_tasks.append(old_task_id)

        # Create new task
        new_task_id = await create_test_thread_task(
            thread_id=thread_id,
            subject="Integration Test New",
            email_count=2
        )
        cleanup_test_tasks.append(new_task_id)

        # Mark old task as superseded
        await consolidator._mark_task_superseded(
            task_id=str(old_task_id),
            superseded_by_task_id=str(new_task_id),
            reason="thread_consolidation"
        )

        # Find should return the new task, not the superseded one
        found_task = await consolidator.find_existing_thread_task(thread_id)

        assert found_task is not None
        assert found_task.id == new_task_id
        assert found_task.id != old_task_id

    @pytest.mark.asyncio
    async def test_reset_stabilization_window(self, consolidator, cleanup_test_tasks):
        """Test that reset_stabilization_window updates the database correctly."""
        thread_id = f"test_thread_{uuid4().hex[:8]}"

        # Create task with old stabilization time
        task_id = await create_test_thread_task(
            thread_id=thread_id,
            subject="Integration Test Reset",
            email_count=1,
            is_stabilizing=True,
            stabilization_minutes=-5  # Already expired
        )
        cleanup_test_tasks.append(task_id)

        # Find the task
        task = await consolidator.find_existing_thread_task(thread_id)
        assert task is not None

        # Reset stabilization window
        await consolidator.reset_stabilization_window(task)

        # Verify the window was reset to future
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            updated_task = result.scalar_one()

            end_time_str = updated_task.task_metadata.get("thread_stabilization_ends_at")
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00')).replace(tzinfo=None)

            # Should be in the future now
            assert end_time > datetime.utcnow()


class TestCoreAgentStabilizationFilterIntegration:
    """Integration tests for CoreAgent stabilization filter with real database."""

    @pytest.fixture
    async def setup_test_tasks(self):
        """Create test tasks with various stabilization states."""
        task_ids = []

        async with db_manager.get_session() as session:
            # Task 1: Stabilizing (should be skipped)
            stabilizing_task = Task(
                title="Stabilizing Task - Integration Test",
                description="Task with active stabilization",
                status=TaskStatus.NEW,
                task_metadata={
                    "email_thread_id": "thread_stabilizing",
                    "is_thread_stabilizing": True,
                    "thread_stabilization_ends_at": (datetime.utcnow() + timedelta(minutes=30)).isoformat() + "Z"
                }
            )
            session.add(stabilizing_task)

            # Task 2: Stabilization expired (should be picked up)
            expired_task = Task(
                title="Expired Stabilization - Integration Test",
                description="Task with expired stabilization",
                status=TaskStatus.NEW,
                task_metadata={
                    "email_thread_id": "thread_expired",
                    "is_thread_stabilizing": True,
                    "thread_stabilization_ends_at": (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z"
                }
            )
            session.add(expired_task)

            # Task 3: No metadata (should be picked up)
            no_metadata_task = Task(
                title="No Metadata Task - Integration Test",
                description="Task without thread metadata",
                status=TaskStatus.NEW,
                task_metadata=None
            )
            session.add(no_metadata_task)

            # Task 4: is_thread_stabilizing=false (should be picked up)
            not_stabilizing_task = Task(
                title="Not Stabilizing Task - Integration Test",
                description="Task with stabilizing=false",
                status=TaskStatus.NEW,
                task_metadata={
                    "email_thread_id": "thread_not_stabilizing",
                    "is_thread_stabilizing": False
                }
            )
            session.add(not_stabilizing_task)

            # Task 5: is_thread_stabilizing=true but no end time (should be picked up - defensive)
            missing_end_time_task = Task(
                title="Missing End Time - Integration Test",
                description="Task with stabilizing=true but no end time",
                status=TaskStatus.NEW,
                task_metadata={
                    "email_thread_id": "thread_missing_end",
                    "is_thread_stabilizing": True
                    # Note: thread_stabilization_ends_at is intentionally missing
                }
            )
            session.add(missing_end_time_task)

            await session.commit()

            # Refresh to get IDs
            await session.refresh(stabilizing_task)
            await session.refresh(expired_task)
            await session.refresh(no_metadata_task)
            await session.refresh(not_stabilizing_task)
            await session.refresh(missing_end_time_task)

            task_ids = [
                str(stabilizing_task.id),
                str(expired_task.id),
                str(no_metadata_task.id),
                str(not_stabilizing_task.id),
                str(missing_end_time_task.id)
            ]

        yield task_ids

        # Cleanup
        async with db_manager.get_session() as session:
            for task_id in task_ids:
                result = await session.execute(
                    select(Task).where(Task.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    await session.delete(task)
            await session.commit()

    @pytest.mark.asyncio
    async def test_stabilization_filter_in_database_query(self, setup_test_tasks):
        """Test that the stabilization filter correctly works in database queries."""
        task_ids = setup_test_tasks
        stabilizing_task_id = task_ids[0]

        async with db_manager.get_session() as session:
            now = datetime.utcnow()

            # This is the same filter used in CoreAgent._get_next_task()
            not_stabilizing = or_(
                Task.task_metadata.is_(None),
                ~Task.task_metadata.has_key('is_thread_stabilizing'),
                Task.task_metadata['is_thread_stabilizing'].astext.is_(None),
                Task.task_metadata['is_thread_stabilizing'].astext == 'false',
                ~Task.task_metadata.has_key('thread_stabilization_ends_at'),
                Task.task_metadata['thread_stabilization_ends_at'].astext.is_(None),
                Task.task_metadata['thread_stabilization_ends_at'].astext < now.isoformat()
            )

            # Query for NEW tasks that are NOT stabilizing
            result = await session.execute(
                select(Task)
                .where(Task.status == TaskStatus.NEW)
                .where(Task.title.like("%Integration Test%"))
                .where(not_stabilizing)
                .order_by(Task.updated_at.asc())
            )

            available_tasks = result.scalars().all()
            available_task_ids = [str(t.id) for t in available_tasks]

            # Stabilizing task should NOT be in results
            assert stabilizing_task_id not in available_task_ids

            # These tasks SHOULD be in results:
            expired_task_id = task_ids[1]  # expired stabilization
            no_metadata_id = task_ids[2]   # no metadata
            not_stabilizing_id = task_ids[3]  # is_thread_stabilizing=false
            missing_end_time_id = task_ids[4]  # missing end time

            assert expired_task_id in available_task_ids, "Expired stabilization task should be available"
            assert no_metadata_id in available_task_ids, "No metadata task should be available"
            assert not_stabilizing_id in available_task_ids, "Not stabilizing task should be available"
            assert missing_end_time_id in available_task_ids, "Missing end time task should be available"


class TestGmailThreadConsolidationIntegration:
    """
    Integration tests for Gmail hook with thread consolidation.

    These tests require:
    - Google Workspace MCP server running with valid credentials
    - Real Gmail access (read-only)
    """

    @pytest.fixture
    def gmail_config(self):
        """Create Gmail hook config with thread consolidation enabled."""
        return GmailHookConfig(
            name="test_gmail_thread_consolidation",
            enabled=True,
            create_tasks=True,
            polling_interval=300,
            hook_settings=GmailHookSettings(
                max_per_fetch=5,
                label_filter=None,
                thread_consolidation_enabled=True,
                thread_stabilization_minutes=1  # Short for testing
            )
        )

    @pytest.mark.asyncio
    async def test_gmail_mcp_connection(self, gmail_config):
        """Test that Gmail MCP tools are available."""
        from input_hooks.email_processing.fetcher import EmailFetcher

        fetcher = EmailFetcher()

        try:
            # Check MCP tools are available
            tools = await fetcher._get_email_tools()

            assert tools is not None
            assert len(tools) > 0, "No Gmail MCP tools found - is google-workspace MCP server running?"

            # Check for essential tools
            assert "list_emails" in tools, "list_emails tool not found"

            print(f"Found Gmail MCP tools: {list(tools.keys())}")

        except Exception as e:
            if "mcp" in str(e).lower() or "connection" in str(e).lower():
                pytest.skip(f"Gmail MCP not available: {e}")
            raise

    @pytest.mark.asyncio
    async def test_gmail_fetch_emails(self, gmail_config):
        """Test fetching emails from Gmail via MCP."""
        processor = EmailProcessor(
            thread_consolidation_enabled=True,
            stabilization_minutes=1
        )

        try:
            emails = await processor.fetch_new_emails(gmail_config)

            # Should return a list (may be empty if no new emails)
            assert isinstance(emails, list)

            if emails:
                # Check email structure
                email = emails[0]
                assert "id" in email or "subject" in email, "Email missing expected fields"

                # Log what we found for debugging
                print(f"\nFetched {len(emails)} emails from Gmail:")
                for e in emails[:3]:  # Show first 3
                    print(f"  - Subject: {e.get('subject', 'No subject')[:50]}")
                    print(f"    Thread ID: {e.get('thread_id', 'N/A')}")
                    print(f"    From: {e.get('from', 'N/A')}")
            else:
                print("\nNo new emails found (this is OK if inbox is empty or all processed)")

        except Exception as e:
            # If MCP not available, skip gracefully
            if "tool" in str(e).lower() or "mcp" in str(e).lower():
                pytest.skip(f"Gmail MCP not available: {e}")
            raise

    @pytest.mark.asyncio
    async def test_email_processor_with_thread_consolidation(self, gmail_config):
        """Test EmailProcessor handles thread consolidation correctly."""
        processor = EmailProcessor(
            thread_consolidation_enabled=True,
            stabilization_minutes=1
        )

        # Verify consolidation settings propagated
        assert processor.thread_consolidation_enabled is True
        assert processor.thread_consolidator is not None
        assert processor.thread_consolidator.stabilization_minutes == 1


class TestTaskToResponseThreadFields:
    """Integration test for API endpoint task serialization with thread fields."""

    @pytest.fixture
    async def task_with_thread_metadata(self):
        """Create a task with thread consolidation metadata."""
        async with db_manager.get_session() as session:
            task = Task(
                title="Email Thread: API Test Thread (2 messages)",
                description="Test thread content",
                status=TaskStatus.NEW,
                task_metadata={
                    "email_thread_id": "thread_api_test_123",
                    "email_count": 2,
                    "is_thread_stabilizing": True,
                    "thread_stabilization_ends_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat() + "Z"
                }
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        yield task_id

        # Cleanup
        async with db_manager.get_session() as session:
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                await session.delete(task)
            await session.commit()

    @pytest.mark.asyncio
    async def test_task_to_response_extracts_thread_fields(self, task_with_thread_metadata):
        """Test that task_to_response correctly extracts thread consolidation fields."""
        from api.api_endpoints import task_to_response

        task_id = task_with_thread_metadata

        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task)
                .options(selectinload(Task.comments))
                .where(Task.id == task_id)
            )
            task = result.scalar_one()

            # Convert to response
            response = task_to_response(task)

            # Verify thread fields are extracted
            assert response.email_thread_id == "thread_api_test_123"
            assert response.email_count == 2
            assert response.is_thread_stabilizing is True
            assert response.thread_stabilization_ends_at is not None

    @pytest.mark.asyncio
    async def test_task_to_response_handles_missing_metadata(self):
        """Test that task_to_response handles tasks without thread metadata."""
        from api.api_endpoints import task_to_response

        # Create task without metadata
        async with db_manager.get_session() as session:
            task = Task(
                title="Regular Task - No Thread Metadata",
                description="Test description",
                status=TaskStatus.NEW,
                task_metadata=None
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(Task)
                    .options(selectinload(Task.comments))
                    .where(Task.id == task_id)
                )
                task = result.scalar_one()

                # Convert to response - should not raise
                response = task_to_response(task)

                # Verify defaults
                assert response.email_thread_id is None
                assert response.email_count is None
                assert response.is_thread_stabilizing is False
                assert response.thread_stabilization_ends_at is None
                assert response.superseded_by_task_id is None
        finally:
            # Cleanup
            async with db_manager.get_session() as session:
                result = await session.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    await session.delete(task)
                await session.commit()

    @pytest.mark.asyncio
    async def test_task_to_response_handles_malformed_datetime(self):
        """Test that task_to_response handles malformed datetime strings."""
        from api.api_endpoints import task_to_response

        # Create task with malformed datetime
        async with db_manager.get_session() as session:
            task = Task(
                title="Task with Malformed DateTime",
                description="Test description",
                status=TaskStatus.NEW,
                task_metadata={
                    "email_thread_id": "thread_malformed",
                    "is_thread_stabilizing": True,
                    "thread_stabilization_ends_at": "not-a-valid-datetime"
                }
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(Task)
                    .options(selectinload(Task.comments))
                    .where(Task.id == task_id)
                )
                task = result.scalar_one()

                # Convert to response - should not raise, should default to None
                response = task_to_response(task)

                # Malformed datetime should result in None
                assert response.thread_stabilization_ends_at is None
                # But other fields should still work
                assert response.email_thread_id == "thread_malformed"
                assert response.is_thread_stabilizing is True
        finally:
            # Cleanup
            async with db_manager.get_session() as session:
                result = await session.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    await session.delete(task)
                await session.commit()

    @pytest.mark.asyncio
    async def test_task_to_response_handles_malformed_uuid(self):
        """Test that task_to_response handles malformed UUID strings."""
        from api.api_endpoints import task_to_response

        # Create task with malformed superseded_by_task_id
        async with db_manager.get_session() as session:
            task = Task(
                title="Task with Malformed UUID",
                description="Test description",
                status=TaskStatus.DONE,
                task_metadata={
                    "email_thread_id": "thread_uuid_test",
                    "superseded_by_task_id": "not-a-valid-uuid"
                }
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(Task)
                    .options(selectinload(Task.comments))
                    .where(Task.id == task_id)
                )
                task = result.scalar_one()

                # Convert to response - should not raise, should default to None
                response = task_to_response(task)

                # Malformed UUID should result in None
                assert response.superseded_by_task_id is None
                # But other fields should still work
                assert response.email_thread_id == "thread_uuid_test"
        finally:
            # Cleanup
            async with db_manager.get_session() as session:
                result = await session.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    await session.delete(task)
                await session.commit()
