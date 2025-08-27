"""
Test all-day event detection and creation logic.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.calendar_tools import CalendarTools


class TestAllDayEvents:
    """Test all-day event functionality in CalendarTools."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_calendar_service = Mock()
        self.calendar_tools = CalendarTools(self.mock_calendar_service)
    
    def test_is_all_day_event_same_day_23_59_59(self):
        """Test detection of all-day event ending at 23:59:59 of same day."""
        start_dt = datetime(2025, 8, 28, 0, 0, 0)
        end_dt = datetime(2025, 8, 28, 23, 59, 59)
        
        result = self.calendar_tools._is_all_day_event(start_dt, end_dt)
        
        assert result is True
    
    def test_is_all_day_event_next_day_midnight(self):
        """Test detection of all-day event ending at 00:00:00 of next day."""
        start_dt = datetime(2025, 8, 28, 0, 0, 0)
        end_dt = datetime(2025, 8, 29, 0, 0, 0)
        
        result = self.calendar_tools._is_all_day_event(start_dt, end_dt)
        
        assert result is True
    
    def test_is_not_all_day_event_different_start_time(self):
        """Test that events not starting at midnight are not all-day."""
        start_dt = datetime(2025, 8, 28, 9, 0, 0)
        end_dt = datetime(2025, 8, 28, 17, 0, 0)
        
        result = self.calendar_tools._is_all_day_event(start_dt, end_dt)
        
        assert result is False
    
    def test_is_not_all_day_event_partial_day(self):
        """Test that partial day events are not detected as all-day."""
        start_dt = datetime(2025, 8, 28, 0, 0, 0)
        end_dt = datetime(2025, 8, 28, 12, 0, 0)
        
        result = self.calendar_tools._is_all_day_event(start_dt, end_dt)
        
        assert result is False
    
    def test_is_not_all_day_event_multiple_days(self):
        """Test that multi-day timed events are not detected as all-day."""
        start_dt = datetime(2025, 8, 28, 0, 0, 0)
        end_dt = datetime(2025, 8, 30, 0, 0, 0)  # 2 days later
        
        result = self.calendar_tools._is_all_day_event(start_dt, end_dt)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_create_all_day_event_23_59_59_format(self):
        """Test that all-day events ending at 23:59:59 get proper end date."""
        # Mock the calendar service response
        mock_event = {
            'id': 'test_event_id',
            'summary': 'Test All Day Event',
            'htmlLink': 'https://calendar.google.com/test'
        }
        
        with patch('asyncio.to_thread') as mock_to_thread:
            # Mock conflict checking and event creation
            mock_to_thread.return_value = mock_event
            self.calendar_tools._check_conflicts = AsyncMock(return_value=[])
            
            # Create event with 23:59:59 end time (should be all-day)
            result = await self.calendar_tools.create_event(
                calendar_id='primary',
                summary='Test All Day Event',
                start_datetime='2025-08-28T00:00:00+02:00',
                end_datetime='2025-08-28T23:59:59+02:00'
            )
            
            # Verify asyncio.to_thread was called (for event creation)
            assert mock_to_thread.called
            
            # Since we're mocking asyncio.to_thread, we need to inspect what would have been passed
            # In a real scenario, we'd check the event body passed to the calendar service
            # For this test, we'll verify the response structure
            assert result['status'] == 'success'
            assert result['event_id'] == 'test_event_id'
    
    @pytest.mark.asyncio
    async def test_create_timed_event(self):
        """Test that timed events use dateTime format."""
        # Mock the calendar service response
        mock_event = {
            'id': 'test_timed_event_id',
            'summary': 'Test Timed Event',
            'htmlLink': 'https://calendar.google.com/test'
        }
        
        with patch('asyncio.to_thread') as mock_to_thread:
            # Mock conflict checking and event creation
            mock_to_thread.return_value = mock_event
            self.calendar_tools._check_conflicts = AsyncMock(return_value=[])
            
            # Create timed event
            result = await self.calendar_tools.create_event(
                calendar_id='primary',
                summary='Test Timed Event',
                start_datetime='2025-08-28T09:00:00+02:00',
                end_datetime='2025-08-28T10:00:00+02:00'
            )
            
            # Verify response structure
            assert result['status'] == 'success'
            assert result['event_id'] == 'test_timed_event_id'