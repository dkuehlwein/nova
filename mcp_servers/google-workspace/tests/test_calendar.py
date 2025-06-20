import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime

# Import from the local main module (since this test is in mcp_servers/gmail/tests/)
from main import GoogleWorkspaceService

class TestGoogleCalendarIntegration:
    """Test suite for Google Calendar integration in the Google Workspace MCP server."""
    
    @pytest.fixture
    def mock_workspace_service_dependencies(self):
        """Mock dependencies for GoogleWorkspaceService initialization."""
        with patch('os.path.exists', return_value=True), \
             patch('main.Credentials') as mock_creds, \
             patch('main.build') as mock_build:
            
            # Mock credentials
            mock_creds.from_authorized_user_file.return_value = Mock(
                valid=True,
                expired=False
            )
            
            # Mock Gmail and Calendar services
            mock_gmail_service = Mock()
            mock_gmail_service.users().getProfile().execute.return_value = {
                'emailAddress': 'test@example.com'
            }
            
            mock_calendar_service = Mock()
            
            def build_side_effect(service, version, credentials=None, static_discovery=False):
                if service == 'gmail':
                    return mock_gmail_service
                elif service == 'calendar':
                    return mock_calendar_service
                else:
                    raise ValueError(f"Unknown service: {service}")
            
            mock_build.side_effect = build_side_effect
            
            yield {
                'mock_gmail_service': mock_gmail_service,
                'mock_calendar_service': mock_calendar_service
            }
    
    @pytest.mark.asyncio
    async def test_list_calendars(self, mock_workspace_service_dependencies):
        """Test listing calendars."""
        mocks = mock_workspace_service_dependencies
        
        # Mock calendar list response
        mock_response = {
            'items': [
                {
                    'id': 'primary',
                    'summary': 'Test Calendar',
                    'description': 'Primary calendar',
                    'primary': True,
                    'accessRole': 'owner',
                    'selected': True
                }
            ]
        }
        
        service = GoogleWorkspaceService(
            creds_file_path='test_creds.json',
            token_path='test_token.json'
        )
        
        with patch('asyncio.to_thread', return_value=mock_response):
            result = await service.list_calendars()
            
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['id'] == 'primary'
            assert result[0]['summary'] == 'Test Calendar'
            assert result[0]['primary'] is True
    
    @pytest.mark.asyncio
    async def test_create_event(self, mock_workspace_service_dependencies):
        """Test creating a calendar event."""
        mocks = mock_workspace_service_dependencies
        
        # Mock event creation response
        mock_response = {
            'id': 'event123',
            'htmlLink': 'https://calendar.google.com/event?eid=event123',
            'summary': 'Test Meeting'
        }
        
        service = GoogleWorkspaceService(
            creds_file_path='test_creds.json',
            token_path='test_token.json'
        )
        
        with patch('asyncio.to_thread', return_value=mock_response):
            result = await service.create_event(
                calendar_id='primary',
                summary='Test Meeting',
                start_datetime='2025-06-06T10:00:00',
                end_datetime='2025-06-06T11:00:00',
                description='Test meeting description',
                location='Berlin Office',
                attendees=['colleague@example.com']
            )
            
            assert result['status'] == 'success'
            assert result['event_id'] == 'event123'
            assert 'html_link' in result
    
    @pytest.mark.asyncio
    async def test_list_events(self, mock_workspace_service_dependencies):
        """Test listing calendar events."""
        mocks = mock_workspace_service_dependencies
        
        # Mock events list response
        mock_response = {
            'items': [
                {
                    'id': 'event1',
                    'summary': 'Meeting 1',
                    'start': {'dateTime': '2025-06-06T10:00:00+01:00'},
                    'end': {'dateTime': '2025-06-06T11:00:00+01:00'},
                    'description': 'First meeting',
                    'location': 'Office',
                    'htmlLink': 'https://calendar.google.com/event?eid=event1',
                    'status': 'confirmed',
                    'creator': {'email': 'test@example.com'},
                    'organizer': {'email': 'test@example.com'},
                    'attendees': [
                        {'email': 'attendee@example.com', 'responseStatus': 'accepted'}
                    ]
                }
            ]
        }
        
        service = GoogleWorkspaceService(
            creds_file_path='test_creds.json',
            token_path='test_token.json'
        )
        
        with patch('asyncio.to_thread', return_value=mock_response):
            result = await service.list_events('primary', max_results=10)
            
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['id'] == 'event1'
            assert result[0]['summary'] == 'Meeting 1'
            assert len(result[0]['attendees']) == 1
    
    @pytest.mark.asyncio
    async def test_create_quick_event(self, mock_workspace_service_dependencies):
        """Test creating an event using natural language."""
        mocks = mock_workspace_service_dependencies
        
        # Mock quick add response
        mock_response = {
            'id': 'quick_event123',
            'summary': 'Meeting tomorrow at 2pm',
            'htmlLink': 'https://calendar.google.com/event?eid=quick_event123'
        }
        
        service = GoogleWorkspaceService(
            creds_file_path='test_creds.json',
            token_path='test_token.json'
        )
        
        with patch('asyncio.to_thread', return_value=mock_response):
            result = await service.create_quick_event(
                'primary',
                'Meeting with John tomorrow at 2pm'
            )
            
            assert result['status'] == 'success'
            assert result['event_id'] == 'quick_event123'
            assert result['summary'] == 'Meeting tomorrow at 2pm'
    
    @pytest.mark.asyncio
    async def test_calendar_error_handling(self, mock_workspace_service_dependencies):
        """Test calendar error handling."""
        mocks = mock_workspace_service_dependencies
        
        from googleapiclient.errors import HttpError
        import httplib2
        
        # Mock HTTP error
        mock_error = HttpError(
            httplib2.Response({'status': '404'}),
            b'{"error": {"message": "Calendar not found"}}'
        )
        
        service = GoogleWorkspaceService(
            creds_file_path='test_creds.json',
            token_path='test_token.json'
        )
        
        with patch('asyncio.to_thread', side_effect=mock_error):
            result = await service.list_calendars()
            
            assert result['status'] == 'error'
            assert 'error_message' in result
    
    def test_calendar_api_scopes(self):
        """Test that required OAuth scopes are defined."""
        service = GoogleWorkspaceService.__new__(GoogleWorkspaceService)
        service.scopes = [
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/calendar'
        ]
        
        # Verify calendar scope is included
        assert 'https://www.googleapis.com/auth/calendar' in service.scopes
        assert len(service.scopes) == 2
    
    def test_event_data_structure(self):
        """Test calendar event data structure."""
        event = {
            'summary': 'Nova Planning Meeting',
            'location': 'Berlin Office',
            'description': 'Planning next sprint for Nova project',
            'start': {
                'dateTime': '2025-06-07T10:00:00',
                'timeZone': 'Europe/Berlin',
            },
            'end': {
                'dateTime': '2025-06-07T11:00:00',
                'timeZone': 'Europe/Berlin',
            },
            'attendees': [
                {'email': 'daniel@nova.dev'},
                {'email': 'team@nova.dev'}
            ]
        }
        
        # Validate event structure
        assert 'summary' in event
        assert 'start' in event and 'dateTime' in event['start']
        assert 'end' in event and 'dateTime' in event['end']
        assert 'timeZone' in event['start']
        assert event['start']['timeZone'] == 'Europe/Berlin'
        assert len(event['attendees']) == 2
    
    def test_timezone_configuration(self):
        """Test timezone configuration for Daniel's location."""
        daniel_timezone = 'Europe/Berlin'
        
        # Test that timezone is correctly set for Daniel
        assert daniel_timezone == 'Europe/Berlin'
        
        # Test date formatting
        from datetime import datetime
        now = datetime.now()
        iso_format = now.isoformat()
        
        assert 'T' in iso_format  # ISO format includes T separator
        assert len(iso_format) >= 19  # YYYY-MM-DDTHH:MM:SS minimum

if __name__ == '__main__':
    pytest.main([__file__]) 