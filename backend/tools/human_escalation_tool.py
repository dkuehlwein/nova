"""
Human escalation tool for Nova core agent.

Allows the agent to escalate questions to humans using LangGraph's interrupt mechanism.
The task status will be updated to NEEDS_REVIEW by the core agent when it resumes.
"""

from langchain_core.tools import tool
from langgraph.types import interrupt

from utils.logging import get_logger

logger = get_logger(__name__)


@tool
def ask_user(question: str) -> str:
    """
    Ask the user a question when you need input, decisions, or clarification.
    
    **WHEN TO USE THIS TOOL**:
    - Task contains "ask user" or "get user input" - use this tool
    - Task requires user decision, approval, or clarification
    - Task involves notifying user of important information
    - You need user input to proceed with the task
    
    This will pause the current task and wait for user response.
    The core agent will automatically move the task to NEEDS_REVIEW status
    when this tool is called, and back to USER_INPUT_RECEIVED when resumed.
    
    Args:
        question: Your question for the user. Provide sufficient context 
                 since this will be the message they see in the task chat.
                 
                 Examples:
                 - "Should I send this email draft to the client? [email content]"
                 - "I need approval to book the McKittrick Hotel for $200/night"
                 - "This task requires clarification: should I prioritize speed or accuracy?"
    
    Returns:
        The user's response from the chat interface
    """
    logger.info("Asking user question", extra={"data": {"question": question}})
    
    # Use LangGraph interrupt to pause execution and wait for user input
    # The interrupt data will be handled by the core agent to update task status
    user_response = interrupt({
        "type": "user_question",
        "question": question,
        "instructions": "Please respond to this question to continue task processing."
    })
    
    # When resuming with Command(resume=value), the interrupt receives the value directly
    # If it's a string, use it directly; if it's a dict, extract the response
    if isinstance(user_response, str):
        response = user_response
    elif isinstance(user_response, dict):
        response = user_response.get("response", "No response received")
    else:
        response = str(user_response)
    
    logger.info("Received user response", extra={"data": {"response": response}})
    
    return response 