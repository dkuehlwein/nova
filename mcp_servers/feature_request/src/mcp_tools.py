"""MCP tool definitions for feature request functionality."""

from typing import Dict, Any
from pydantic import Field

from .linear_client import LinearClient
from .feature_analyzer import FeatureRequestAnalyzer


async def request_feature_impl(
    request: str,
    linear_client: LinearClient,
    analyzer: FeatureRequestAnalyzer
) -> Dict[str, Any]:
    """
    Implementation of the feature request functionality.
    
    Args:
        request: Detailed description of the feature or capability needed
        linear_client: Linear API client instance
        analyzer: Feature request analyzer instance
    
    Returns:
        Dictionary with operation result details
    """
    if not linear_client or not analyzer:
        return {
            "success": False,
            "error": "Feature request system not configured - missing API keys",
            "message": "Please configure LINEAR_API_KEY and GOOGLE_API_KEY environment variables"
        }
    
    try:
        # Get existing issues for context
        existing_issues = await linear_client.get_open_issues()
        
        # Analyze the request
        analysis = await analyzer.analyze_request(request, existing_issues)
        
        if analysis["action"] == "create":
            # Create new issue
            result = await linear_client.create_issue(
                title=analysis["title"],
                description=analysis["description"],
                priority=analysis["priority"]
            )
            
            if result["success"]:
                return {
                    "success": True,
                    "action": "created",
                    "issue_id": result["issue"]["id"],
                    "issue_url": result["issue"]["url"],
                    "title": result["issue"]["title"],
                    "reasoning": analysis["reasoning"],
                    "message": f"Created new feature request: {result['issue']['title']}"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create issue",
                    "details": result
                }
        
        elif analysis["action"] == "update":
            # Update existing issue
            issue_id = analysis["existing_issue_id"]
            if not issue_id:
                # Fallback to creating new issue if no ID provided
                result = await linear_client.create_issue(
                    title=analysis["title"],
                    description=analysis["description"],
                    priority=analysis["priority"]
                )
                
                if result["success"]:
                    return {
                        "success": True,
                        "action": "created",  # Report correct action for fallback
                        "issue_id": result["issue"]["id"],
                        "issue_url": result["issue"]["url"],
                        "title": result["issue"]["title"],
                        "reasoning": analysis["reasoning"],
                        "message": f"Created new feature request: {result['issue']['title']}"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to create issue",
                        "details": result
                    }
            else:
                result = await linear_client.update_issue(
                    issue_id=issue_id,
                    description=analysis["description"]
                )
                
                if result["success"]:
                    return {
                        "success": True,
                        "action": "updated",
                        "issue_id": result["issue"]["id"],
                        "issue_url": result["issue"]["url"],
                        "title": result["issue"]["title"],
                        "reasoning": analysis["reasoning"],
                        "message": f"Updated existing issue: {result['issue']['title']}"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to update issue",
                        "details": result
                    }
        
        else:
            return {
                "success": False,
                "error": f"Unknown action: {analysis['action']}",
                "analysis": analysis
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Feature request failed: {str(e)}",
            "request": request
        }


def create_request_feature_tool(mcp, linear_client: LinearClient, analyzer: FeatureRequestAnalyzer):
    """Create and register the request_feature tool with the MCP server."""
    
    @mcp.tool()
    async def request_feature(
        request: str = Field(..., description="Detailed description of the feature or capability you need")
    ) -> Dict[str, Any]:
        """
        Use this tool when you encounter limitations or need new capabilities that prevent you from helping users effectively.
        
        This tool helps you create well-structured feature requests in Linear when you're stuck or need improvements.
        
        When to use this:
        - You can't complete a user's request due to missing functionality
        - You discover bugs or limitations in existing tools
        - You need new integrations or capabilities
        - Current workflows are inefficient and could be improved
        
        How to write a good feature request:
        - Describe the PROBLEM: What limitation are you facing? What can't you do?
        - Explain the CONTEXT: What were you trying to accomplish for the user?
        - Specify REQUIREMENTS: What exactly do you need to solve this?
        - Include IMPACT: How would this help you serve users better?
        
        Example: "I cannot create calendar events with multiple attendees because the current tool only accepts a single attendee. I was trying to help a user schedule a team meeting but had to ask them to add attendees manually. I need the create_calendar_event tool to accept a list of email addresses for attendees so I can fully automate meeting creation."
        """
        return await request_feature_impl(request, linear_client, analyzer)
    
    return request_feature 