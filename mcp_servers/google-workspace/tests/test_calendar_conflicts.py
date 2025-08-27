"""
Test calendar conflict detection functionality.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
import json

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.calendar_tools import CalendarTools


@pytest.fixture
def mock_calendar_service():
    """Mock Google Calendar API service."""
    service = Mock()
    # Mock the nested structure calendar_service.events().list().execute
    service.events.return_value.list.return_value.execute = Mock()
    service.events.return_value.insert.return_value.execute = Mock()
    service.events.return_value.get.return_value.execute = Mock()
    service.events.return_value.update.return_value.execute = Mock()
    return service


@pytest.fixture
def calendar_tools(mock_calendar_service):
    """Create CalendarTools instance with mocked service."""
    return CalendarTools(mock_calendar_service)


@pytest.fixture
def sample_existing_event():
    """Sample existing calendar event."""
    return {
        'id': 'existing_event_123',
        'summary': 'Project Sync',
        'start': {
            'dateTime': '2025-06-25T10:00:00+02:00',
            'timeZone': 'Europe/Berlin'
        },
        'end': {
            'dateTime': '2025-06-25T11:00:00+02:00',
            'timeZone': 'Europe/Berlin'
        },
        'status': 'confirmed',
        'location': 'Conference Room A',
        'organizer': {'email': 'user@example.com'},
        'htmlLink': 'https://calendar.google.com/event?eid=abc123'
    }


class TestCalendarConflictDetection:
    """Test calendar conflict detection functionality."""

    @pytest.mark.asyncio
    async def test_create_event_with_conflict(self, calendar_tools, mock_calendar_service, sample_existing_event):
        """Test creating an event that conflicts with existing event."""
        
        # Mock the asyncio.to_thread calls
        created_event = {
            'id': 'new_event_456',
            'summary': 'Kindergarten Closed',
            'start': {'dateTime': '2025-06-25T09:00:00+02:00'},
            'end': {'dateTime': '2025-06-25T17:00:00+02:00'},
            'htmlLink': 'https://calendar.google.com/event?eid=def456'
        }
        
        list_response = {'items': [sample_existing_event]}
        
        with patch('asyncio.to_thread') as mock_to_thread:
            # Set up side effects for different API calls
            mock_to_thread.side_effect = [
                list_response,  # First call: conflict checking
                created_event   # Second call: event creation
            ]
            
            # Create conflicting event (all-day event that overlaps Project Sync)
            result = await calendar_tools.create_event(
                calendar_id='primary',
                summary='Kindergarten Closed',
                start_datetime='2025-06-25T09:00:00+02:00',
                end_datetime='2025-06-25T17:00:00+02:00',
                description='The kindergarten will be closed for the entire day'
            )
            
            # Verify event was created
            assert result['status'] == 'success'
            assert result['event_id'] == 'new_event_456'
            assert result['summary'] == 'Kindergarten Closed'
            
            # Verify conflicts were detected
            assert result['conflicts_detected'] is True
            assert len(result['conflicts']) == 1
            assert result['conflicts'][0]['summary'] == 'Project Sync'
            assert result['conflicts'][0]['id'] == 'existing_event_123'
            assert 'conflict_summary' in result
            
            # Verify asyncio.to_thread was called twice (conflict check + event creation)
            assert mock_to_thread.call_count == 2

    @pytest.mark.asyncio
    async def test_create_event_without_conflict(self, calendar_tools, mock_calendar_service):
        """Test creating an event with no conflicts."""
        
        created_event = {
            'id': 'new_event_789',
            'summary': 'Team Meeting',
            'start': {'dateTime': '2025-06-26T14:00:00+02:00'},
            'end': {'dateTime': '2025-06-26T15:00:00+02:00'},
            'htmlLink': 'https://calendar.google.com/event?eid=ghi789'
        }
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.side_effect = [
                {'items': []},  # First call: no conflicts
                created_event   # Second call: event creation
            ]
            
            result = await calendar_tools.create_event(
                calendar_id='primary',
                summary='Team Meeting',
                start_datetime='2025-06-26T14:00:00+02:00',
                end_datetime='2025-06-26T15:00:00+02:00'
            )
            
            # Verify event was created without conflicts
            assert result['status'] == 'success'
            assert result['event_id'] == 'new_event_789'
            assert result['conflicts_detected'] is False
            assert len(result['conflicts']) == 0
            assert 'conflict_summary' not in result

    @pytest.mark.asyncio
    async def test_update_event_with_new_conflicts(self, calendar_tools, mock_calendar_service, sample_existing_event):
        """Test updating an event time that creates new conflicts."""
        
        existing_event = {
            'id': 'event_to_update',
            'summary': 'Important Meeting',
            'start': {'dateTime': '2025-06-25T08:00:00+02:00'},
            'end': {'dateTime': '2025-06-25T09:00:00+02:00'},
            'description': 'Original time',
            'location': 'Room B'
        }
        
        updated_event = {
            'id': 'event_to_update',
            'summary': 'Important Meeting',
            'start': {'dateTime': '2025-06-25T10:30:00+02:00'},
            'end': {'dateTime': '2025-06-25T11:30:00+02:00'},
            'htmlLink': 'https://calendar.google.com/event?eid=update123'
        }
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.side_effect = [
                existing_event,  # First call: get existing event
                {'items': [sample_existing_event]},  # Second call: conflict checking
                updated_event    # Third call: update event
            ]
            
            # Update event to a conflicting time
            result = await calendar_tools.update_event(
                calendar_id='primary',
                event_id='event_to_update',
                start_datetime='2025-06-25T10:30:00+02:00',
                end_datetime='2025-06-25T11:30:00+02:00'
            )
            
            # Verify update completed with conflict detection
            assert result['status'] == 'success'
            assert result['event_id'] == 'event_to_update'
            assert result['conflicts_detected'] is True
            assert len(result['conflicts']) == 1
            assert result['conflicts'][0]['summary'] == 'Project Sync'
            assert 'conflict_summary' in result

    @pytest.mark.asyncio
    async def test_conflict_detection_excludes_self(self, calendar_tools, mock_calendar_service):
        """Test that conflict detection excludes the event being updated."""
        
        event_being_updated = {
            'id': 'self_event',
            'summary': 'Self Event',
            'start': {'dateTime': '2025-06-25T10:00:00+02:00'},
            'end': {'dateTime': '2025-06-25T11:00:00+02:00'},
            'status': 'confirmed'
        }
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = {'items': [event_being_updated]}
            
            # Check conflicts, excluding self
            conflicts = await calendar_tools._check_conflicts(
                calendar_id='primary',
                start_datetime='2025-06-25T10:00:00+02:00',
                end_datetime='2025-06-25T11:00:00+02:00',
                exclude_event_id='self_event'
            )
            
            # Should find no conflicts since we exclude the event itself
            assert len(conflicts) == 0

    @pytest.mark.asyncio
    async def test_conflict_detection_skips_cancelled_events(self, calendar_tools, mock_calendar_service):
        """Test that cancelled events are not considered conflicts."""
        
        cancelled_event = {
            'id': 'cancelled_event',
            'summary': 'Cancelled Meeting',
            'start': {'dateTime': '2025-06-25T10:00:00+02:00'},
            'end': {'dateTime': '2025-06-25T11:00:00+02:00'},
            'status': 'cancelled'  # This should be skipped
        }
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = {'items': [cancelled_event]}
            
            conflicts = await calendar_tools._check_conflicts(
                calendar_id='primary',
                start_datetime='2025-06-25T10:00:00+02:00',
                end_datetime='2025-06-25T11:00:00+02:00'
            )
            
            # Should find no conflicts since cancelled events are skipped
            assert len(conflicts) == 0

    @pytest.mark.asyncio
    async def test_conflict_detection_edge_cases(self, calendar_tools, mock_calendar_service):
        """Test edge cases for conflict detection (adjacent times, etc.)."""
        
        # Event that ends exactly when new event starts (no conflict)
        adjacent_event = {
            'id': 'adjacent_event',
            'summary': 'Adjacent Event',
            'start': {'dateTime': '2025-06-25T09:00:00+02:00'},
            'end': {'dateTime': '2025-06-25T10:00:00+02:00'},  # Ends when new starts
            'status': 'confirmed'
        }
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = {'items': [adjacent_event]}
            
            conflicts = await calendar_tools._check_conflicts(
                calendar_id='primary',
                start_datetime='2025-06-25T10:00:00+02:00',  # Starts when existing ends
                end_datetime='2025-06-25T11:00:00+02:00'
            )
            
            # Adjacent events should not be considered conflicts
            assert len(conflicts) == 0

    @pytest.mark.asyncio
    async def test_error_handling_in_conflict_detection(self, calendar_tools, mock_calendar_service):
        """Test that conflict detection gracefully handles errors."""
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.side_effect = Exception("Calendar API error")
            
            conflicts = await calendar_tools._check_conflicts(
                calendar_id='primary',
                start_datetime='2025-06-25T10:00:00+02:00',
                end_datetime='2025-06-25T11:00:00+02:00'
            )
            
            # Should return empty list on error, not crash
            assert conflicts == []


class TestCalendarHelperMethods:
    """Test the new helper methods added during refactoring."""

    @pytest.fixture
    def calendar_tools_for_helpers(self):
        """Create CalendarTools instance for testing helper methods."""
        mock_service = Mock()
        return CalendarTools(mock_service)

    def test_normalize_datetime_with_timezone(self, calendar_tools_for_helpers):
        """Test _normalize_datetime with timezone-aware datetime."""
        dt_string = '2025-06-25T10:00:00+02:00'
        result = calendar_tools_for_helpers._normalize_datetime(dt_string)
        
        assert result.tzinfo is not None
        assert result.hour == 10

    def test_normalize_datetime_without_timezone(self, calendar_tools_for_helpers):
        """Test _normalize_datetime with timezone-naive datetime."""
        dt_string = '2025-06-25T10:00:00'
        result = calendar_tools_for_helpers._normalize_datetime(dt_string)
        
        # Should add Berlin timezone
        assert result.tzinfo is not None
        assert result.hour == 10

    def test_format_event_info(self, calendar_tools_for_helpers):
        """Test _format_event_info helper method."""
        event = {
            'id': 'test_event_123',
            'summary': 'Test Meeting',
            'start': {'dateTime': '2025-06-25T10:00:00+02:00'},
            'end': {'dateTime': '2025-06-25T11:00:00+02:00'},
            'description': 'Test description',
            'location': 'Berlin Office',
            'htmlLink': 'https://calendar.google.com/event?eid=test123',
            'status': 'confirmed',
            'creator': {'email': 'creator@example.com'},
            'organizer': {'email': 'organizer@example.com'},
            'attendees': [{'email': 'attendee@example.com'}]
        }
        
        result = calendar_tools_for_helpers._format_event_info(event)
        
        assert result['id'] == 'test_event_123'
        assert result['summary'] == 'Test Meeting'
        assert result['start'] == '2025-06-25T10:00:00+02:00'
        assert result['end'] == '2025-06-25T11:00:00+02:00'
        assert result['description'] == 'Test description'
        assert result['location'] == 'Berlin Office'
        assert result['html_link'] == 'https://calendar.google.com/event?eid=test123'
        assert result['status'] == 'confirmed'
        assert len(result['attendees']) == 1

    def test_format_event_info_minimal_event(self, calendar_tools_for_helpers):
        """Test _format_event_info with minimal event data."""
        event = {
            'id': 'minimal_event',
            'start': {'dateTime': '2025-06-25T10:00:00+02:00'},
            'end': {'dateTime': '2025-06-25T11:00:00+02:00'}
        }
        
        result = calendar_tools_for_helpers._format_event_info(event)
        
        assert result['id'] == 'minimal_event'
        assert result['summary'] == 'No Title'  # Default value
        assert result['description'] == ''  # Default value
        assert result['location'] == ''  # Default value
        assert result['attendees'] == []  # Default value

    def test_should_skip_event_with_exclude_id(self, calendar_tools_for_helpers):
        """Test _should_skip_event excludes specific event ID."""
        event = {'id': 'event_to_exclude', 'status': 'confirmed'}
        
        result = calendar_tools_for_helpers._should_skip_event(event, 'event_to_exclude')
        assert result is True

    def test_should_skip_event_cancelled_status(self, calendar_tools_for_helpers):
        """Test _should_skip_event excludes cancelled events."""
        event = {'id': 'cancelled_event', 'status': 'cancelled'}
        
        result = calendar_tools_for_helpers._should_skip_event(event, None)
        assert result is True

    def test_should_skip_event_normal_event(self, calendar_tools_for_helpers):
        """Test _should_skip_event allows normal events."""
        event = {'id': 'normal_event', 'status': 'confirmed'}
        
        result = calendar_tools_for_helpers._should_skip_event(event, None)
        assert result is False

    def test_events_overlap_true(self, calendar_tools_for_helpers):
        """Test _events_overlap detects overlapping events."""
        from datetime import datetime
        from dateutil import tz
        
        berlin_tz = tz.gettz('Europe/Berlin')
        start1 = datetime(2025, 6, 25, 10, 0, tzinfo=berlin_tz)  # 10:00-11:00
        end1 = datetime(2025, 6, 25, 11, 0, tzinfo=berlin_tz)
        start2 = datetime(2025, 6, 25, 10, 30, tzinfo=berlin_tz)  # 10:30-11:30 (overlaps)
        end2 = datetime(2025, 6, 25, 11, 30, tzinfo=berlin_tz)
        
        result = calendar_tools_for_helpers._events_overlap(start1, end1, start2, end2)
        assert result is True

    def test_events_overlap_false_adjacent(self, calendar_tools_for_helpers):
        """Test _events_overlap returns false for adjacent events."""
        from datetime import datetime
        from dateutil import tz
        
        berlin_tz = tz.gettz('Europe/Berlin')
        start1 = datetime(2025, 6, 25, 10, 0, tzinfo=berlin_tz)  # 10:00-11:00
        end1 = datetime(2025, 6, 25, 11, 0, tzinfo=berlin_tz)
        start2 = datetime(2025, 6, 25, 11, 0, tzinfo=berlin_tz)  # 11:00-12:00 (adjacent)
        end2 = datetime(2025, 6, 25, 12, 0, tzinfo=berlin_tz)
        
        result = calendar_tools_for_helpers._events_overlap(start1, end1, start2, end2)
        assert result is False

    def test_create_conflict_response_with_conflicts(self, calendar_tools_for_helpers):
        """Test _create_conflict_response with conflicts detected."""
        event = {
            'id': 'test_event',
            'htmlLink': 'https://example.com',
            'summary': 'Test Event'
        }
        conflicts = [{'id': 'conflict1', 'summary': 'Conflicting Event'}]
        
        result = calendar_tools_for_helpers._create_conflict_response(event, conflicts)
        
        assert result['status'] == 'success'
        assert result['event_id'] == 'test_event'
        assert result['conflicts_detected'] is True
        assert len(result['conflicts']) == 1
        assert 'conflict_summary' in result

    def test_create_conflict_response_no_conflicts(self, calendar_tools_for_helpers):
        """Test _create_conflict_response with no conflicts."""
        event = {
            'id': 'test_event',
            'htmlLink': 'https://example.com',
            'summary': 'Test Event'
        }
        conflicts = []
        
        result = calendar_tools_for_helpers._create_conflict_response(event, conflicts)
        
        assert result['status'] == 'success'
        assert result['event_id'] == 'test_event'
        assert result['conflicts_detected'] is False
        assert len(result['conflicts']) == 0
        assert 'conflict_summary' not in result

    def test_handle_http_error(self, calendar_tools_for_helpers):
        """Test _handle_http_error creates proper error response."""
        from googleapiclient.errors import HttpError
        import httplib2
        
        error = HttpError(
            httplib2.Response({'status': '404'}),
            b'{"error": {"message": "Calendar not found"}}'
        )
        
        result = calendar_tools_for_helpers._handle_http_error(error, "testing operation")
        
        assert result['status'] == 'error'
        assert 'error_message' in result
        assert 'testing operation' in result['error_message']