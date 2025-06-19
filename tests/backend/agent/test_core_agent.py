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
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.chat_models.fake import FakeMessagesListChatModel

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
            # Simulate escalation interrupt
            yield {
                "messages": [Mock(content="I need to ask the user a question.")],
                "__interrupt__": [(
                    "escalate_to_human",
                    {
                        "type": "human_escalation", 
                        "question": self.escalation_question,
                        "instructions": "Please respond to continue."
                    }
                )]
            }
        else:
            # Normal response
            response = self.responses[self.response_index % len(self.responses)]
            self.response_index += 1
            yield {
                "messages": [Mock(content=response)]
            }


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
    task.persons = []
    task.projects = []
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


@pytest.fixture
def sample_tools():
    """Create sample tools for testing."""
    
    @tool
    def update_task_tool(task_id: str, status: str):
        """Update task status."""
        return f"Updated task {task_id} to {status}"
    
    @tool
    def add_task_comment_tool(task_id: str, content: str, author: str):
        """Add comment to task."""
        return f"Added comment to task {task_id}"
    
    @tool
    def escalate_to_human(question: str):
        """Escalate question to human."""
        return f"Escalated: {question}"
    
    return [update_task_tool, add_task_comment_tool, escalate_to_human]


class TestCoreAgentInitialization:
    """Test core agent initialization and setup."""
    
    @pytest.mark.asyncio
    async def test_core_agent_init(self):
        """Test basic core agent initialization."""
        agent = CoreAgent()
        
        assert agent.agent is None
        assert agent.status_id is None
        assert agent.is_running is False
        assert agent.should_stop is False
        assert agent.check_interval == 30
        assert agent.timeout_minutes == 30
    
    @pytest.mark.asyncio
    async def test_initialize_creates_agent_and_status(self, mock_agent_status):
        """Test that initialize creates LangGraph agent and status."""
        
        with patch('agent.core_agent.create_chat_agent') as mock_create_agent, \
             patch.object(CoreAgent, '_initialize_status') as mock_init_status:
            
            mock_create_agent.return_value = Mock()
            mock_init_status.return_value = None
            
            agent = CoreAgent()
            await agent.initialize()
            
            # Verify agent was created
            mock_create_agent.assert_called_once()
            assert agent.agent is not None
            
            # Verify status was initialized
            mock_init_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_status_creates_new_record(self):
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
            
            agent = CoreAgent()
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
    async def test_initialize_status_resets_existing_record(self, mock_agent_status):
        """Test that status initialization resets existing record."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_agent_status
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent()
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
    async def test_get_next_task_prioritizes_user_input_received(self, mock_task):
        """Test that tasks with USER_INPUT_RECEIVED status are prioritized."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent()
            result = await agent._get_next_task()
            
            assert result == mock_task
            # Should have made two queries - first for USER_INPUT_RECEIVED, then for NEW
            assert mock_session.execute.call_count >= 1
    
    @pytest.mark.asyncio 
    async def test_get_next_task_falls_back_to_new_tasks(self, mock_task):
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
            
            agent = CoreAgent()
            result = await agent._get_next_task()
            
            assert result == mock_task
            assert mock_session.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_next_task_returns_none_when_no_tasks(self):
        """Test that None is returned when no tasks are available."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent()
            result = await agent._get_next_task()
            
            assert result is None


class TestCoreAgentStatusManagement:
    """Test agent status management functionality."""
    
    @pytest.mark.asyncio
    async def test_is_busy_returns_false_when_idle(self, mock_agent_status):
        """Test that _is_busy returns False when agent is idle."""
        
        mock_agent_status.status = AgentStatusEnum.IDLE
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_agent_status  # Use scalar_one for _is_busy
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent()
            agent.status_id = mock_agent_status.id
            result = await agent._is_busy()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_is_busy_returns_true_when_processing(self, mock_agent_status):
        """Test that _is_busy returns True when agent is processing."""
        
        mock_agent_status.status = AgentStatusEnum.PROCESSING
        mock_agent_status.last_activity = datetime.utcnow()  # Recent activity
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_agent_status
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent()
            agent.status_id = mock_agent_status.id
            result = await agent._is_busy()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_is_busy_handles_timeout(self, mock_agent_status):
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
            
            agent = CoreAgent()
            agent.status_id = mock_agent_status.id
            agent.timeout_minutes = 30
            result = await agent._is_busy()
            
            # Should detect timeout and return False
            assert result is False
            # Should have called _set_idle
            mock_set_idle.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_busy_updates_status(self, mock_agent_status, mock_task):
        """Test that _set_busy correctly updates status."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_agent_status  # Use scalar_one
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent()
            agent.status_id = mock_agent_status.id
            await agent._set_busy(mock_task.id)
            
            assert mock_agent_status.status == AgentStatusEnum.PROCESSING
            assert mock_agent_status.current_task_id == mock_task.id
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_idle_updates_status(self, mock_agent_status):
        """Test that _set_idle correctly updates status."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_agent_status
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent()
            agent.status_id = mock_agent_status.id
            await agent._set_idle()
            
            assert mock_agent_status.status == AgentStatusEnum.IDLE
            assert mock_agent_status.current_task_id is None
            assert mock_agent_status.total_tasks_processed == 1  # Should increment by 1
            mock_session.commit.assert_called_once()


class TestCoreAgentTaskProcessing:
    """Test task processing functionality."""
    
    @pytest.mark.asyncio
    async def test_process_task_with_mock_methods(self, mock_task):
        """Test that _process_task calls the expected methods."""
        
        # Create fake agent that doesn't escalate
        fake_agent = FakeCoreAgentModel(should_escalate=False)
        
        with patch.object(CoreAgent, '_move_task_to_in_progress') as mock_move, \
             patch.object(CoreAgent, '_get_context') as mock_get_context, \
             patch.object(CoreAgent, '_create_task_messages') as mock_create_msgs, \
             patch.object(CoreAgent, '_update_context') as mock_update_context:
            
            mock_get_context.return_value = {"persons": [], "projects": [], "comments": []}
            mock_create_msgs.return_value = [Mock(content="test message")]
            
            agent = CoreAgent()
            agent.agent = fake_agent
            
            await agent._process_task(mock_task)
            
            # Verify expected method calls
            mock_move.assert_called_once_with(mock_task)
            mock_get_context.assert_called_once_with(mock_task)
            mock_update_context.assert_called_once()
            assert fake_agent.call_count == 1
    
    @pytest.mark.asyncio
    async def test_process_task_skips_completed_tasks(self, mock_task):
        """Test that _process_task skips already completed tasks."""
        
        mock_task.status = TaskStatus.DONE  # Already completed
        
        with patch.object(CoreAgent, '_move_task_to_in_progress') as mock_move:
            agent = CoreAgent()
            await agent._process_task(mock_task)
            
            # Should not try to move task
            mock_move.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_task_error_sets_failed_status(self, mock_task):
        """Test that _handle_task_error correctly handles failures."""
        
        error_msg = "Test error message"
        
        with patch('agent.core_agent.update_task_tool') as mock_update, \
             patch('agent.core_agent.add_task_comment_tool') as mock_comment:
            
            agent = CoreAgent()
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
    """Test core agent integration functionality with mocked dependencies."""
    
    @pytest.mark.asyncio
    async def test_force_process_task_success(self, mock_task):
        """Test successful force processing of a task."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session, \
             patch('agent.core_agent.create_chat_agent') as mock_create_agent, \
             patch.object(CoreAgent, '_initialize_status'), \
             patch.object(CoreAgent, '_process_task') as mock_process:
            
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_create_agent.return_value = Mock()
            
            agent = CoreAgent()
            await agent.initialize()
            
            result = await agent.force_process_task(str(mock_task.id))
            
            # Should return success message
            assert result == f"Task {mock_task.id} processed successfully"
            mock_process.assert_called_once_with(mock_task)
    
    @pytest.mark.asyncio
    async def test_force_process_task_invalid_id(self):
        """Test force process with invalid task ID raises ValueError."""
        
        agent = CoreAgent()
        
        with pytest.raises(ValueError, match="Invalid task ID format"):
            await agent.force_process_task("invalid-uuid")
    
    @pytest.mark.asyncio
    async def test_force_process_task_not_found(self):
        """Test force process when task is not found raises ValueError."""
        
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None  # Task not found
        mock_session.execute.return_value = mock_result
        
        with patch('agent.core_agent.db_manager.get_session') as mock_get_session, \
             patch('agent.core_agent.create_chat_agent'), \
             patch.object(CoreAgent, '_initialize_status'):
            
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            agent = CoreAgent()
            await agent.initialize()
            
            valid_uuid = str(uuid4())
            
            with pytest.raises(ValueError, match="Task not found"):
                await agent.force_process_task(valid_uuid)
    
    @pytest.mark.asyncio
    async def test_shutdown_gracefully(self):
        """Test graceful shutdown functionality."""
        
        agent = CoreAgent()
        agent.is_running = False  # Not running, so should shutdown quickly
        
        with patch.object(CoreAgent, '_set_idle') as mock_set_idle:
            agent.status_id = uuid4()  # Set status_id so _set_idle gets called
            
            await agent.shutdown()
            
            assert agent.should_stop is True
            mock_set_idle.assert_called_once()


