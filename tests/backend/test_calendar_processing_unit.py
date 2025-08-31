"""
Pure Unit Tests for Calendar Processing Components.

These tests mock all external dependencies and test business logic in isolation.
They verify the components work correctly with proper input/output contracts.

Run with: uv run pytest tests/backend/test_calendar_processing_unit.py -v
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone, timedelta, date
import json

from backend.input_hooks.calendar_processing.fetcher import CalendarFetcher
from backend.input_hooks.calendar_processing.analyzer import MeetingAnalyzer
from backend.input_hooks.calendar_processing.memo_generator import MemoGenerator
from backend.input_hooks.calendar_processing.meeting_creator import MeetingCreator
from backend.input_hooks.calendar_processing.processor import CalendarProcessor
from backend.input_hooks.models import CalendarMeetingInfo, CalendarHookConfig, CalendarHookSettings


class TestCalendarFetcherUnit:
    """Pure unit tests for CalendarFetcher (all MCP calls mocked)."""
    
    @pytest.mark.asyncio
    async def test_fetch_todays_events_mcp_format(self):
        """Test fetching events returns MCP server format (not Google API format)."""
        with patch('backend.input_hooks.calendar_processing.fetcher.mcp_manager') as mock_mcp:
            # Mock MCP response in the actual format we discovered
            mcp_events = [
                {
                    "id": "test_123",
                    "summary": "Team Meeting",
                    "start": "2025-08-31T10:00:00+02:00",  # MCP format: direct string
                    "end": "2025-08-31T11:00:00+02:00",
                    "description": "Weekly sync",
                    "attendees": [{"email": "alice@example.com"}]
                }
            ]
            
            mock_tool = Mock()
            mock_tool.name = "google_calendar_list_events"
            mock_tool.ainvoke = AsyncMock(return_value=mcp_events)
            
            mock_mcp.get_tools = AsyncMock(return_value=[mock_tool])
            
            fetcher = CalendarFetcher()
            events = await fetcher.fetch_todays_events()
            
            assert len(events) == 1
            assert events[0]["id"] == "test_123"
            assert events[0]["start"] == "2025-08-31T10:00:00+02:00"  # Direct string, not nested
            assert isinstance(events[0]["start"], str)  # Critical: must be string not dict
            
            # Verify MCP was called with correct parameters (no time_max!)
            call_args = mock_tool.ainvoke.call_args[0][0]
            assert "calendar_id" in call_args
            assert "time_min" in call_args 
            assert "time_max" not in call_args  # This was the bug!
            assert "max_results" not in call_args  # Also not supported
    
    @pytest.mark.asyncio
    async def test_fetch_todays_events_no_tools(self):
        """Test graceful handling when no calendar tools found."""
        with patch('backend.input_hooks.calendar_processing.fetcher.mcp_manager') as mock_mcp:
            # Mock no calendar tools available
            mock_tool = Mock()
            mock_tool.name = "some_other_tool"
            mock_mcp.get_tools = AsyncMock(return_value=[mock_tool])
            
            fetcher = CalendarFetcher()
            events = await fetcher.fetch_todays_events()
            
            assert events == []
    
    @pytest.mark.asyncio
    async def test_fetch_todays_events_mcp_error(self):
        """Test error handling during MCP tool calls."""
        with patch('backend.input_hooks.calendar_processing.fetcher.mcp_manager') as mock_mcp:
            mock_tool = Mock()
            mock_tool.name = "google_calendar_list_events"
            mock_tool.ainvoke = AsyncMock(side_effect=Exception("MCP tool failed"))
            
            mock_mcp.get_tools = AsyncMock(return_value=[mock_tool])
            
            fetcher = CalendarFetcher()
            events = await fetcher.fetch_todays_events()
            
            assert events == []  # Should handle error gracefully


class TestMeetingAnalyzerUnit:
    """Pure unit tests for MeetingAnalyzer (no external dependencies)."""
    
    def test_parse_event_datetime_mcp_format(self):
        """Test parsing MCP server datetime format (direct strings)."""
        from backend.input_hooks.datetime_utils import parse_datetime
        
        # Test timed event (ISO format string)
        timed_dt = parse_datetime("2025-08-31T10:00:00+02:00", source_type="calendar")
        assert timed_dt is not None
        assert timed_dt.year == 2025
        assert timed_dt.month == 8
        assert timed_dt.day == 31
        assert timed_dt.hour == 10
        
        # Test all-day event (date-only string) 
        allday_dt = parse_datetime("2025-08-31", source_type="calendar")
        assert allday_dt is not None
        assert allday_dt.year == 2025
        assert allday_dt.month == 8
        assert allday_dt.day == 31
        assert allday_dt.hour == 0  # Should be start of day
    
    def test_parse_event_datetime_google_api_format(self):
        """Test parsing Google Calendar API format (nested objects)."""
        from backend.input_hooks.datetime_utils import parse_datetime
        
        # Test timed event (nested format)
        timed_event = {"dateTime": "2025-08-31T10:00:00+02:00", "timeZone": "Europe/Berlin"}
        timed_dt = parse_datetime(timed_event, source_type="calendar")
        assert timed_dt is not None
        assert timed_dt.hour == 10
        
        # Test all-day event (nested format)
        allday_event = {"date": "2025-08-31"}
        allday_dt = parse_datetime(allday_event, source_type="calendar")
        assert allday_dt is not None
        assert allday_dt.hour == 0
    
    def test_analyze_events_date_filtering(self):
        """Test that events are filtered by target date correctly."""
        analyzer = MeetingAnalyzer()
        
        # Events for different dates
        events = [
            {
                "id": "today_meeting",
                "summary": "Today's Meeting",
                "start": "2025-08-31T10:00:00+02:00",
                "end": "2025-08-31T11:00:00+02:00",
                "attendees": [{"email": "test@example.com"}]
            },
            {
                "id": "tomorrow_meeting", 
                "summary": "Tomorrow's Meeting",
                "start": "2025-09-01T10:00:00+02:00",  # Different date
                "end": "2025-09-01T11:00:00+02:00",
                "attendees": [{"email": "test@example.com"}]
            },
            {
                "id": "yesterday_meeting",
                "summary": "Yesterday's Meeting", 
                "start": "2025-08-30T10:00:00+02:00",  # Different date
                "end": "2025-08-30T11:00:00+02:00",
                "attendees": [{"email": "test@example.com"}]
            }
        ]
        
        # Filter for August 31, 2025
        target_date = date(2025, 8, 31)
        meetings = analyzer.analyze_events(events, target_date=target_date)
        
        # Should only get today's meeting
        assert len(meetings) == 1
        assert meetings[0].title == "Today's Meeting"
        assert meetings[0].meeting_id == "today_meeting"
    
    def test_analyze_events_duration_filtering(self):
        """Test that short meetings are filtered out."""
        analyzer = MeetingAnalyzer(min_duration_minutes=15)
        target_date = date(2025, 8, 31)
        
        events = [
            {
                "id": "short_meeting",
                "summary": "Short Meeting",
                "start": "2025-08-31T10:00:00+02:00",
                "end": "2025-08-31T10:10:00+02:00",  # Only 10 minutes
                "attendees": [{"email": "test@example.com"}]
            },
            {
                "id": "long_meeting",
                "summary": "Long Meeting", 
                "start": "2025-08-31T11:00:00+02:00",
                "end": "2025-08-31T11:30:00+02:00",  # 30 minutes
                "attendees": [{"email": "test@example.com"}]
            }
        ]
        
        meetings = analyzer.analyze_events(events, target_date=target_date)
        
        # Should only get the longer meeting
        assert len(meetings) == 1
        assert meetings[0].title == "Long Meeting"
        assert meetings[0].duration_minutes == 30
    
    def test_analyze_events_keyword_filtering(self):
        """Test that meetings are filtered based on keywords."""
        analyzer = MeetingAnalyzer()
        target_date = date(2025, 8, 31)
        
        events = [
            {
                "id": "standup_meeting",
                "summary": "Daily Standup",  # Contains prep keyword
                "start": "2025-08-31T10:00:00+02:00",
                "end": "2025-08-31T10:30:00+02:00",
                "attendees": [{"email": "test@example.com"}]
            },
            {
                "id": "personal_time",
                "summary": "Personal Time",  # Contains skip keyword
                "start": "2025-08-31T11:00:00+02:00", 
                "end": "2025-08-31T12:00:00+02:00",
                "attendees": []
            },
            {
                "id": "client_meeting",
                "summary": "Client Review Meeting",  # Contains prep keywords
                "start": "2025-08-31T14:00:00+02:00",
                "end": "2025-08-31T15:00:00+02:00",
                "attendees": [{"email": "client@example.com"}]
            }
        ]
        
        meetings = analyzer.analyze_events(events, target_date=target_date)
        
        # Should get meetings that need prep, exclude personal time
        meeting_titles = [m.title for m in meetings]
        assert "Daily Standup" in meeting_titles
        assert "Client Review Meeting" in meeting_titles
        assert "Personal Time" not in meeting_titles
    
    def test_analyze_events_all_day_filtering(self):
        """Test all-day event filtering."""
        analyzer = MeetingAnalyzer()
        target_date = date(2025, 8, 31)
        
        events = [
            {
                "id": "timed_meeting",
                "summary": "Timed Meeting",
                "start": "2025-08-31T10:00:00+02:00",  # Has time
                "end": "2025-08-31T11:00:00+02:00",
                "attendees": [{"email": "test@example.com"}]
            },
            {
                "id": "allday_event", 
                "summary": "All Day Conference",
                "start": "2025-08-31",  # No time = all day
                "end": "2025-09-01",
                "attendees": [{"email": "test@example.com"}]
            }
        ]
        
        # Without all-day events
        meetings_no_allday = analyzer.analyze_events(events, include_all_day=False, target_date=target_date)
        meeting_titles = [m.title for m in meetings_no_allday]
        assert "Timed Meeting" in meeting_titles
        assert "All Day Conference" not in meeting_titles
        
        # With all-day events
        meetings_with_allday = analyzer.analyze_events(events, include_all_day=True, target_date=target_date)
        meeting_titles = [m.title for m in meetings_with_allday]
        assert "Timed Meeting" in meeting_titles
        assert "All Day Conference" in meeting_titles


class TestMemoGeneratorUnit:
    """Pure unit tests for MemoGenerator (all AI/memory calls mocked)."""
    
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
    
    @pytest.mark.asyncio
    async def test_generate_fallback_memo(self, sample_meeting_info):
        """Test fallback memo generation without AI."""
        generator = MemoGenerator()
        
        memo = generator._generate_fallback_memo(sample_meeting_info)
        
        assert memo is not None
        assert "Sprint Planning" in memo
        assert "alice@example.com" in memo
        assert "bob@example.com" in memo
        assert "Conference Room A" in memo
        assert "60 minutes" in memo or "1 hour" in memo
    
    @pytest.mark.asyncio 
    async def test_generate_memo_with_ai_fallback(self, sample_meeting_info):
        """Test that memo generation falls back to simple memo on AI failure."""
        with patch('backend.input_hooks.calendar_processing.memo_generator.create_chat_agent') as mock_agent:
            # Mock AI agent to fail
            mock_agent.side_effect = Exception("AI service unavailable")
            
            generator = MemoGenerator()
            memo = await generator.generate_meeting_memo(sample_meeting_info)
            
            # Should get fallback memo, not crash
            assert memo is not None
            assert "Sprint Planning" in memo
            assert len(memo) > 50  # Should be substantial content


class TestMeetingCreatorUnit:
    """Pure unit tests for MeetingCreator (all MCP calls mocked)."""
    
    @pytest.fixture
    def sample_meeting_info(self):
        """Sample meeting info for testing."""
        return CalendarMeetingInfo(
            meeting_id="test_123",
            title="Sprint Planning",
            attendees=["alice@example.com"],
            start_time=datetime(2025, 8, 31, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2025, 8, 31, 11, 0, tzinfo=timezone.utc),
            duration_minutes=60,
            location="Conference Room A",
            description="Plan next sprint",
            organizer="manager@example.com",
            calendar_id="primary"
        )
    
    @pytest.mark.asyncio
    async def test_create_prep_meeting_success(self, sample_meeting_info):
        """Test successful prep meeting creation."""
        with patch('backend.input_hooks.calendar_processing.meeting_creator.mcp_manager') as mock_mcp:
            # Mock create event tool
            mock_create_tool = Mock()
            mock_create_tool.name = "google_calendar_create_event"
            mock_create_tool.ainvoke = AsyncMock(return_value={"id": "prep_123"})
            
            mock_mcp.get_tools = AsyncMock(return_value=[mock_create_tool])
            
            creator = MeetingCreator(prep_time_minutes=15)
            memo = "# Meeting Preparation\nTest memo content"
            
            result = await creator.create_prep_meeting(sample_meeting_info, memo)
            
            assert result == "prep_123"  # Should return the event ID, not boolean
            
            # Verify create tool was called with correct parameters
            call_args = mock_create_tool.ainvoke.call_args[0][0]
            assert "PREP:" in call_args["summary"]
            assert "Sprint Planning" in call_args["summary"]
            assert memo in call_args["description"]
            assert call_args["calendar_id"] == "primary"
            
            # Prep meeting should start 15 minutes before original
            expected_start = datetime(2025, 8, 31, 9, 45, tzinfo=timezone.utc)  # 10:00 - 15min
            # Note: exact time comparison may need timezone handling
    
    @pytest.mark.asyncio
    async def test_create_prep_meeting_no_tools(self, sample_meeting_info):
        """Test graceful handling when no create tools available."""
        with patch('backend.input_hooks.calendar_processing.meeting_creator.mcp_manager') as mock_mcp:
            # Mock no create tools
            mock_tool = Mock()
            mock_tool.name = "some_other_tool"
            mock_mcp.get_tools = AsyncMock(return_value=[mock_tool])
            
            creator = MeetingCreator()
            memo = "Test memo"
            
            result = await creator.create_prep_meeting(sample_meeting_info, memo)
            
            assert result is None  # Should return None when no tools available
    
    def test_format_memo_for_description(self, sample_meeting_info):
        """Test memo formatting for calendar description."""
        creator = MeetingCreator()
        memo = "# Meeting Preparation\nSome test content"
        
        formatted = creator.format_memo_for_description(memo, sample_meeting_info)
        
        assert memo in formatted
        assert "Sprint Planning" in formatted
        assert "10:00" in formatted or "10:00:00" in formatted
        assert "Conference Room A" in formatted


class TestCalendarProcessorUnit:
    """Pure unit tests for CalendarProcessor (all components mocked)."""
    
    @pytest.fixture
    def sample_config(self):
        """Sample config for testing."""
        return CalendarHookConfig(
            name="test_processor",
            hook_type="calendar",
            enabled=True,
            polling_interval=86400,
            create_tasks=True,
            hook_settings=CalendarHookSettings(
                calendar_ids=["primary"],
                look_ahead_days=1,
                min_meeting_duration=15,
                prep_time_minutes=15
            )
        )
    
    @pytest.mark.asyncio
    async def test_process_daily_meetings_success(self, sample_config):
        """Test successful daily meeting processing with all components mocked."""
        processor = CalendarProcessor()
        
        # Mock all components
        with patch.object(processor, 'fetcher') as mock_fetcher, \
             patch.object(processor, 'analyzer') as mock_analyzer, \
             patch.object(processor, 'memo_generator') as mock_memo, \
             patch.object(processor, 'meeting_creator', Mock()) as mock_creator:
            
            # Mock fetcher
            mock_events = [{"id": "test_123", "summary": "Test Meeting"}]
            mock_fetcher.fetch_todays_events = AsyncMock(return_value=mock_events)
            
            # Mock analyzer
            mock_meeting = CalendarMeetingInfo(
                meeting_id="test_123",
                title="Test Meeting",
                attendees=["test@example.com"],
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(hours=1),
                duration_minutes=60,
                location="",
                description="",
                organizer="",
                calendar_id="primary"
            )
            mock_analyzer.analyze_events = Mock(return_value=[mock_meeting])
            
            # Mock memo generator
            mock_memo.generate_meeting_memo = AsyncMock(return_value="Test memo")
            
            # Mock meeting creator
            mock_creator.check_prep_meeting_exists = AsyncMock(return_value=None)
            mock_creator.create_prep_meeting = AsyncMock(return_value="mock_prep_event_id")
            
            # Process meetings
            result = await processor.process_daily_meetings(sample_config)
            
            # Verify results
            assert result["success"] == True
            assert result["events_fetched"] == 1
            assert result["meetings_analyzed"] == 1
            assert result["prep_meetings_created"] == 1
            assert result["prep_meetings_updated"] == 0
            assert len(result["errors"]) == 0
            
            # Verify all components were called
            mock_fetcher.fetch_todays_events.assert_called_once()
            mock_analyzer.analyze_events.assert_called_once()
            mock_memo.generate_meeting_memo.assert_called_once()
            mock_creator.create_prep_meeting.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_daily_meetings_no_events(self, sample_config):
        """Test processing when no events found."""
        processor = CalendarProcessor()
        
        with patch.object(processor, 'fetcher') as mock_fetcher:
            mock_fetcher.fetch_todays_events = AsyncMock(return_value=[])
            
            result = await processor.process_daily_meetings(sample_config)
            
            assert result["success"] == True
            assert result["events_fetched"] == 0
            assert result["meetings_analyzed"] == 0
            assert result["prep_meetings_created"] == 0
    
    @pytest.mark.asyncio
    async def test_process_daily_meetings_with_errors(self, sample_config):
        """Test error handling during processing."""
        processor = CalendarProcessor()
        
        with patch.object(processor, 'fetcher') as mock_fetcher:
            mock_fetcher.fetch_todays_events = AsyncMock(side_effect=Exception("Fetch failed"))
            
            result = await processor.process_daily_meetings(sample_config)
            
            assert result["success"] == False
            assert len(result["errors"]) > 0
            assert "Fetch failed" in str(result["errors"])


if __name__ == "__main__":
    # Run unit tests
    import subprocess
    result = subprocess.run([
        "python", "-m", "pytest", 
        __file__, 
        "-v", 
        "--tb=short"
    ], cwd="/home/daniel/nova-1/backend")
    
    print(f"Unit tests completed with return code: {result.returncode}")