"""AI-powered feature request analysis using LiteLLM gateway."""

import json
from typing import Dict, List, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from .llm_factory import create_feature_analyzer_llm


class FeatureRequestAnalyzer:
    """AI analyzer for feature requests using LiteLLM gateway."""
    
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        self.llm = None  # Lazy initialization for better testability
        self.system_prompt = self._create_system_prompt()
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for feature request analysis."""
        return """You are an AI assistant that analyzes feature requests for a software project management system.

Your task is to analyze feature requests and decide whether to create a new Linear issue or update an existing one.

**Analysis Guidelines:**
- Create new issue if the request is genuinely new or significantly different
- Update existing if it's clearly related to an open issue (use the exact "id" field from the existing issues)
- Write clear, actionable descriptions
- Set appropriate priority based on impact and urgency
- IMPORTANT: When updating, you MUST provide the exact "id" from the existing issues list, not a made-up ID
- For updates: Write a comment that adds ONLY new information - do NOT repeat what's already in the existing description
- Comments should be concise and focus on: new requirements, clarifications, edge cases, or additional context not already covered
- For updates: Only suggest priority increase if the new request genuinely indicates higher urgency than the existing issue

**Response Format:**
You must respond with a JSON object containing exactly these fields:
1. "action": either "create" or "update"
2. "reasoning": brief explanation of your decision
3. "title": suggested issue title (max 100 chars)
4. "description": detailed issue description including problem statement, requirements, and acceptance criteria
5. "priority": number 1-4 (1=urgent, 2=high, 3=normal, 4=low)
6. "existing_issue_id": if action is "update", provide the EXACT ID from the existing issues list (otherwise null)
7. "comment": if action is "update", provide a concise comment that adds ONLY new information not already in the existing issue (new requirements, clarifications, edge cases)
8. "should_increase_priority": if action is "update", boolean indicating if the new request suggests higher urgency than the existing issue

Respond only with valid JSON, no additional text."""
    
    async def analyze_request(self, request: str, existing_issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a feature request and decide whether to create new or update existing issue."""
        
        # Prepare context about existing issues
        issues_context = ""
        if existing_issues:
            issues_context = "Existing issues:\n"
            for issue in existing_issues[:20]:  # Limit to prevent token overflow
                issues_context += f"ID: {issue['id']}\nTitle: {issue['title']}\nDescription: {issue.get('description', '')[:200]}...\n\n"
        else:
            issues_context = "No existing issues found."
        
        user_prompt = f"""Feature Request:
{request}

{issues_context}

Please analyze this feature request and provide your response as JSON."""
        
        try:
            # Lazy initialization of LLM for better testability
            if self.llm is None:
                self.llm = create_feature_analyzer_llm(
                    model=self.model_name,
                    temperature=0.1,  # Low temperature for consistent analysis
                    max_tokens=2048
                )
            
            # Create messages for LangChain
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Generate response using LangChain
            response = await self.llm.ainvoke(messages)
            
            # Parse the JSON response
            response_text = response.content.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()
            
            return json.loads(response_text)
            
        except Exception as e:
            # Fallback to creating new issue if AI analysis fails
            return {
                "action": "create",
                "reasoning": f"AI analysis failed ({str(e)}), defaulting to new issue",
                "title": f"Feature Request: {request[:80]}",
                "description": f"**Problem**: {request}\n\n**Requirements**: To be defined\n\n**Acceptance Criteria**: To be defined",
                "priority": 3,
                "existing_issue_id": None,
                "comment": None,
                "should_increase_priority": False
            } 