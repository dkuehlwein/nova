"""
Unit tests for Nova Core Agent

Tests for the autonomous task processing functionality using mocks 
following modern testing patterns.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from langchain_core.tools import tool

from agent.core_agent import CoreAgent
from models.models import Task, TaskStatus, TaskComment, AgentStatus, AgentStatusEnum


class FakeCoreAgentModel:
    """A fake model for testing core agent functionality."""
    
    def __init__(self, responses=None, should_escalate=False, escalation_question="Test question?"):
        self.responses = responses or ["Task processed successfully."]
        self.response_index = 0
        self.should_escalate = should_escalate
        self.escalation_question = escalation_question
        self.call_count = 0
        self._state = {"messages": []}
    
    async def aget_state(self, config):
        """Mock get state method for LangGraph agent."""
        return Mock(values=self._state, next=[], config=config)
    
    async def astream(self, messages_or_input, config, stream_mode=None):
        """Mock the LangGraph agent stream response."""
        self.call_count += 1
        
        # Handle both message format and input format
        if isinstance(messages_or_input, dict) and "messages" in messages_or_input:
            input_data = messages_or_input
        else:
            input_data = {"messages": messages_or_input}
        
        if self.should_escalate:
            # Simulate escalation interrupt with updates format
            yield {
                "agent": {
                    "messages": [Mock(content="I need to ask the user a question.")]
                }
            }
            yield {
                "__interrupt__": [Mock(value={
                    "type": "human_escalation", 
                    "question": self.escalation_question,
                    "instructions": "Please respond to continue."
                })]
            }
        else:
            # Normal response with updates format
            response = self.responses[self.response_index % len(self.responses)]
            self.response_index += 1
            yield {
                "agent": {
                    "messages": [Mock(content=response)]
                }
            }


@pytest.fixture
def mock_pg_pool():
    """Create a mock PostgreSQL pool for testing."""
    return Mock()


@pytest.fixture
def mock_task():
    """Create a mock task for testing."""
    task = Mock()
    task.id = uuid4()
    task.title = "Test Task"
    task.description = "Test task description"
    task.status = TaskStatus.NEW  # This already has .value = "new"
    task.created_at = datetime.utcnow()
    task.updated_at = datetime.utcnow()
    task.person_emails = []
    task.project_names = []
    task.comments = []
    task.tags = []  # Add tags attribute
    return task


@pytest.fixture
def mock_agent_status():
    """Create a mock agent status for testing."""
    status = Mock()
    status.id = uuid4()
    status.status = AgentStatusEnum.IDLE
    status.current_task_id = None
    status.last_activity = datetime.utcnow()
    status.total_tasks_processed = 0  # Integer, not Mock
    status.error_count = 0  # Integer, not Mock
    return status


class TestCoreAgentInitialization:
    """Test core agent initialization and setup."""
    
    @pytest.mark.asyncio
    async def test_core_agent_init(self, mock_pg_pool):
        """Test basic core agent initialization."""
        agent = CoreAgent(mock_pg_pool)
        
        assert agent.agent is None
        assert agent.status_id is None
        assert agent.is_running is False
        assert agent.should_stop is False
        assert agent.check_interval == 30
        assert agent.timeout_minutes == 30
        assert agent.pg_pool == mock_pg_pool
    
    @pytest.mark.asyncio
    async def test_initialize_creates_agent_and_status(self, mock_agent_status, mock_pg_pool):
        """Test that initialize creates LangGraph agent and status."""
        
        with patch('agent.core_agent.create_chat_agent') as mock_create_agent, \
             patch.object(CoreAgent, '_initialize_status') as mock_init_status:
            
            mock_create_agent.return_value = Mock()
            mock_init_status.return_value = None
            
            agent = CoreAgent(mock_pg_pool)
            await agent.initialize()
            
            # Verify agent was created with pg_pool
            mock_create_agent.assert_called_once_with(pg_pool=mock_pg_pool)
            assert agent.agent is not None
            
            # Verify status was initialized
            mock_init_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reload_agent(self, mock_pg_pool):
        """Test that reload_agent recreates the agent with updated prompt."""
        
        with patch('agent.core_agent.create_chat_agent') as mock_create_agent:
            mock_create_agent.return_value = Mock()
            
            agent = CoreAgent(mock_pg_pool)
            await agent.reload_agent()
            
            # Verify agent was recreated with pg_pool and use_cache=False
            mock_create_agent.assert_called_once_with(pg_pool=mock_pg_pool, use_cache=False)
            assert agent.agent is not None
    
    @pytest.mark.asyncio
    async def test_initialize_status_creates_new_record(self, mock_pg_pool):
        """Test that status initialization creates new record when none exists."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None  # No existing status
        mock_session.execute.return_value = mock_result
        
        # Mock session.add as regular Mock (not AsyncMock) since it's not async
        mock_session.add = Mock()
        
        # Mock session.refresh to simulate setting the ID after database insert
        def mock_refresh(obj):
            obj.id = uuid4()
        mock_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            await agent._initialize_status()
            
            # Verify database operations were performed
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()
            
            # Verify the status object that was added has correct properties
            added_status = mock_session.add.call_args[0][0]
            assert hasattr(added_status, 'status')
            assert hasattr(added_status, 'started_at')
            assert agent.status_id is not None
    
    @pytest.mark.asyncio
    async def test_initialize_status_resets_existing_record(self, mock_agent_status, mock_pg_pool):
        """Test that status initialization resets existing record."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_agent_status
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            await agent._initialize_status()
            
            # Verify existing status was reset
            assert mock_agent_status.status == AgentStatusEnum.IDLE
            assert mock_agent_status.current_task_id is None
            assert mock_agent_status.last_error is None
            mock_session.commit.assert_called_once()
            assert agent.status_id == mock_agent_status.id


class TestCoreAgentTaskSelection:
    """Test task selection logic."""
    
    @pytest.mark.asyncio
    async def test_get_next_task_prioritizes_user_input_received(self, mock_task, mock_pg_pool):
        """Test that tasks with USER_INPUT_RECEIVED status are prioritized."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            result = await agent._get_next_task()
            
            assert result == mock_task
            # Should have made two queries - first for USER_INPUT_RECEIVED, then for NEW
            assert mock_session.execute.call_count >= 1
    
    @pytest.mark.asyncio 
    async def test_get_next_task_falls_back_to_new_tasks(self, mock_task, mock_pg_pool):
        """Test that if no USER_INPUT_RECEIVED tasks, it falls back to NEW tasks."""
        
        mock_session = AsyncMock()
        mock_result_empty = Mock()
        mock_result_empty.scalar_one_or_none.return_value = None
        mock_result_with_task = Mock()
        mock_result_with_task.scalar_one_or_none.return_value = mock_task
        
        # First call (USER_INPUT_RECEIVED) returns None, second (NEW) returns task
        mock_session.execute.side_effect = [mock_result_empty, mock_result_with_task]
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            result = await agent._get_next_task()
            
            assert result == mock_task
            assert mock_session.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_next_task_returns_none_when_no_tasks(self, mock_pg_pool):
        """Test that None is returned when no tasks are available."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            result = await agent._get_next_task()
            
            assert result is None


class TestCoreAgentStatusManagement:
    """Test agent status management functionality."""
    
    @pytest.mark.asyncio
    async def test_is_busy_returns_false_when_idle(self, mock_agent_status, mock_pg_pool):
        """Test that _is_busy returns False when agent is idle."""
        
        mock_agent_status.status = AgentStatusEnum.IDLE
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_agent_status  # Use scalar_one for _is_busy
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            agent.status_id = mock_agent_status.id
            result = await agent._is_busy()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_is_busy_returns_true_when_processing(self, mock_agent_status, mock_pg_pool):
        """Test that _is_busy returns True when agent is processing."""
        
        mock_agent_status.status = AgentStatusEnum.PROCESSING
        mock_agent_status.last_activity = datetime.utcnow()  # Recent activity
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_agent_status
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            agent.status_id = mock_agent_status.id
            result = await agent._is_busy()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_is_busy_handles_timeout(self, mock_agent_status, mock_pg_pool):
        """Test that _is_busy handles timeout scenarios correctly."""
        
        mock_agent_status.status = AgentStatusEnum.PROCESSING
        # Set activity to be older than timeout
        mock_agent_status.last_activity = datetime.utcnow() - timedelta(minutes=35)
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_agent_status
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session, \
             patch.object(CoreAgent, '_set_idle') as mock_set_idle:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            agent.status_id = mock_agent_status.id
            agent.timeout_minutes = 30
            result = await agent._is_busy()
            
            # Should detect timeout and return False
            assert result is False
            # Should have called _set_idle
            mock_set_idle.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_busy_updates_status(self, mock_agent_status, mock_task, mock_pg_pool):
        """Test that _set_busy correctly updates status."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_agent_status  # Use scalar_one
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            agent.status_id = mock_agent_status.id
            await agent._set_busy(mock_task.id)
            
            assert mock_agent_status.status == AgentStatusEnum.PROCESSING
            assert mock_agent_status.current_task_id == mock_task.id
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_idle_updates_status(self, mock_agent_status, mock_pg_pool):
        """Test that _set_idle correctly updates status."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_agent_status
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            agent.status_id = mock_agent_status.id
            await agent._set_idle()
            
            assert mock_agent_status.status == AgentStatusEnum.IDLE
            assert mock_agent_status.current_task_id is None
            assert mock_agent_status.total_tasks_processed == 1  # Should increment by 1
            mock_session.commit.assert_called_once()


class TestCoreAgentTaskProcessing:
    """Test task processing functionality."""
    
    @pytest.mark.asyncio
    async def test_process_task_with_mock_methods(self, mock_task, mock_pg_pool):
        """Test that _process_task calls the expected methods."""
        
        # Create fake agent that doesn't escalate
        fake_agent = FakeCoreAgentModel(should_escalate=False)
        
        with patch.object(CoreAgent, '_move_task_to_in_progress') as mock_move, \
             patch.object(CoreAgent, '_get_context') as mock_get_context, \
             patch.object(CoreAgent, '_create_task_messages') as mock_create_msgs:
            
            mock_get_context.return_value = {"memory_context": [], "comments": []}
            mock_create_msgs.return_value = [Mock(content="test message")]
            
            agent = CoreAgent(mock_pg_pool)
            agent.agent = fake_agent
            
            await agent._process_task(mock_task)
            
            # Verify expected method calls
            mock_move.assert_called_once_with(mock_task)
            mock_get_context.assert_called_once_with(mock_task)
            assert fake_agent.call_count == 1
    
    @pytest.mark.asyncio
    async def test_process_task_skips_completed_tasks(self, mock_task, mock_pg_pool):
        """Test that _process_task skips already completed tasks."""
        
        mock_task.status = TaskStatus.DONE  # Already completed
        
        with patch.object(CoreAgent, '_move_task_to_in_progress') as mock_move:
            agent = CoreAgent(mock_pg_pool)
            await agent._process_task(mock_task)
            
            # Should not try to move task
            mock_move.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_task_error_sets_failed_status(self, mock_task, mock_pg_pool):
        """Test that _handle_task_error correctly handles failures."""
        
        error_msg = "Test error message"
        
        with patch('agent.core_agent.update_task_tool') as mock_update, \
             patch('agent.core_agent.add_task_comment_tool') as mock_comment:
            
            agent = CoreAgent(mock_pg_pool)
            await agent._handle_task_error(mock_task, error_msg)
            
            # Should update task to failed
            mock_update.assert_called_once_with(
                task_id=str(mock_task.id),
                status="failed"
            )
            
            # Should add error comment
            mock_comment.assert_called_once_with(
                task_id=str(mock_task.id),
                content=f"Core Agent encountered an error while processing this task:\n\n{error_msg}",
                author="core_agent"
            )


class TestCoreAgentIntegration:
    """Test core agent integration functionality."""
    
    @pytest.mark.asyncio
    async def test_force_process_task_success(self, mock_task, mock_pg_pool):
        """Test force processing a specific task."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session, \
             patch.object(CoreAgent, '_process_task') as mock_process:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            result = await agent.force_process_task(str(mock_task.id))
            
            assert "processed successfully" in result
            mock_process.assert_called_once_with(mock_task)
    
    @pytest.mark.asyncio
    async def test_force_process_task_invalid_id(self, mock_pg_pool):
        """Test force processing with invalid task ID."""
        
        agent = CoreAgent(mock_pg_pool)
        
        with pytest.raises(ValueError, match="Invalid task ID format"):
            await agent.force_process_task("invalid-uuid")
    
    @pytest.mark.asyncio
    async def test_force_process_task_not_found(self, mock_pg_pool):
        """Test force processing with non-existent task ID."""
        
        task_id = str(uuid4())
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None  # Task not found
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent(mock_pg_pool)
            
            with pytest.raises(ValueError, match="Task not found"):
                await agent.force_process_task(task_id)
    
    @pytest.mark.asyncio
    async def test_shutdown_gracefully(self, mock_pg_pool):
        """Test graceful shutdown of the agent."""
        
        with patch.object(CoreAgent, '_set_idle') as mock_set_idle, \
             patch('agent.chat_agent.clear_chat_agent_cache') as mock_clear_cache:
            
            agent = CoreAgent(mock_pg_pool)
            agent.status_id = uuid4()
            agent.is_running = True
            
            # Start shutdown - should be quick since is_running will be set to False
            await agent.shutdown()
            
            # Should have called cleanup methods
            mock_set_idle.assert_called_once()
            mock_clear_cache.assert_called_once()


