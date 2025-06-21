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

    @pytest.fixture
    def mock_existing_issues(self):
        """Mock existing issues with web/URL functionality."""
        return [
            {
                'id': 'existing-123',
                'title': 'Add URL fetching and summarization capabilities',
                'description': 'Agent needs ability to fetch and summarize web content from URLs in tasks and emails. This would enable processing of linked articles and documents.',
                'priority': 2,
                'state': {'name': 'In Progress'}
            },
            {
                'id': 'different-456', 
                'title': 'Improve database performance',
                'description': 'Database queries are slow and need optimization.',
                'priority': 1,
                'state': {'name': 'Todo'}
            }
        ]
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv('GOOGLE_API_KEY'), reason="GOOGLE_API_KEY not set")
    async def test_duplicate_detection_and_merging(self, analyzer, mock_existing_issues):
        """Test that similar requests are correctly identified for updating existing issues."""
        
        # Test request that should be merged with existing URL/web functionality issue
        similar_request = "I need the agent to process information from external links in emails and summarize web content"
        
        result = await analyzer.analyze_request(similar_request, mock_existing_issues)
        
        # Should decide to update existing issue
        assert result["action"] == "update", f"Expected 'update' but got '{result['action']}'. Reasoning: {result['reasoning']}"
        assert result["existing_issue_id"] == "existing-123", f"Expected 'existing-123' but got '{result['existing_issue_id']}'"
        assert "existing" in result["reasoning"].lower() or "duplicate" in result["reasoning"].lower()
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv('GOOGLE_API_KEY'), reason="GOOGLE_API_KEY not set")
    async def test_new_feature_creation(self, analyzer, mock_existing_issues):
        """Test that genuinely new requests create new issues."""
        
        # Test request that's different from existing issues
        new_request = "I need the agent to control IoT devices and smart home automation"
        
        result = await analyzer.analyze_request(new_request, mock_existing_issues)
        
        # Should decide to create new issue
        assert result["action"] == "create", f"Expected 'create' but got '{result['action']}'. Reasoning: {result['reasoning']}"
        assert result["existing_issue_id"] is None
        assert "new" in result["reasoning"].lower() or "different" in result["reasoning"].lower()
    
    @pytest.mark.asyncio
    async def test_ai_failure_fallback(self, analyzer):
        """Test fallback behavior when AI analysis fails."""
        
        # Mock AI failure
        with patch.object(analyzer, 'model') as mock_model:
            mock_model.generate_content_async.side_effect = Exception("API rate limit")
            
            result = await analyzer.analyze_request("test request", [])
            
            # Should fallback to creating new issue
            assert result["action"] == "create"
            assert "AI analysis failed" in result["reasoning"]
            assert result["existing_issue_id"] is None
            assert "Feature Request:" in result["title"]
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv('GOOGLE_API_KEY'), reason="GOOGLE_API_KEY not set") 
    async def test_multiple_similar_requests_consistency(self, analyzer, mock_existing_issues):
        """Test that multiple similar requests consistently identify the same existing issue."""
        
        similar_requests = [
            "The agent cannot access web content from URLs shared in tasks",
            "I need URL summarization functionality for the agent", 
            "Agent should be able to fetch and process web page content"
        ]
        
        results = []
        for request in similar_requests:
            result = await analyzer.analyze_request(request, mock_existing_issues)
            results.append(result)
        
        # All should decide to update the same existing issue
        for i, result in enumerate(results):
            assert result["action"] == "update", f"Request {i+1} should update existing issue"
            assert result["existing_issue_id"] == "existing-123", f"Request {i+1} should reference existing-123"
    
    @pytest.mark.asyncio
    async def test_empty_existing_issues(self, analyzer):
        """Test behavior with no existing issues."""
        
        result = await analyzer.analyze_request("Need web scraping capability", [])
        
        # Should create new issue when no existing issues
        assert result["action"] == "create"
        assert result["existing_issue_id"] is None
        assert "title" in result
        assert "description" in result
        assert "priority" in result 