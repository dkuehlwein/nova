"""
Tests for Nova Core Agent

Integration tests using real database for testing the autonomous task processing 
functionality including task discovery, status transitions, and AI processing.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from agent.core_agent import CoreAgent
from models.models import Task, TaskStatus, TaskComment, AgentStatus, AgentStatusEnum, Person, Project
from database.database import db_manager


@pytest_asyncio.fixture
async def core_agent():
    """Create a CoreAgent instance for testing with mocked AI but real database."""
    agent = CoreAgent()
    
    # Create AsyncMock for the AI agent only
    mock_langgraph_agent = AsyncMock()
    
    # Mock agent response
    async def mock_astream(*args, **kwargs):
        yield {
            "messages": [
                Mock(content="Task processed successfully by AI agent. Ready for review.")
            ]
        }
    
    mock_langgraph_agent.astream = AsyncMock(side_effect=mock_astream)
    agent.agent = mock_langgraph_agent
    
    # Initialize with real database
    await agent.initialize()
    
    yield agent
    
    # Cleanup after test
    try:
        await agent.shutdown()
    except:
        pass


@pytest_asyncio.fixture
async def sample_task():
    """Create a real task in the database for testing."""
    async with db_manager.get_session() as session:
        # Generate unique IDs to avoid conflicts
        test_id = str(uuid4())[:8]
        
        # Create test person and project with unique identifiers
        person = Person(
            id=uuid4(),
            name=f"Test User {test_id}",
            email=f"test-{test_id}@example.com",
            role="Developer"
        )
        session.add(person)
        
        project = Project(
            id=uuid4(),
            name=f"Test Project {test_id}",
            client="Test Client",
            summary="A test project for the core agent"
        )
        session.add(project)
        
        # Create task
        task = Task(
            id=uuid4(),
            title=f"Test Task for Core Agent {test_id}",
            description="This is a test task to verify core agent processing",
            status=TaskStatus.NEW,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            tags=["test", "core-agent"]
        )
        session.add(task)
        
        # Associate task with person and project
        task.persons.append(person)
        task.projects.append(project)
        
        await session.commit()
        await session.refresh(task)
        
        return task


@pytest_asyncio.fixture 
async def user_input_task():
    """Create a real USER_INPUT_RECEIVED task in the database for testing priority."""
    async with db_manager.get_session() as session:
        # Generate unique ID to avoid conflicts
        test_id = str(uuid4())[:8]
        
        task = Task(
            id=uuid4(),
            title=f"User Input Required Test Task {test_id}",
            description="This task requires user input and should be processed first",
            status=TaskStatus.USER_INPUT_RECEIVED,
            created_at=datetime.utcnow() - timedelta(hours=1),  # Older task
            updated_at=datetime.utcnow() - timedelta(hours=1),
            tags=["urgent", "user-input", "test"]
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        
        return task


class TestCoreAgentTaskProcessing:
    """Test core agent task processing functionality."""
    
    @pytest.mark.asyncio
    async def test_get_next_task_prioritizes_user_input_received(self, core_agent, sample_task, user_input_task):
        """Test that USER_INPUT_RECEIVED tasks are prioritized over NEW tasks."""
        
        # With both tasks in the database, should prioritize USER_INPUT_RECEIVED
        next_task = await core_agent._get_next_task()
        
        # Should find the USER_INPUT_RECEIVED task
        assert next_task is not None
        assert next_task.status == TaskStatus.USER_INPUT_RECEIVED
        assert "User Input Required" in next_task.title


    @pytest.mark.asyncio
    async def test_get_next_task_finds_new_tasks_when_no_user_input(self, core_agent, sample_task):
        """Test that NEW tasks are found when no USER_INPUT_RECEIVED tasks exist."""
        
        # Only NEW task in database, should find it
        next_task = await core_agent._get_next_task()
        
        # Should find the NEW task
        assert next_task is not None
        assert next_task.status == TaskStatus.NEW
        # Check that it's our test task (contains the base title)
        assert "Test Task for Core Agent" in next_task.title


    @pytest.mark.asyncio
    async def test_process_task_moves_to_in_progress(self, core_agent, sample_task):
        """Test that processing a task moves it to IN_PROGRESS status."""
        
        # Process the task
        await core_agent._process_task(sample_task)
        
        # Check the task status was updated in the database
        async with db_manager.get_session() as session:
            result = await session.get(Task, sample_task.id)
            assert result.status == TaskStatus.IN_PROGRESS
            
            # Check that a comment was added
            comments = [c for c in result.comments if c.author == 'core_agent']
            assert len(comments) > 0
            assert 'Core Agent processed this task' in comments[0].content


    @pytest.mark.asyncio
    async def test_process_task_creates_proper_prompt(self, core_agent, sample_task):
        """Test that task processing creates a proper AI prompt with context."""
        
        with patch('agent.core_agent.update_task_tool') as mock_update_task, \
             patch('agent.core_agent.add_task_comment_tool') as mock_add_comment:
            
            mock_update_task.return_value = None
            mock_add_comment.return_value = None
            
            # Process the task
            await core_agent._process_task(sample_task)
            
            # Verify AI agent was called with proper config
            core_agent.agent.astream.assert_called()
            call_args = core_agent.agent.astream.call_args
            
            # Check thread_id format
            config = call_args.kwargs['config']
            expected_thread_id = f"core_agent_task_{sample_task.id}"
            assert config.configurable['thread_id'] == expected_thread_id
            
            # Check prompt contains task information
            messages = call_args.args[0]['messages']
            prompt = messages[0]['content']
            
            assert sample_task.title in prompt
            assert sample_task.description in prompt
            assert str(sample_task.id) in prompt


    @pytest.mark.asyncio
    async def test_process_task_handles_ai_errors(self, core_agent, sample_task):
        """Test that AI processing errors are handled gracefully."""
        
        # Make AI agent raise an error
        async def mock_astream_error(*args, **kwargs):
            raise Exception("AI processing failed")
        
        core_agent.agent.astream = AsyncMock(side_effect=Exception("AI processing failed"))
        
        with patch('agent.core_agent.update_task_tool') as mock_update_task, \
             patch('agent.core_agent.add_task_comment_tool') as mock_add_comment:
            
            mock_update_task.return_value = None
            mock_add_comment.return_value = None
            
            # Process should raise the error
            with pytest.raises(Exception, match="AI processing failed"):
                await core_agent._process_task(sample_task)
            
            # But task should still be moved to IN_PROGRESS first
            mock_update_task.assert_called_with(
                task_id=str(sample_task.id),
                status="in_progress"
            )


    @pytest.mark.asyncio 
    async def test_handle_task_error_moves_to_failed(self, core_agent, sample_task):
        """Test that task errors move the task to FAILED status."""
        
        with patch('agent.core_agent.update_task_tool') as mock_update_task, \
             patch('agent.core_agent.add_task_comment_tool') as mock_add_comment:
            
            mock_update_task.return_value = None
            mock_add_comment.return_value = None
            
            error_msg = "Test error message"
            
            # Handle the error
            await core_agent._handle_task_error(sample_task, error_msg)
            
            # Verify task moved to FAILED
            mock_update_task.assert_called_with(
                task_id=str(sample_task.id),
                status="failed"  
            )
            
            # Verify error comment added
            mock_add_comment.assert_called_once()
            call_args = mock_add_comment.call_args
            assert call_args[1]['task_id'] == str(sample_task.id)
            assert call_args[1]['author'] == 'core_agent'
            assert error_msg in call_args[1]['content']


    @pytest.mark.asyncio
    async def test_agent_status_transitions(self, core_agent, sample_task):
        """Test that agent status properly transitions during task processing."""
        
        # Mock database operations
        mock_status = Mock()
        mock_status.id = core_agent.status_id
        mock_status.status = AgentStatusEnum.IDLE
        mock_status.current_task_id = None
        mock_status.last_activity = datetime.utcnow()
        mock_status.total_tasks_processed = 0
        mock_status.error_count = 0
        
        async def mock_execute(query):
            result = Mock()
            result.scalar_one.return_value = mock_status
            return result
        
        with patch.object(db_manager, 'get_session') as mock_session, \
             patch('agent.core_agent.update_task_tool'), \
             patch('agent.core_agent.add_task_comment_tool'):
            
            mock_session.return_value.__aenter__.return_value.execute = mock_execute
            mock_session.return_value.__aenter__.return_value.commit = AsyncMock()
            
            # Set busy
            await core_agent._set_busy(sample_task.id)
            assert mock_status.status == AgentStatusEnum.PROCESSING
            assert mock_status.current_task_id == sample_task.id
            
            # Set idle
            await core_agent._set_idle()
            assert mock_status.status == AgentStatusEnum.IDLE
            assert mock_status.current_task_id is None
            assert mock_status.total_tasks_processed == 1


class TestCoreAgentIntegration:
    """Integration tests for complete task processing workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_task_processing_workflow(self, core_agent, sample_task):
        """Test the complete workflow from task discovery to completion."""
        
        # Mock all database operations
        mock_status = Mock()
        mock_status.id = core_agent.status_id
        mock_status.status = AgentStatusEnum.IDLE
        mock_status.current_task_id = None
        mock_status.last_activity = datetime.utcnow()
        mock_status.total_tasks_processed = 0
        mock_status.error_count = 0
        
        task_found = False
        task_processed = False
        
        async def mock_execute(query):
            nonlocal task_found, task_processed
            
            result = Mock()
            
            # Agent status queries
            if "AgentStatus" in str(query):
                result.scalar_one.return_value = mock_status
                result.scalar_one_or_none.return_value = mock_status
                return result
            
            # Task selection queries  
            elif "USER_INPUT_RECEIVED" in str(query) and not task_found:
                result.scalar_one_or_none.return_value = None
                return result
            elif "NEW" in str(query) and not task_found:
                task_found = True
                result.scalar_one_or_none.return_value = sample_task
                return result
            else:
                # No more tasks after first one is processed
                result.scalar_one_or_none.return_value = None
                return result
        
        with patch.object(db_manager, 'get_session') as mock_session, \
             patch('agent.core_agent.update_task_tool') as mock_update_task, \
             patch('agent.core_agent.add_task_comment_tool') as mock_add_comment:
            
            mock_session.return_value.__aenter__.return_value.execute = mock_execute
            mock_session.return_value.__aenter__.return_value.commit = AsyncMock()
            mock_update_task.return_value = None
            mock_add_comment.return_value = None
            
            # Simulate one iteration of the processing loop
            # 1. Check if busy (should be idle)
            is_busy = await core_agent._is_busy()
            assert not is_busy
            
            # 2. Get next task (should find our sample task)
            next_task = await core_agent._get_next_task()
            assert next_task is not None
            assert next_task.id == sample_task.id
            
            # 3. Set busy and process task
            await core_agent._set_busy(next_task.id)
            assert mock_status.status == AgentStatusEnum.PROCESSING
            assert mock_status.current_task_id == next_task.id
            
            # 4. Process the task (should move to IN_PROGRESS and add comment)
            await core_agent._process_task(next_task)
            
            # 5. Set back to idle
            await core_agent._set_idle()
            assert mock_status.status == AgentStatusEnum.IDLE
            assert mock_status.current_task_id is None
            assert mock_status.total_tasks_processed == 1
            
            # Verify all the expected calls were made
            mock_update_task.assert_called_with(
                task_id=str(sample_task.id),
                status="in_progress"
            )
            
            mock_add_comment.assert_called_once()
            comment_call = mock_add_comment.call_args
            assert comment_call[1]['task_id'] == str(sample_task.id)
            assert comment_call[1]['author'] == 'core_agent'


    @pytest.mark.asyncio
    async def test_force_process_task(self, core_agent, sample_task):
        """Test the force process task functionality."""
        
        # Mock database operations
        async def mock_execute(query):
            result = Mock()
            if "Task" in str(query):
                result.scalar_one_or_none.return_value = sample_task
            return result
        
        with patch.object(db_manager, 'get_session') as mock_session, \
             patch('agent.core_agent.update_task_tool') as mock_update_task, \
             patch('agent.core_agent.add_task_comment_tool') as mock_add_comment:
            
            mock_session.return_value.__aenter__.return_value.execute = mock_execute
            mock_update_task.return_value = None
            mock_add_comment.return_value = None
            
            # Force process the task
            result = await core_agent.force_process_task(str(sample_task.id))
            
            assert "processed successfully" in result
            mock_update_task.assert_called_with(
                task_id=str(sample_task.id),
                status="in_progress"
            )


    @pytest.mark.asyncio
    async def test_invalid_task_id_force_process(self, core_agent):
        """Test force processing with invalid task ID."""
        
        with pytest.raises(ValueError, match="Invalid task ID format"):
            await core_agent.force_process_task("not-a-uuid")


    @pytest.mark.asyncio
    async def test_nonexistent_task_force_process(self, core_agent):
        """Test force processing with non-existent task."""
        
        task_id = str(uuid4())
        
        async def mock_execute(query):
            result = Mock()
            result.scalar_one_or_none.return_value = None
            return result
        
        with patch.object(db_manager, 'get_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.execute = mock_execute
            
            with pytest.raises(ValueError, match="Task not found"):
                await core_agent.force_process_task(task_id)


class TestCoreAgentErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_agent_timeout_detection(self, core_agent):
        """Test that stuck tasks are detected and reset."""
        
        # Create a status that appears stuck
        mock_status = Mock()
        mock_status.id = core_agent.status_id
        mock_status.status = AgentStatusEnum.PROCESSING
        mock_status.last_activity = datetime.utcnow() - timedelta(minutes=35)  # Older than timeout
        
        async def mock_execute(query):
            result = Mock()
            result.scalar_one.return_value = mock_status
            return result
        
        with patch.object(db_manager, 'get_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.execute = mock_execute
            mock_session.return_value.__aenter__.return_value.commit = AsyncMock()
            
            # Should detect timeout and reset to idle
            is_busy = await core_agent._is_busy()
            assert not is_busy
            assert mock_status.status == AgentStatusEnum.IDLE


    @pytest.mark.asyncio
    async def test_shutdown_gracefully(self, core_agent):
        """Test that agent shuts down gracefully."""
        
        # Mock status update
        with patch.object(core_agent, '_set_idle') as mock_set_idle:
            mock_set_idle.return_value = None
            
            # Test shutdown
            await core_agent.shutdown()
            
            assert core_agent.should_stop is True
            mock_set_idle.assert_called_once() 