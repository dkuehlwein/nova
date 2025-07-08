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
    return AsyncMock()


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
        
        # Mock list() call for conflict checking
        mock_list_events = AsyncMock()
        mock_list_events.execute.return_value = {
            'items': [sample_existing_event]
        }
        mock_calendar_service.events.return_value.list.return_value = mock_list_events
        
        # Mock insert() call for event creation
        created_event = {
            'id': 'new_event_456',
            'summary': 'Kindergarten Closed',
            'start': {'dateTime': '2025-06-25T09:00:00+02:00'},
            'end': {'dateTime': '2025-06-25T17:00:00+02:00'},
            'htmlLink': 'https://calendar.google.com/event?eid=def456'
        }
        mock_insert_event = AsyncMock()
        mock_insert_event.execute.return_value = created_event
        mock_calendar_service.events.return_value.insert.return_value = mock_insert_event
        
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
        
        # Verify both list and insert were called
        mock_calendar_service.events.return_value.list.assert_called_once()
        mock_calendar_service.events.return_value.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_event_without_conflict(self, calendar_tools, mock_calendar_service):
        """Test creating an event with no conflicts."""
        
        # Mock list() call - no existing events
        mock_list_events = AsyncMock()
        mock_list_events.execute.return_value = {'items': []}
        mock_calendar_service.events.return_value.list.return_value = mock_list_events
        
        # Mock insert() call
        created_event = {
            'id': 'new_event_789',
            'summary': 'Team Meeting',
            'start': {'dateTime': '2025-06-26T14:00:00+02:00'},
            'end': {'dateTime': '2025-06-26T15:00:00+02:00'},
            'htmlLink': 'https://calendar.google.com/event?eid=ghi789'
        }
        mock_insert_event = AsyncMock()
        mock_insert_event.execute.return_value = created_event
        mock_calendar_service.events.return_value.insert.return_value = mock_insert_event
        
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
        
        # Mock get() call for retrieving existing event
        mock_get_event = AsyncMock()
        mock_get_event.execute.return_value = {
            'id': 'event_to_update',
            'summary': 'Important Meeting',
            'start': {'dateTime': '2025-06-25T08:00:00+02:00'},
            'end': {'dateTime': '2025-06-25T09:00:00+02:00'},
            'description': 'Original time',
            'location': 'Room B'
        }
        mock_calendar_service.events.return_value.get.return_value = mock_get_event
        
        # Mock list() call for conflict checking - returns conflicting event
        mock_list_events = AsyncMock()
        mock_list_events.execute.return_value = {
            'items': [sample_existing_event]
        }
        mock_calendar_service.events.return_value.list.return_value = mock_list_events
        
        # Mock update() call
        updated_event = {
            'id': 'event_to_update',
            'summary': 'Important Meeting',
            'start': {'dateTime': '2025-06-25T10:30:00+02:00'},
            'end': {'dateTime': '2025-06-25T11:30:00+02:00'},
            'htmlLink': 'https://calendar.google.com/event?eid=update123'
        }
        mock_update_event = AsyncMock()
        mock_update_event.execute.return_value = updated_event
        mock_calendar_service.events.return_value.update.return_value = mock_update_event
        
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
        
        # Mock list() call - returns the same event we're updating
        mock_list_events = AsyncMock()
        mock_list_events.execute.return_value = {
            'items': [event_being_updated]
        }
        mock_calendar_service.events.return_value.list.return_value = mock_list_events
        
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
        
        # Mock list() call
        mock_list_events = AsyncMock()
        mock_list_events.execute.return_value = {
            'items': [cancelled_event]
        }
        mock_calendar_service.events.return_value.list.return_value = mock_list_events
        
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
        
        mock_list_events = AsyncMock()
        mock_list_events.execute.return_value = {
            'items': [adjacent_event]
        }
        mock_calendar_service.events.return_value.list.return_value = mock_list_events
        
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
        
        # Mock list() call to raise an exception
        mock_list_events = AsyncMock()
        mock_list_events.execute.side_effect = Exception("Calendar API error")
        mock_calendar_service.events.return_value.list.return_value = mock_list_events
        
        conflicts = await calendar_tools._check_conflicts(
            calendar_id='primary',
            start_datetime='2025-06-25T10:00:00+02:00',
            end_datetime='2025-06-25T11:00:00+02:00'
        )
        
        # Should return empty list on error, not crash
        assert conflicts == []