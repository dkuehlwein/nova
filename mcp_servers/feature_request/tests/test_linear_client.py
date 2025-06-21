"""Tests for LinearClient functionality."""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.linear_client import LinearClient


class TestLinearClient:
    """Test Linear API client functionality."""
    
    @pytest.fixture
    def linear_client(self):
        """Create a LinearClient instance for testing."""
        return LinearClient("test-api-key", "https://api.linear.app/graphql")
    
    @pytest.mark.asyncio
    async def test_get_open_issues_success(self, linear_client):
        """Test successful retrieval of open issues."""
        mock_response = {
            "data": {
                "issues": {
                    "nodes": [
                        {
                            "id": "issue-1",
                            "title": "Test Issue 1",
                            "description": "Test description",
                            "priority": 2,
                            "state": {"name": "In Progress"},
                            "labels": {"nodes": [{"name": "bug"}]},
                            "createdAt": "2025-01-01T10:00:00Z",
                            "updatedAt": "2025-01-01T11:00:00Z"
                        },
                        {
                            "id": "issue-2", 
                            "title": "Test Issue 2",
                            "description": "Another test",
                            "priority": 3,
                            "state": {"name": "To Do"},
                            "labels": {"nodes": []},
                            "createdAt": "2025-01-01T09:00:00Z",
                            "updatedAt": "2025-01-01T09:30:00Z"
                        }
                    ]
                }
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = lambda: None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response_obj
            
            issues = await linear_client.get_open_issues()
            
            assert len(issues) == 2
            assert issues[0]["id"] == "issue-1"
            assert issues[0]["title"] == "Test Issue 1"
            assert issues[1]["id"] == "issue-2"
            assert issues[1]["title"] == "Test Issue 2"
    
    @pytest.mark.asyncio
    async def test_get_open_issues_error(self, linear_client):
        """Test error handling when fetching open issues."""
        mock_response = {
            "errors": [{"message": "Authentication failed"}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = lambda: None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response_obj
            
            with pytest.raises(Exception, match="Linear API error"):
                await linear_client.get_open_issues()
    
    @pytest.mark.asyncio
    async def test_create_issue_success(self, linear_client):
        """Test successful issue creation."""
        # Mock get_teams response first
        teams_response = {
            "data": {
                "teams": {
                    "nodes": [
                        {"id": "team-1", "name": "Engineering", "key": "ENG"}
                    ]
                }
            }
        }
        
        # Mock create issue response
        create_response = {
            "data": {
                "issueCreate": {
                    "success": True,
                    "issue": {
                        "id": "new-issue-id",
                        "title": "New Feature Request",
                        "url": "https://linear.app/team/issue/ENG-123"
                    }
                }
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response_obj = AsyncMock()
            # First call returns teams, second call returns create result
            mock_response_obj.json = AsyncMock(side_effect=[teams_response, create_response])
            mock_response_obj.raise_for_status = lambda: None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response_obj
            
            result = await linear_client.create_issue(
                title="New Feature Request",
                description="This is a test feature request",
                priority=2
            )
            
            assert result["success"] is True
            assert result["issue"]["id"] == "new-issue-id"
            assert result["issue"]["title"] == "New Feature Request"
            assert "linear.app" in result["issue"]["url"]
    
    @pytest.mark.asyncio
    async def test_create_issue_no_teams(self, linear_client):
        """Test issue creation when no teams are available."""
        teams_response = {
            "data": {
                "teams": {
                    "nodes": []
                }
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=teams_response)
            mock_response_obj.raise_for_status = lambda: None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response_obj
            
            with pytest.raises(Exception, match="No teams available"):
                await linear_client.create_issue(
                    title="Test Issue",
                    description="Test description"
                )
    
    @pytest.mark.asyncio
    async def test_update_issue_success(self, linear_client):
        """Test successful issue update."""
        mock_response = {
            "data": {
                "issueUpdate": {
                    "success": True,
                    "issue": {
                        "id": "issue-123",
                        "title": "Updated Issue Title",
                        "url": "https://linear.app/team/issue/ENG-123"
                    }
                }
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = lambda: None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response_obj
            
            result = await linear_client.update_issue(
                issue_id="issue-123",
                title="Updated Issue Title",
                description="Updated description"
            )
            
            assert result["success"] is True
            assert result["issue"]["id"] == "issue-123"
            assert result["issue"]["title"] == "Updated Issue Title"
    
    @pytest.mark.asyncio
    async def test_get_teams_success(self, linear_client):
        """Test successful teams retrieval."""
        mock_response = {
            "data": {
                "teams": {
                    "nodes": [
                        {"id": "team-1", "name": "Engineering", "key": "ENG"},
                        {"id": "team-2", "name": "Design", "key": "DES"}
                    ]
                }
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = lambda: None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response_obj
            
            teams = await linear_client.get_teams()
            
            assert len(teams) == 2
            assert teams[0]["name"] == "Engineering"
            assert teams[1]["name"] == "Design"
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self, linear_client):
        """Test HTTP error handling."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock the HTTP error to be raised during the request
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.HTTPStatusError(
                "API Error", request=AsyncMock(), response=AsyncMock()
            )
            
            with pytest.raises(httpx.HTTPStatusError):
                await linear_client.get_open_issues() 