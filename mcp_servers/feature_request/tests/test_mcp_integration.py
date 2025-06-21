"""Integration tests for the MCP server and request_feature tool."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.linear_client import LinearClient
from src.feature_analyzer import FeatureRequestAnalyzer
from src.mcp_tools import request_feature_impl
from main import mcp, request_feature


class TestMCPIntegration:
    """Test end-to-end MCP integration."""
    
    @pytest.fixture
    def mock_linear_issues(self):
        """Mock Linear issues data."""
        return [
            {
                "id": "issue1",
                "identifier": "NOV-1",
                "title": "Improve chat UI responsiveness",
                "description": "Current chat interface has delays",
                "state": {"name": "In Progress", "type": "started"},
                "team": {"name": "Frontend", "key": "FE"},
                "priority": 2
            }
        ]
    
    @pytest.fixture
    def mock_teams(self):
        """Mock Linear teams data."""
        return [
            {"id": "team1", "name": "Development", "key": "DEV"},
            {"id": "team2", "name": "Design", "key": "DES"}
        ]
    
    @pytest.mark.asyncio
    async def test_request_feature_tool_success_create(self):
        """Test successful feature request resulting in new issue creation."""
        # Mock analyzer response for create action
        mock_analysis = {
            "action": "create",
            "reasoning": "This is a new feature request",
            "title": "Add email integration to tasks",
            "description": "**Problem**: Cannot send emails from tasks\n\n**Requirements**: Email integration\n\n**Acceptance Criteria**: Tasks can send emails",
            "priority": 2,
            "existing_issue_id": None
        }
        
        # Mock Linear create issue response
        mock_create_result = {
            "success": True,
            "issue": {
                "id": "new-issue-123",
                "title": "Add email integration to tasks",
                "url": "https://linear.app/team/issue/ENG-123"
            }
        }
        
        with patch('src.mcp_tools.LinearClient') as mock_linear_class, \
             patch('src.mcp_tools.FeatureRequestAnalyzer') as mock_analyzer_class:
            
            # Setup mock instances
            mock_linear_client = AsyncMock()
            mock_analyzer = AsyncMock()
            mock_linear_class.return_value = mock_linear_client
            mock_analyzer_class.return_value = mock_analyzer
            
            # Configure mock responses
            mock_linear_client.get_open_issues.return_value = []
            mock_analyzer.analyze_request.return_value = mock_analysis
            mock_linear_client.create_issue.return_value = mock_create_result
            
            # Test the implementation function directly
            result = await request_feature_impl(
                "I need to send emails directly from tasks but there's no integration available",
                mock_linear_client,
                mock_analyzer
            )
            
            assert result["success"] is True
            assert result["action"] == "created"
            assert result["issue_id"] == "new-issue-123"
            assert result["title"] == "Add email integration to tasks"
            assert "linear.app" in result["issue_url"]
            assert "Created new feature request" in result["message"]
    
    @pytest.mark.asyncio
    async def test_request_feature_tool_success_update(self):
        """Test successful feature request resulting in issue update."""
        # Mock analyzer response for update action
        mock_analysis = {
            "action": "update",
            "reasoning": "This relates to existing email integration work",
            "title": "Enhanced email integration",
            "description": "**Problem**: Email integration needs improvements\n\n**Requirements**: Better email handling\n\n**Acceptance Criteria**: Reliable email operations",
            "priority": 1,
            "existing_issue_id": "existing-1"
        }
        
        # Mock Linear update issue response
        mock_update_result = {
            "success": True,
            "issue": {
                "id": "existing-1",
                "title": "Enhanced email integration",
                "url": "https://linear.app/team/issue/ENG-456"
            }
        }
        
        with patch('src.mcp_tools.LinearClient') as mock_linear_class, \
             patch('src.mcp_tools.FeatureRequestAnalyzer') as mock_analyzer_class:
            
            # Setup mock instances
            mock_linear_client = AsyncMock()
            mock_analyzer = AsyncMock()
            mock_linear_class.return_value = mock_linear_client
            mock_analyzer_class.return_value = mock_analyzer
            
            # Configure mock responses
            mock_linear_client.get_open_issues.return_value = []
            mock_analyzer.analyze_request.return_value = mock_analysis
            mock_linear_client.update_issue.return_value = mock_update_result
            
            # Test the implementation function directly
            result = await request_feature_impl(
                "The email integration is unreliable and needs improvements",
                mock_linear_client,
                mock_analyzer
            )
            
            assert result["success"] is True
            assert result["action"] == "updated"
            assert result["issue_id"] == "existing-1"
            assert result["title"] == "Enhanced email integration"
            assert "Updated existing issue" in result["message"]
    
    @pytest.mark.asyncio
    async def test_request_feature_tool_no_api_keys(self):
        """Test tool behavior when API keys are not configured."""
        result = await request_feature_impl(
            "I need a new feature",
            None,  # No linear client
            None   # No analyzer
        )
        
        assert result["success"] is False
        assert "not configured" in result["error"]
        assert "missing API keys" in result["error"]
        assert "LINEAR_API_KEY and GOOGLE_API_KEY" in result["message"]
    
    @pytest.mark.asyncio
    async def test_request_feature_tool_linear_error(self):
        """Test tool behavior when Linear API fails."""
        with patch('src.mcp_tools.LinearClient') as mock_linear_class, \
             patch('src.mcp_tools.FeatureRequestAnalyzer') as mock_analyzer_class:
            
            # Setup mock instances
            mock_linear_client = AsyncMock()
            mock_analyzer = AsyncMock()
            mock_linear_class.return_value = mock_linear_client
            mock_analyzer_class.return_value = mock_analyzer
            
            # Mock Linear API error
            mock_linear_client.get_open_issues.side_effect = Exception("Linear API authentication failed")
            
            result = await request_feature_impl(
                "Test request that will fail",
                mock_linear_client,
                mock_analyzer
            )
            
            assert result["success"] is False
            assert "Feature request failed" in result["error"]
            assert "Linear API authentication failed" in result["error"]
            assert result["request"] == "Test request that will fail"
    
    @pytest.mark.asyncio
    async def test_request_feature_tool_create_issue_failure(self):
        """Test handling when issue creation fails."""
        mock_analysis = {
            "action": "create",
            "reasoning": "New feature needed",
            "title": "Test Feature",
            "description": "Test description",
            "priority": 3,
            "existing_issue_id": None
        }
        
        # Mock failed creation
        mock_create_result = {
            "success": False,
            "error": "Team not found"
        }
        
        with patch('src.mcp_tools.LinearClient') as mock_linear_class, \
             patch('src.mcp_tools.FeatureRequestAnalyzer') as mock_analyzer_class:
            
            # Setup mock instances
            mock_linear_client = AsyncMock()
            mock_analyzer = AsyncMock()
            mock_linear_class.return_value = mock_linear_client
            mock_analyzer_class.return_value = mock_analyzer
            
            # Configure mock responses
            mock_linear_client.get_open_issues.return_value = []
            mock_analyzer.analyze_request.return_value = mock_analysis
            mock_linear_client.create_issue.return_value = mock_create_result
            
            result = await request_feature_impl(
                "Test request",
                mock_linear_client,
                mock_analyzer
            )
            
            assert result["success"] is False
            assert result["error"] == "Failed to create issue"
            assert result["details"] == mock_create_result
    
    @pytest.mark.asyncio
    async def test_request_feature_tool_update_fallback_to_create(self):
        """Test fallback to create when update has no issue ID."""
        mock_analysis = {
            "action": "update",
            "reasoning": "Related to existing work",
            "title": "Test Feature",
            "description": "Test description",
            "priority": 2,
            "existing_issue_id": None  # Missing issue ID
        }
        
        # Mock successful creation (fallback)
        mock_create_result = {
            "success": True,
            "issue": {
                "id": "fallback-issue-123",
                "title": "Test Feature",
                "url": "https://linear.app/team/issue/ENG-789"
            }
        }
        
        with patch('src.mcp_tools.LinearClient') as mock_linear_class, \
             patch('src.mcp_tools.FeatureRequestAnalyzer') as mock_analyzer_class:
            
            # Setup mock instances
            mock_linear_client = AsyncMock()
            mock_analyzer = AsyncMock()
            mock_linear_class.return_value = mock_linear_client
            mock_analyzer_class.return_value = mock_analyzer
            
            # Configure mock responses
            mock_linear_client.get_open_issues.return_value = []
            mock_analyzer.analyze_request.return_value = mock_analysis
            mock_linear_client.create_issue.return_value = mock_create_result
            
            result = await request_feature_impl(
                "Test request with fallback",
                mock_linear_client,
                mock_analyzer
            )
            
            assert result["success"] is True
            assert result["action"] == "created"  # Should fallback to create
            assert result["issue_id"] == "fallback-issue-123"
    
    @pytest.mark.asyncio
    async def test_request_feature_tool_unknown_action(self):
        """Test handling of unknown action from analyzer."""
        mock_analysis = {
            "action": "unknown_action",
            "reasoning": "Something went wrong",
            "title": "Test",
            "description": "Test",
            "priority": 3,
            "existing_issue_id": None
        }
        
        with patch('src.mcp_tools.LinearClient') as mock_linear_class, \
             patch('src.mcp_tools.FeatureRequestAnalyzer') as mock_analyzer_class:
            
            # Setup mock instances
            mock_linear_client = AsyncMock()
            mock_analyzer = AsyncMock()
            mock_linear_class.return_value = mock_linear_client
            mock_analyzer_class.return_value = mock_analyzer
            
            # Configure mock responses
            mock_linear_client.get_open_issues.return_value = []
            mock_analyzer.analyze_request.return_value = mock_analysis
            
            result = await request_feature_impl(
                "Test request",
                mock_linear_client,
                mock_analyzer
            )
            
            assert result["success"] is False
            assert "Unknown action: unknown_action" in result["error"]
            assert result["analysis"] == mock_analysis
    
    def test_tool_function_exists(self):
        """Test that the request_feature tool is properly registered."""
        # Simple check that the tool function exists
        assert hasattr(request_feature, 'fn')
        assert callable(request_feature.fn)
    
    def test_tool_description_quality(self):
        """Test that the tool has a comprehensive description."""
        # Check the tool's docstring
        description = request_feature.fn.__doc__
        
        # Check for key guidance elements
        assert "limitations" in description.lower()
        assert "problem" in description.lower()
        assert "context" in description.lower()
        assert "requirements" in description.lower()
        assert "example" in description.lower()
        
        # Should be substantial guidance (more than just a one-liner)
        assert len(description) > 200
    
    def test_mcp_server_configuration(self):
        """Test that MCP server is properly configured."""
        assert mcp.name == "FeatureRequestServer" 