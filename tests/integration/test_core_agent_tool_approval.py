"""
Integration tests for core agent tool approval handling.
Tests the unified interrupt handling system for both user questions and tool approvals.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy import select

from agent.core_agent import CoreAgent
from models.models import Task, TaskStatus, TaskComment
from database.database import db_manager


class TestCoreAgentToolApproval:
    """Test core agent's handling of tool approval interrupts."""

    @pytest.fixture
    async def sample_task(self):
        """Create a sample task for testing."""
        async with db_manager.get_session() as session:
            task = Task(
                title="Test Tool Approval Task",
                description="A task that will trigger tool approval interrupts",
                status=TaskStatus.NEW,
                tags=["test", "tool-approval"]
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            
            yield task
            
            # Clean up the task after test
            try:
                await session.delete(task)
                await session.commit()
            except Exception:
                pass  # Best effort cleanup

    @pytest.fixture
    def mock_pg_pool(self):
        """Mock PostgreSQL pool for core agent initialization."""
        return Mock()

    @pytest.mark.asyncio
    async def test_handle_tool_approval_interrupt(self, mock_pg_pool, sample_task):
        """Test that _handle_interrupt correctly handles tool approval requests."""
        # Create core agent instance
        core_agent = CoreAgent(mock_pg_pool)
        
        # Mock the interrupt data structure for tool approval
        mock_interrupts = [
            Mock(
                value={
                    "type": "tool_approval_request",
                    "tool_name": "create_task",
                    "tool_args": {"title": "New Task", "description": "Test task creation"}
                }
            )
        ]
        
        # Mock the update_task_tool function
        with patch('agent.core_agent.update_task_tool') as mock_update_task:
            mock_update_task.return_value = None
            
            # Call the unified handler
            await core_agent._handle_interrupt(sample_task, mock_interrupts)
            
            # Verify task was moved to NEEDS_REVIEW
            mock_update_task.assert_any_call(
                task_id=str(sample_task.id),
                status="needs_review"
            )
            
            # Verify comment was added with tool details
            comment_call = mock_update_task.call_args_list[1]
            assert comment_call[1]["task_id"] == str(sample_task.id)
            assert "create_task(title=New Task, description=Test task creation)" in comment_call[1]["comment"]
            assert "⏸️ Task paused" in comment_call[1]["comment"]

    @pytest.mark.asyncio
    async def test_handle_interrupt_routes_to_tool_approval(self, mock_pg_pool, sample_task):
        """Test that _handle_interrupt correctly handles tool approval interrupts."""
        core_agent = CoreAgent(mock_pg_pool)
        
        # Mock tool approval interrupt
        mock_interrupts = [
            Mock(
                value={
                    "type": "tool_approval_request",
                    "tool_name": "update_task",
                    "tool_args": {"status": "done"}
                }
            )
        ]
        
        # Mock the update_task_tool function
        with patch('agent.core_agent.update_task_tool') as mock_update_task:
            mock_update_task.return_value = None
            
            # Call the unified interrupt handler
            await core_agent._handle_interrupt(sample_task, mock_interrupts)
            
            # Verify task was moved to NEEDS_REVIEW
            mock_update_task.assert_any_call(
                task_id=str(sample_task.id),
                status="needs_review"
            )
            
            # Verify tool approval comment was added
            comment_call = mock_update_task.call_args_list[1]
            assert "update_task(status=done)" in comment_call[1]["comment"]
            assert "Core Agent is requesting permission to use tool" in comment_call[1]["comment"]

    @pytest.mark.asyncio
    async def test_handle_interrupt_routes_to_user_question(self, mock_pg_pool, sample_task):
        """Test that _handle_interrupt correctly handles user question interrupts."""
        core_agent = CoreAgent(mock_pg_pool)
        
        # Mock user question interrupt
        mock_interrupts = [
            Mock(
                value={
                    "type": "user_question",
                    "question": "Should I proceed with this task?",
                    "instructions": "Please respond to continue."
                }
            )
        ]
        
        # Mock the update_task_tool function
        with patch('agent.core_agent.update_task_tool') as mock_update_task:
            mock_update_task.return_value = None
            
            # Call the unified interrupt handler
            await core_agent._handle_interrupt(sample_task, mock_interrupts)
            
            # Verify task was moved to NEEDS_REVIEW
            mock_update_task.assert_any_call(
                task_id=str(sample_task.id),
                status="needs_review"
            )
            
            # Verify user question comment was added
            comment_call = mock_update_task.call_args_list[1]
            assert "Should I proceed with this task?" in comment_call[1]["comment"]
            assert "Core Agent is requesting human input" in comment_call[1]["comment"]

    @pytest.mark.asyncio
    async def test_handle_interrupt_unknown_type_defaults_to_user_question(self, mock_pg_pool, sample_task):
        """Test that unknown interrupt types default to user question handling."""
        core_agent = CoreAgent(mock_pg_pool)
        
        # Mock unknown interrupt type
        mock_interrupts = [
            Mock(
                value={
                    "type": "unknown_type",
                    "data": "some data"
                }
            )
        ]
        
        # Mock the update_task_tool function
        with patch('agent.core_agent.update_task_tool') as mock_update_task:
            mock_update_task.return_value = None
            
            # Call the unified interrupt handler
            await core_agent._handle_interrupt(sample_task, mock_interrupts)
            
            # Verify task was moved to NEEDS_REVIEW
            mock_update_task.assert_any_call(
                task_id=str(sample_task.id),
                status="needs_review"
            )
            
            # Verify default user question comment was added
            comment_call = mock_update_task.call_args_list[1]
            assert "Core Agent is requesting human input" in comment_call[1]["comment"]

    @pytest.mark.asyncio
    async def test_tool_approval_comment_formatting(self, mock_pg_pool, sample_task):
        """Test that tool approval comments are formatted correctly."""
        core_agent = CoreAgent(mock_pg_pool)
        
        # Note: With the refactored design, we only handle one interrupt at a time
        # Test with a tool that has arguments
        mock_interrupts = [
            Mock(value={"type": "tool_approval_request", "tool_name": "create_task", "tool_args": {"title": "Task 1", "status": "new"}})
        ]
        
        with patch('agent.core_agent.update_task_tool') as mock_update_task:
            mock_update_task.return_value = None
            
            await core_agent._handle_interrupt(sample_task, mock_interrupts)
            
            # Get the comment from the second call
            comment_call = mock_update_task.call_args_list[1]
            comment = comment_call[1]["comment"]
            
            # Verify tool is formatted correctly
            assert "create_task(title=Task 1, status=new)" in comment
            assert "Core Agent is requesting permission to use tool:" in comment
            assert "⏸️ Task paused" in comment

    @pytest.mark.asyncio
    async def test_tool_approval_error_handling(self, mock_pg_pool, sample_task):
        """Test error handling in tool approval processing."""
        core_agent = CoreAgent(mock_pg_pool)
        
        mock_interrupts = [
            Mock(value={"type": "tool_approval_request", "tool_name": "test_tool", "tool_args": {}})
        ]
        
        # Mock update_task_tool to raise an exception
        with patch('agent.core_agent.update_task_tool') as mock_update_task:
            mock_update_task.side_effect = Exception("Database error")
            
            # Should not raise exception - error should be logged and handled
            await core_agent._handle_interrupt(sample_task, mock_interrupts)
            
            # Verify the function attempted to update the task
            assert mock_update_task.called