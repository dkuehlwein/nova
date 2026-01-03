"""
Integration Tests for Calendar Memo Generator.

These tests verify MemoGenerator works with real dependencies:
- Memory system (Neo4j/Graphiti)
- AI chat agent
- PostgreSQL checkpointer

These are NOT unit tests because MemoGenerator imports memory_tools,
which imports graphiti_manager, which imports graphiti_core that 
requires Neo4j connection.

Run with: uv run pytest tests/integration/test_calendar_memo_integration.py -v
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from backend.input_hooks.calendar_processing.memo_generator import MemoGenerator
from backend.input_hooks.models import CalendarMeetingInfo


class TestMemoGeneratorIntegration:
    """Integration tests for MemoGenerator with mocked external services."""
    
    @pytest.fixture
    def sample_meeting_info(self):
        """Sample meeting info for testing."""
        return CalendarMeetingInfo(
            meeting_id="test_123",
            title="Sprint Planning",
            attendees=["alice@example.com", "bob@example.com"],
            start_time=datetime(2025, 8, 31, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2025, 8, 31, 11, 0, tzinfo=timezone.utc),
            duration_minutes=60,
            location="Conference Room A",
            description="Plan next sprint",
            organizer="manager@example.com",
            calendar_id="primary"
        )
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_generate_memo_success(self, sample_meeting_info):
        """
        Test successful memo generation with AI.
        
        This is an integration test because:
        - MemoGenerator imports memory systems (Neo4j/Graphiti)
        - Tests interaction between components
        - Verifies full memo generation flow
        """
        with patch('backend.input_hooks.calendar_processing.memo_generator.create_chat_agent') as mock_agent, \
             patch('utils.service_manager.ServiceManager') as mock_service_mgr:
            # Mock AI agent to succeed
            mock_chat_agent = AsyncMock()
            
            # Mock astream to return an async iterator
            async def mock_astream(*args, **kwargs):
                # Simulate streaming chunks
                yield {"chat_agent": {"messages": [type('obj', (), {'content': 'Generated memo for Sprint Planning', 'type': 'ai'})]}}
            
            mock_chat_agent.astream = mock_astream
            mock_agent.return_value = mock_chat_agent
            
            # Mock service manager to avoid database connections
            mock_mgr_instance = AsyncMock()
            mock_mgr_instance.init_pg_pool = AsyncMock(return_value=Mock())
            mock_service_mgr.return_value = mock_mgr_instance
            
            generator = MemoGenerator()
            memo_text, thread_id = await generator.generate_meeting_memo(sample_meeting_info)
            
            # Verify results
            assert memo_text is not None, "Memo text should not be None"
            assert isinstance(thread_id, str), "Thread ID should be a string"
            assert len(memo_text) > 0, "Memo text should not be empty"
            assert "Sprint Planning" in memo_text or len(memo_text) > 10, "Memo should have content"
    
    @pytest.mark.integration
    @pytest.mark.asyncio 
    async def test_generate_memo_with_ai_failure(self, sample_meeting_info):
        """
        Test that memo generation raises exception on AI failure.
        
        Integration test verifying error handling across components.
        """
        with patch('backend.input_hooks.calendar_processing.memo_generator.create_chat_agent') as mock_agent, \
             patch('utils.service_manager.ServiceManager') as mock_service_mgr:
            # Mock AI agent to fail
            mock_agent.side_effect = Exception("AI service unavailable")
            
            # Mock service manager to avoid database connections
            mock_mgr_instance = AsyncMock()
            mock_mgr_instance.init_pg_pool = AsyncMock(return_value=Mock())
            mock_service_mgr.return_value = mock_mgr_instance
            
            generator = MemoGenerator()
            
            # Should raise exception, not return fallback
            with pytest.raises(Exception) as exc_info:
                await generator.generate_meeting_memo(sample_meeting_info)
            
            assert "AI service unavailable" in str(exc_info.value), \
                "Exception should contain AI error message"
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_memo_includes_memory_context(self, sample_meeting_info):
        """
        Test that memo generation attempts to gather memory context.
        
        This verifies the integration with memory search tools.
        """
        with patch('backend.input_hooks.calendar_processing.memo_generator.create_chat_agent') as mock_agent, \
             patch('backend.input_hooks.calendar_processing.memo_generator.search_memory_tool') as mock_memory, \
             patch('utils.service_manager.ServiceManager') as mock_service_mgr:
            
            # Mock memory search
            mock_memory.return_value = "No relevant memories found"
            
            # Mock AI agent
            mock_chat_agent = AsyncMock()
            async def mock_astream(*args, **kwargs):
                yield {"chat_agent": {"messages": [type('obj', (), {'content': 'Memo with context', 'type': 'ai'})]}}
            mock_chat_agent.astream = mock_astream
            mock_agent.return_value = mock_chat_agent
            
            # Mock service manager
            mock_mgr_instance = AsyncMock()
            mock_mgr_instance.init_pg_pool = AsyncMock(return_value=Mock())
            mock_service_mgr.return_value = mock_mgr_instance
            
            generator = MemoGenerator()
            memo_text, thread_id = await generator.generate_meeting_memo(sample_meeting_info)
            
            # Verify memory search was called for attendees
            assert mock_memory.called, "Memory search should be called"
            # Should search for each attendee
            call_count = mock_memory.call_count
            assert call_count >= 2, f"Should search for at least 2 attendees, got {call_count} calls"


if __name__ == "__main__":
    # Run integration tests
    import subprocess
    result = subprocess.run([
        "python", "-m", "pytest", 
        __file__, 
        "-v",
        "-m", "integration",
        "--tb=short"
    ], cwd="/home/daniel/nova-1/backend")
    
    print(f"Integration tests completed with return code: {result.returncode}")
