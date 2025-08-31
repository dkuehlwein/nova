"""
AI memo generator module.

Generates meeting preparation memos using Nova's memory system and AI agent.
Creates plain text memos with context about attendees, projects, and talking points.
"""

from datetime import datetime
from typing import List

from utils.logging import get_logger
from tools.memory_tools import search_memory_tool
from agent.chat_agent import create_chat_agent
from ..models import CalendarMeetingInfo

logger = get_logger(__name__)


class MemoGenerator:
    """
    Generates AI-powered meeting preparation memos.
    
    Uses Nova's memory system to gather context about attendees and projects,
    then generates a concise, actionable memo for meeting preparation.
    """
    
    # Prompt template for memo generation
    MEETING_PREP_PROMPT_TEMPLATE = """Generate a concise meeting preparation memo for the following meeting:

**Meeting Details:**
- Title: {meeting_title}
- Date/Time: {meeting_time}
- Duration: {duration} minutes
- Location: {location}
- Attendees: {attendees}
- Organizer: {organizer}

**Meeting Description:**
{meeting_description}

**Context from Memory System:**
{attendee_context}

{project_context}

**Instructions:**
Create a brief, actionable meeting preparation memo that includes:
1. Key background information about attendees (based on memory context)
2. 3-4 main talking points or questions to discuss
3. Primary objectives for this meeting
4. Any follow-up items or decisions that may be needed

Keep the memo concise and practical for quick reference. Format it clearly with bullet points and sections. Focus on actionable insights that will help make the meeting productive.

If no relevant context is found in memory, focus on the meeting title and description to suggest relevant discussion topics."""

    def __init__(self):
        pass
    
    async def generate_meeting_memo(self, meeting: CalendarMeetingInfo) -> str:
        """
        Generate a comprehensive meeting preparation memo.
        
        Args:
            meeting: CalendarMeetingInfo object with meeting details
            
        Returns:
            Plain text memo for meeting preparation
        """
        try:
            logger.info(
                f"Generating memo for meeting: {meeting.title}",
                extra={"data": {
                    "meeting_id": meeting.meeting_id,
                    "title": meeting.title,
                    "attendee_count": len(meeting.attendee_emails)
                }}
            )
            
            # Gather context from memory system
            attendee_context = await self._gather_attendee_context(meeting.attendee_emails)
            project_context = await self._gather_project_context(meeting.title, meeting.description)
            
            # Format meeting details
            meeting_time = meeting.start_time.strftime("%A, %B %d at %I:%M %p")
            attendees_list = ", ".join(meeting.attendee_emails) if meeting.attendee_emails else "No attendees listed"
            location_text = meeting.location if meeting.location else "No location specified"
            description_text = meeting.description if meeting.description else "No description provided"
            organizer_text = meeting.organizer if meeting.organizer else "Unknown organizer"
            
            # Build the prompt
            memo_prompt = self.MEETING_PREP_PROMPT_TEMPLATE.format(
                meeting_title=meeting.title,
                meeting_time=meeting_time,
                duration=meeting.duration_minutes,
                location=location_text,
                attendees=attendees_list,
                organizer=organizer_text,
                meeting_description=description_text,
                attendee_context=attendee_context,
                project_context=project_context
            )
            
            # Generate memo using Nova's chat agent (no fallback - fail if LLM unavailable)
            memo_text = await self._generate_memo_with_chat_agent(memo_prompt)
            
            logger.info(
                f"Successfully generated memo for meeting {meeting.meeting_id}",
                extra={"data": {
                    "meeting_id": meeting.meeting_id,
                    "memo_length": len(memo_text)
                }}
            )
            
            return memo_text
            
        except Exception as e:
            logger.error(
                f"Failed to generate memo for meeting {meeting.meeting_id}: {str(e)}",
                exc_info=True,
                extra={"data": {
                    "meeting_id": meeting.meeting_id,
                    "error": str(e)
                }}
            )
            # Re-raise the exception - no fallback, Nova needs LLM to work
            raise
    
    async def _gather_attendee_context(self, attendee_emails: List[str]) -> str:
        """
        Gather context about meeting attendees from memory system.
        
        Args:
            attendee_emails: List of attendee email addresses
            
        Returns:
            Formatted context string about attendees
        """
        if not attendee_emails:
            return "**Attendee Context:** No attendees listed for this meeting."
        
        try:
            attendee_contexts = []
            
            for email in attendee_emails:
                # Search memory for information about this person
                query = f"person {email} background role project"
                context = await search_memory_tool(query)
                
                if context and "No relevant memories found" not in context:
                    attendee_contexts.append(f"**{email}:** {context}")
                else:
                    attendee_contexts.append(f"**{email}:** No background information available in memory.")
            
            if attendee_contexts:
                context_text = "**Attendee Context:**\n" + "\n".join(attendee_contexts)
            else:
                context_text = "**Attendee Context:** No information found about attendees in memory."
                
            return context_text
            
        except Exception as e:
            logger.error(f"Error gathering attendee context: {e}")
            return "**Attendee Context:** Error retrieving attendee information from memory."
    
    async def _gather_project_context(self, meeting_title: str, meeting_description: str) -> str:
        """
        Gather context about meeting topics/projects from memory system.
        
        Args:
            meeting_title: Title of the meeting
            meeting_description: Description of the meeting
            
        Returns:
            Formatted context string about projects/topics
        """
        try:
            # Extract key terms from title and description for memory search
            search_terms = []
            
            # Use title words (filter out common meeting words)
            title_words = meeting_title.lower().split()
            common_words = {'meeting', 'call', 'sync', 'standup', 'review', 'weekly', 'daily', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            meaningful_words = [word for word in title_words if word not in common_words and len(word) > 2]
            
            if meaningful_words:
                search_terms.extend(meaningful_words[:3])  # Use top 3 meaningful words
            
            # Add description terms if available
            if meeting_description:
                desc_words = meeting_description.lower().split()[:10]  # First 10 words
                desc_meaningful = [word for word in desc_words if word not in common_words and len(word) > 2]
                search_terms.extend(desc_meaningful[:2])  # Add top 2 from description
            
            if not search_terms:
                return "**Project Context:** No specific topics identified for memory search."
            
            # Search memory for project/topic context
            query = f"project {' '.join(search_terms[:5])}"  # Limit to 5 terms
            context = await search_memory_tool(query)
            
            if context and "No relevant memories found" not in context:
                context_text = f"**Project Context:**\n{context}"
            else:
                context_text = f"**Project Context:** No relevant project information found for topics: {', '.join(search_terms[:3])}"
                
            return context_text
            
        except Exception as e:
            logger.error(f"Error gathering project context: {e}")
            return "**Project Context:** Error retrieving project information from memory."
    
    async def _generate_memo_with_chat_agent(self, prompt: str) -> str:
        """
        Generate memo using Nova's chat agent.
        
        Args:
            prompt: Formatted prompt for memo generation
            
        Returns:
            Generated memo text (raises exception if LLM unavailable)
        """
        logger.debug("Generating memo with Nova chat agent")
        
        # Create chat agent and generate memo
        chat_agent = await create_chat_agent()
        
        messages = [{"role": "user", "content": prompt}]
        response = await chat_agent.ainvoke({"messages": messages})
        
        # Extract the content from the response
        if hasattr(response, 'get') and "messages" in response:
            last_message = response["messages"][-1]
            if hasattr(last_message, 'content'):
                return last_message.content
            else:
                return str(last_message)
        else:
            return str(response)