class TestCoreAgentEscalationFlow:
    """Test escalation handling with mocked LangGraph agent."""
    
    @pytest.mark.asyncio
    async def test_escalation_workflow_with_fake_agent(self):
        """Test escalation workflow using controlled fake agent."""
        
        # Create escalating fake agent
        fake_agent = FakeCoreAgentModel(
            should_escalate=True,
            escalation_question="What's your favorite food?"
        )
        
        mock_task = Mock()
        mock_task.id = uuid4()
        mock_task.title = "Food Preference Task"
        mock_task.description = "Ask user for favorite food"
        mock_task.status = TaskStatus.NEW
        mock_task.tags = []
        mock_task.persons = []
        mock_task.projects = []
        mock_task.comments = []
        
        with patch.object(CoreAgent, '_move_task_to_in_progress') as mock_move, \
             patch.object(CoreAgent, '_get_context') as mock_get_context, \
             patch.object(CoreAgent, '_create_task_messages') as mock_create_msgs, \
             patch.object(CoreAgent, '_handle_human_escalation') as mock_escalation:
            
            mock_get_context.return_value = {"persons": [], "projects": [], "comments": []}
            mock_create_msgs.return_value = [Mock(content="test message")]
            
            agent = CoreAgent()
            agent.agent = fake_agent
            
            # Process the task
            await agent._process_task(mock_task)
            
            # Verify escalation workflow
            mock_escalation.assert_called_once()
            
            # Verify agent was called and escalated
            assert fake_agent.call_count == 1
            assert fake_agent.should_escalate is True 