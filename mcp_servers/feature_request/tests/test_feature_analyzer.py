"""Tests for FeatureRequestAnalyzer functionality."""

import pytest
from unittest.mock import AsyncMock, patch
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feature_analyzer import FeatureRequestAnalyzer
import src.feature_analyzer


class TestFeatureRequestAnalyzer:
    """Test AI-powered feature request analysis functionality."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a FeatureRequestAnalyzer instance for testing."""
        return FeatureRequestAnalyzer("gemini-1.5-flash")
    
    @pytest.mark.asyncio
    async def test_analyze_request_create_action(self, analyzer):
        """Test analysis resulting in create action."""
        mock_ai_response = {
            "action": "create",
            "reasoning": "This is a new feature not covered by existing issues",
            "title": "Add multi-attendee support to calendar events",
            "description": "**Problem**: Current create_calendar_event tool only accepts single attendee\n\n**Requirements**: Accept list of email addresses\n\n**Acceptance Criteria**: Tool can create events with multiple attendees",
            "priority": 2,
            "existing_issue_id": None
        }
        
        existing_issues = [
            {
                "id": "issue-1",
                "title": "Fix calendar timezone bug",
                "description": "Calendar events showing wrong timezone"
            }
        ]
        
        with patch('src.feature_analyzer.genai.GenerativeModel') as mock_model_class:
            mock_model = AsyncMock()
            mock_response = AsyncMock()
            mock_response.text = json.dumps(mock_ai_response)
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            result = await analyzer.analyze_request(
                "I need to create calendar events with multiple attendees",
                existing_issues
            )
            
            assert result["action"] == "create"
            assert result["title"] == "Add multi-attendee support to calendar events"
            assert result["priority"] == 2
            assert result["existing_issue_id"] is None
            assert "multiple attendees" in result["description"].lower()
    
    @pytest.mark.asyncio
    async def test_analyze_request_update_action(self, analyzer):
        """Test analysis resulting in update action."""
        mock_ai_response = {
            "action": "update",
            "reasoning": "This is related to the existing calendar timezone issue",
            "title": "Enhanced calendar timezone handling",
            "description": "**Problem**: Calendar timezone issues affecting multiple features\n\n**Requirements**: Comprehensive timezone fix\n\n**Acceptance Criteria**: All calendar operations handle timezones correctly",
            "priority": 1,
            "existing_issue_id": "issue-1"
        }
        
        existing_issues = [
            {
                "id": "issue-1",
                "title": "Fix calendar timezone bug",
                "description": "Calendar events showing wrong timezone"
            }
        ]
        
        with patch('src.feature_analyzer.genai.GenerativeModel') as mock_model_class:
            mock_model = AsyncMock()
            mock_response = AsyncMock()
            mock_response.text = json.dumps(mock_ai_response)
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            result = await analyzer.analyze_request(
                "Calendar events are showing in wrong timezone",
                existing_issues
            )
            
            assert result["action"] == "update"
            assert result["existing_issue_id"] == "issue-1"
            assert result["priority"] == 1
            assert "timezone" in result["description"].lower()
    
    @pytest.mark.asyncio
    async def test_analyze_request_with_json_code_blocks(self, analyzer):
        """Test handling of AI response wrapped in code blocks."""
        mock_ai_response = {
            "action": "create",
            "reasoning": "New feature request",
            "title": "Test Feature",
            "description": "Test description",
            "priority": 3,
            "existing_issue_id": None
        }
        
        # Simulate AI response wrapped in code blocks
        wrapped_response = f"```json\n{json.dumps(mock_ai_response)}\n```"
        
        with patch('src.feature_analyzer.genai.GenerativeModel') as mock_model_class:
            mock_model = AsyncMock()
            mock_response = AsyncMock()
            mock_response.text = wrapped_response
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            result = await analyzer.analyze_request("Test request", [])
            
            assert result["action"] == "create"
            assert result["title"] == "Test Feature"
            assert result["priority"] == 3
    
    @pytest.mark.asyncio
    async def test_analyze_request_empty_existing_issues(self, analyzer):
        """Test analysis with no existing issues."""
        mock_ai_response = {
            "action": "create",
            "reasoning": "No existing issues found, creating new one",
            "title": "New Feature Request",
            "description": "Test description",
            "priority": 3,
            "existing_issue_id": None
        }
        
        with patch('src.feature_analyzer.genai.GenerativeModel') as mock_model_class:
            mock_model = AsyncMock()
            mock_response = AsyncMock()
            mock_response.text = json.dumps(mock_ai_response)
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            result = await analyzer.analyze_request("Test request", [])
            
            assert result["action"] == "create"
            assert result["existing_issue_id"] is None
    
    @pytest.mark.asyncio
    async def test_analyze_request_ai_error_fallback(self, analyzer):
        """Test fallback behavior when AI analysis fails."""
        with patch('src.feature_analyzer.genai.GenerativeModel') as mock_model_class:
            mock_model = AsyncMock()
            mock_model.generate_content_async.side_effect = Exception("API Error")
            mock_model_class.return_value = mock_model
            
            result = await analyzer.analyze_request("Test request", [])
            
            # Should fallback to creating new issue
            assert result["action"] == "create"
            assert "AI analysis failed" in result["reasoning"]
            assert result["title"].startswith("Feature Request:")
            assert result["priority"] == 3
    
    @pytest.mark.asyncio
    async def test_analyze_request_invalid_json_fallback(self, analyzer):
        """Test fallback when AI returns invalid JSON."""
        with patch('src.feature_analyzer.genai.GenerativeModel') as mock_model_class:
            mock_model = AsyncMock()
            mock_response = AsyncMock()
            mock_response.text = "Invalid JSON response"
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            result = await analyzer.analyze_request("Test request", [])
            
            # Should fallback to creating new issue
            assert result["action"] == "create"
            assert "AI analysis failed" in result["reasoning"]
            assert result["priority"] == 3
    
    @pytest.mark.asyncio
    async def test_analyze_request_limits_existing_issues(self, analyzer):
        """Test that analysis limits existing issues to prevent token overflow."""
        # Create more than 10 issues to test limiting
        existing_issues = []
        for i in range(15):
            existing_issues.append({
                "id": f"issue-{i}",
                "title": f"Test Issue {i}",
                "description": f"Description for issue {i}" * 50  # Long description
            })
        
        mock_ai_response = {
            "action": "create",
            "reasoning": "Analysis with limited context",
            "title": "New feature",
            "description": "Test description",
            "priority": 3,
            "existing_issue_id": None
        }
        
        with patch('src.feature_analyzer.genai.GenerativeModel') as mock_model_class:
            mock_model = AsyncMock()
            mock_response = AsyncMock()
            mock_response.text = json.dumps(mock_ai_response)
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            result = await analyzer.analyze_request("Test request", existing_issues)
            
            # Should still work despite many existing issues
            assert result["action"] == "create"
            assert result["title"] == "New feature"
            
            # Verify the prompt was called with limited issues (should be truncated)
            mock_model.generate_content_async.assert_called_once()
            call_args = mock_model.generate_content_async.call_args[0][0]
            # Count how many issues are mentioned in the prompt
            issue_count = call_args.count("Test Issue")
            assert issue_count <= 10  # Should be limited to 10 issues 