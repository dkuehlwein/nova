"""
Human escalation tool for Nova core agent.

Allows the agent to escalate questions to humans using LangGraph's interrupt mechanism.
The task status will be updated to NEEDS_REVIEW by the core agent when it resumes.
"""

import logging
from langchain_core.tools import tool
from langgraph.types import interrupt

logger = logging.getLogger(__name__)


@tool
def escalate_to_human(question: str) -> str:
    """
    **CRITICAL TOOL**: Ask the human a question about the current task.
    
    **WHEN TO USE THIS TOOL**:
    - Task asks you to "ask user" or "get user input" - USE THIS IMMEDIATELY
    - Task requires user decision, approval, or clarification - USE THIS
    - Task involves notifying user of important information - USE THIS
    - You need human input to proceed with the task - USE THIS
    
    This will pause the current task and wait for human response.
    The core agent will automatically move the task to NEEDS_REVIEW status
    when this tool is called, and back to USER_INPUT_RECEIVED when resumed.
    
    Args:
        question: Your question for the human. Provide sufficient context 
                 since this will be the message they see in the task chat.
                 
                 Examples:
                 - "Should I send this email draft to the client? [email content]"
                 - "I need approval to book the McKittrick Hotel for $200/night"
                 - "This task requires clarification: should I prioritize speed or accuracy?"
    
    Returns:
        The human's response from the chat interface
    """
    logger.info(f"Escalating question to human: {question}")
    
    # Use LangGraph interrupt to pause execution and wait for human input
    # The interrupt data will be handled by the core agent to update task status
    human_response = interrupt({
        "type": "human_escalation",
        "question": question,
        "instructions": "Please respond to this question to continue task processing."
    })
    
    # When resuming with Command(resume=value), the interrupt receives the value directly
    # If it's a string, use it directly; if it's a dict, extract the response
    if isinstance(human_response, str):
        response = human_response
    elif isinstance(human_response, dict):
        response = human_response.get("response", "No response received")
    else:
        response = str(human_response)
    
    logger.info(f"Received human response: {response}")
    
    return response 