class TestCoreAgentEscalationFlow:
    """Test human escalation functionality."""
    
    @pytest.mark.asyncio
    async def test_escalation_workflow_with_fake_agent(self, mock_task, mock_pg_pool):
        """Test complete escalation workflow with a fake agent that escalates."""
        
        # Create fake agent that escalates
        fake_agent = FakeCoreAgentModel(
            should_escalate=True, 
            escalation_question="Do you want to proceed with this task?"
        )
        
        with patch.object(CoreAgent, '_move_task_to_in_progress') as mock_move, \
             patch.object(CoreAgent, '_get_context') as mock_get_context, \
             patch.object(CoreAgent, '_create_task_messages') as mock_create_msgs, \
             patch.object(CoreAgent, '_handle_human_escalation') as mock_escalation:
            
            mock_get_context.return_value = {"memory_context": [], "comments": []}
            mock_create_msgs.return_value = [Mock(content="test message")]
            
            agent = CoreAgent(mock_pg_pool)
            agent.agent = fake_agent
            
            await agent._process_task(mock_task)
            
            # Verify escalation path was taken
            mock_move.assert_called_once_with(mock_task)
            mock_get_context.assert_called_once_with(mock_task)
            mock_escalation.assert_called_once()
            
            # Verify escalation was called with correct data
            escalation_call_args = mock_escalation.call_args
            assert escalation_call_args[0][0] == mock_task  # First arg is task
            # Second arg should be interrupt data
            interrupt_data = escalation_call_args[0][1]
            assert len(interrupt_data) == 1  # Should have one interrupt 