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
            "message": "Please configure LINEAR_API_KEY and ensure FEATURE_REQUEST_LITELLM_KEY is set with a valid virtual key"
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
                try:
                    # Get existing issue details to check current priority
                    existing_issue = await linear_client.get_issue(issue_id)
                    current_priority = existing_issue.get("priority", 4)
                    
                    # Add comment with the new request/clarification
                    comment_body = analysis.get("comment", f"**Additional Request:**\n\n{request}")
                    comment_result = await linear_client.add_comment(issue_id, comment_body)
                    
                    # Update priority if needed
                    new_priority = None
                    if analysis.get("should_increase_priority", False) and analysis["priority"] < current_priority:
                        new_priority = analysis["priority"]
                    
                    # Update issue with priority if needed (don't change description)
                    update_result = None
                    if new_priority is not None:
                        update_result = await linear_client.update_issue(
                            issue_id=issue_id,
                            priority=new_priority
                        )
                    
                    # Construct response message
                    actions_taken = ["added comment"]
                    if new_priority is not None:
                        actions_taken.append(f"increased priority to {new_priority}")
                    
                    if comment_result["success"]:
                        return {
                            "success": True,
                            "action": "updated",
                            "issue_id": issue_id,
                            "issue_url": existing_issue["url"],
                            "title": existing_issue["title"],
                            "reasoning": analysis["reasoning"],
                            "actions_taken": actions_taken,
                            "message": f"Updated existing issue '{existing_issue['title']}': {', '.join(actions_taken)}"
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Failed to add comment to issue",
                            "details": comment_result
                        }
                except Exception as update_error:
                    # If update fails (e.g., issue doesn't exist), fallback to creating new issue
                    if "Entity not found" in str(update_error) or "not found" in str(update_error).lower():
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
                                "reasoning": f"{analysis['reasoning']} (Original issue not found, created new one)",
                                "message": f"Created new feature request (original issue not found): {result['issue']['title']}"
                            }
                        else:
                            return {
                                "success": False,
                                "error": "Issue update failed and fallback creation also failed",
                                "update_error": str(update_error),
                                "create_error": result
                            }
                    else:
                        # Re-raise if it's not a "not found" error
                        raise update_error
        
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