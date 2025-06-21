"""Linear API client for creating and managing issues."""

import os
from typing import Dict, List, Any, Optional
import httpx


class LinearClient:
    """Client for interacting with Linear's GraphQL API."""
    
    def __init__(self, api_key: str, api_url: str = "https://api.linear.app/graphql"):
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def _make_request(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GraphQL request to Linear API."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return await response.json()
    
    async def get_open_issues(self) -> List[Dict[str, Any]]:
        """Get all open and in-progress issues for context."""
        query = """
        query GetOpenIssues {
            issues(filter: {
                state: { type: { in: ["started", "unstarted"] } }
            }) {
                nodes {
                    id
                    title
                    description
                    priority
                    state { name }
                    labels { nodes { name } }
                    createdAt
                    updatedAt
                }
            }
        }
        """
        
        result = await self._make_request(query)
        if "errors" in result:
            raise Exception(f"Linear API error: {result['errors']}")
        
        return result["data"]["issues"]["nodes"]
    
    async def create_issue(self, title: str, description: str, priority: int = 3) -> Dict[str, Any]:
        """Create a new issue in Linear."""
        # Get the first available team (simplified approach)
        teams = await self.get_teams()
        if not teams:
            raise Exception("No teams available")
        
        team_id = teams[0]["id"]
        
        query = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    title
                    url
                }
            }
        }
        """
        
        variables = {
            "input": {
                "title": title,
                "description": description,
                "priority": priority,
                "teamId": team_id
            }
        }
        
        result = await self._make_request(query, variables)
        if "errors" in result:
            raise Exception(f"Linear API error: {result['errors']}")
        
        return result["data"]["issueCreate"]
    
    async def update_issue(self, issue_id: str, title: str = None, description: str = None) -> Dict[str, Any]:
        """Update an existing issue."""
        query = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    title
                    url
                }
            }
        }
        """
        
        update_input = {}
        if title:
            update_input["title"] = title
        if description:
            update_input["description"] = description
        
        variables = {
            "id": issue_id,
            "input": update_input
        }
        
        result = await self._make_request(query, variables)
        if "errors" in result:
            raise Exception(f"Linear API error: {result['errors']}")
        
        return result["data"]["issueUpdate"]
    
    async def get_teams(self) -> List[Dict[str, Any]]:
        """Get available teams."""
        query = """
        query GetTeams {
            teams {
                nodes {
                    id
                    name
                    key
                }
            }
        }
        """
        
        result = await self._make_request(query)
        if "errors" in result:
            raise Exception(f"Linear API error: {result['errors']}")
        
        return result["data"]["teams"]["nodes"] 