"""
Nova Core Agent

The proactive task processing engine that continuously monitors kanban lanes
and autonomously processes tasks using AI. Integrated with the backend.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from agent.chat_agent import create_chat_agent
from database.database import db_manager
from models.models import Task, TaskStatus, TaskComment, AgentStatus, AgentStatusEnum
from tools.task_tools import add_task_comment_tool, update_task_tool

logger = logging.getLogger(__name__)


class CoreAgent:
    """
    The Nova Core Agent - autonomous task processor.
    
    Continuously monitors kanban lanes and processes tasks using AI,
    following the user's specified logic flow.
    """
    
    def __init__(self):
        self.agent = None
        self.status_id = None
        self.is_running = False
        self.should_stop = False
        
        # Configuration
        self.check_interval = 30  # seconds
        self.timeout_minutes = 30  # timeout for stuck tasks
    
    async def initialize(self):
        """Initialize the core agent."""
        logger.info("Initializing Core Agent...")
        
        # Create the LangGraph agent (same as chat agent)
        self.agent = await create_chat_agent()
        
        # Initialize or get agent status record
        await self._initialize_status()
        
        logger.info("Core Agent initialized successfully")
    
    async def _initialize_status(self):
        """Initialize the agent status in database."""
        async with db_manager.get_session() as session:
            # Check if status record exists
            result = await session.execute(select(AgentStatus))
            status = result.scalar_one_or_none()
            
            if not status:
                # Create new status record
                status = AgentStatus(
                    status=AgentStatusEnum.IDLE,
                    started_at=datetime.utcnow()
                )
                session.add(status)
                await session.commit()
                await session.refresh(status)
            else:
                # Reset status on startup (in case of crash)
                status.status = AgentStatusEnum.IDLE
                status.current_task_id = None
                status.started_at = datetime.utcnow()
                status.last_error = None
                await session.commit()
            
            self.status_id = status.id
            logger.info(f"Agent status initialized with ID: {self.status_id}")
    
    async def run_loop(self):
        """Main agent processing loop."""
        self.is_running = True
        logger.info("Starting Core Agent processing loop...")
        
        while not self.should_stop:
            try:
                # Check if busy
                if await self._is_busy():
                    logger.debug("Agent is busy, skipping this cycle")
                    # Use shorter sleeps to be more responsive to shutdown
                    await self._interruptible_sleep(self.check_interval)
                    continue
                
                # Get next task
                task = await self._get_next_task()
                if not task:
                    logger.debug("No tasks to process")
                    # Use shorter sleeps to be more responsive to shutdown
                    await self._interruptible_sleep(self.check_interval)
                    continue
                
                # Set busy and process task
                await self._set_busy(task.id)
                
                try:
                    await self._process_task(task)
                except Exception as e:
                    logger.error(f"Error processing task {task.id} ({task.title}): {e}")
                    await self._handle_task_error(task, str(e))
                finally:
                    await self._set_idle()
                    
            except Exception as e:
                logger.error(f"Error in agent loop: {e}")
                await self._set_error(str(e))
                await self._interruptible_sleep(self.check_interval)
        
        self.is_running = False
        logger.info("Core Agent processing loop stopped")
    
    async def _interruptible_sleep(self, duration: float):
        """Sleep that can be interrupted by should_stop flag."""
        # Break sleep into 1-second chunks to be responsive to shutdown
        slept = 0
        while slept < duration and not self.should_stop:
            sleep_time = min(1.0, duration - slept)
            await asyncio.sleep(sleep_time)
            slept += sleep_time
    
    async def _is_busy(self) -> bool:
        """Check if agent is currently busy."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(AgentStatus).where(AgentStatus.id == self.status_id)
            )
            status = result.scalar_one()
            
            # Check for timeout (stuck tasks)
            if (status.status == AgentStatusEnum.PROCESSING and 
                status.last_activity and 
                datetime.utcnow() - status.last_activity > timedelta(minutes=self.timeout_minutes)):
                
                logger.warning(f"Agent stuck for {self.timeout_minutes} minutes, resetting to idle")
                await self._set_idle()
                return False
            
            return status.status != AgentStatusEnum.IDLE
    
    async def _get_next_task(self) -> Optional[Task]:
        """Get the next task to process using the specified logic."""
        async with db_manager.get_session() as session:
            # First, try USER_INPUT_RECEIVED tasks (oldest first)
            result = await session.execute(
                select(Task)
                .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
                .where(Task.status == TaskStatus.USER_INPUT_RECEIVED)
                .order_by(Task.updated_at.asc())
                .limit(1)
            )
            task = result.scalar_one_or_none()
            
            if task:
                logger.info(f"Selected USER_INPUT_RECEIVED task: {task.id} - {task.title}")
                return task
            
            # Then, try NEW tasks (oldest first)
            result = await session.execute(
                select(Task)
                .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
                .where(Task.status == TaskStatus.NEW)
                .order_by(Task.updated_at.asc())
                .limit(1)
            )
            task = result.scalar_one_or_none()
            
            if task:
                logger.info(f"Selected NEW task: {task.id} - {task.title}")
                return task
            
            return None
    
    async def _set_busy(self, task_id: UUID):
        """Set agent status to busy with current task."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(AgentStatus).where(AgentStatus.id == self.status_id)
            )
            status = result.scalar_one()
            
            status.status = AgentStatusEnum.PROCESSING
            status.current_task_id = task_id
            status.last_activity = datetime.utcnow()
            
            await session.commit()
            
        logger.info(f"Agent set to PROCESSING task {task_id}")
    
    async def _set_idle(self):
        """Set agent status to idle."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(AgentStatus).where(AgentStatus.id == self.status_id)
            )
            status = result.scalar_one()
            
            status.status = AgentStatusEnum.IDLE
            status.current_task_id = None
            status.last_activity = datetime.utcnow()
            status.total_tasks_processed += 1
            
            await session.commit()
            
        logger.info("Agent set to IDLE")
    
    async def _set_error(self, error_message: str):
        """Set agent status to error."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(AgentStatus).where(AgentStatus.id == self.status_id)
            )
            status = result.scalar_one()
            
            status.status = AgentStatusEnum.ERROR
            status.last_error = error_message
            status.error_count += 1
            status.last_activity = datetime.utcnow()
            
            await session.commit()
            
        logger.error(f"Agent set to ERROR: {error_message}")
    
    async def _process_task(self, task: Task):
        """Process a task with AI."""
        logger.info(f"Processing task {task.id}: {task.title}")
        
        # Move task to IN_PROGRESS
        await self._move_task_to_in_progress(task)
        
        # Get context (placeholder for now)
        context = await self._get_context(task)
        
        # Process with AI using LangGraph with unique thread_id for rollback capability
        thread_id = f"core_agent_task_{task.id}"
        config = RunnableConfig(configurable={"thread_id": thread_id})
        
        try:
            # Check if thread already has messages and interrupts
            state = await self.agent.aget_state(config)
            has_existing_messages = bool(state.values.get("messages", []))
            
            # Check for pending interrupts (human escalations)
            if state.interrupts:
                logger.info(f"Task {task.id} has pending interrupts - moving to NEEDS_REVIEW")
                await self._handle_human_escalation(task, state.interrupts)
                return
            
            if has_existing_messages:
                logger.info(f"Thread for task {task.id} already has messages, continuing conversation")
                # Get the current messages to extract the AI response
                messages = state.values.get("messages", [])
            else:
                logger.info(f"Starting new conversation for task {task.id}")
                # Create initial prompt only if no existing messages
                prompt = await self._create_prompt(task, context)
                
                # Stream the agent response and watch for interrupts
                messages = []
                interrupt_detected = False
                interrupt_data = None
                
                async for chunk in self.agent.astream(
                    {"messages": [{"role": "user", "content": prompt}]},
                    config=config,
                    stream_mode="values"
                ):
                    if "messages" in chunk and chunk["messages"]:
                        messages = chunk["messages"]
                    
                    # Check for interrupts during streaming but don't return immediately
                    if "__interrupt__" in chunk:
                        logger.info(f"Interrupt detected for task {task.id} during streaming")
                        interrupt_detected = True
                        interrupt_data = chunk["__interrupt__"]
                
                # Final check for interrupts after streaming
                final_state = await self.agent.aget_state(config)
                if final_state.interrupts:
                    logger.info(f"Interrupt detected for task {task.id} in final state")
                    interrupt_detected = True
                    interrupt_data = final_state.interrupts
            
            # Extract and save AI response BEFORE handling interrupts
            if messages:
                ai_response = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
                logger.info(f"AI response for task {task.id} ({task.title}): {ai_response[:200]}...")
                
                # Add AI response as comment only if it's a new conversation
                if not has_existing_messages:
                    await add_task_comment_tool(
                        task_id=str(task.id),
                        content=f"Core Agent processed this task:\n\n{ai_response}",
                        author="core_agent"
                    )
                
                # Update context (placeholder for now)
                await self._update_context(ai_response, task, context)
                
                # NOW handle interrupts after saving the response
                if interrupt_detected and interrupt_data:
                    logger.info(f"Handling interrupt for task {task.id} after saving AI response")
                    await self._handle_human_escalation(task, interrupt_data)
                    return
                
                logger.info(f"Successfully processed task {task.id} ({task.title})")
            else:
                # Handle interrupts even if no messages (edge case)
                if interrupt_detected and interrupt_data:
                    await self._handle_human_escalation(task, interrupt_data)
                    return
                raise Exception("No response from AI agent")
                
        except Exception as e:
            logger.error(f"AI processing failed for task {task.id} ({task.title}): {e}")
            raise
    
    async def _move_task_to_in_progress(self, task: Task):
        """Move task to IN_PROGRESS status."""
        await update_task_tool(
            task_id=str(task.id),
            status="in_progress"
        )
        logger.info(f"Moved task {task.id} ({task.title}) to IN_PROGRESS")
    
    async def _get_context(self, task: Task) -> Dict[str, Any]:
        """Get context for the task (placeholder implementation)."""
        # For now, return basic task context
        # TODO: Implement OpenMemory integration later
        
        context = {
            "task": {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
                "tags": task.tags
            },
            "persons": [
                {
                    "name": person.name,
                    "email": person.email,
                    "role": person.role
                }
                for person in task.persons
            ],
            "projects": [
                {
                    "name": project.name,
                    "client": project.client,
                    "summary": project.summary
                }
                for project in task.projects
            ],
            "comments": [
                {
                    "content": comment.content,
                    "author": comment.author,
                    "created_at": comment.created_at.isoformat()
                }
                for comment in task.comments
            ]
        }
        
        return context
    
    async def _create_prompt(self, task: Task, context: Dict[str, Any]) -> str:
        """Create the AI prompt for task processing."""
        from agent.prompts import CORE_AGENT_TASK_PROMPT_TEMPLATE
        
        # Build context string
        context_str = ""
        
        if context["persons"]:
            context_str += "\n**People involved:**\n"
            for person in context["persons"]:
                context_str += f"- {person['name']} ({person['email']}) - {person.get('role', 'No role specified')}\n"
        
        if context["projects"]:
            context_str += "\n**Projects:**\n"
            for project in context["projects"]:
                context_str += f"- {project['name']} for {project['client']}\n"
                if project.get('summary'):
                    context_str += f"  Summary: {project['summary']}\n"
        
        if context["comments"]:
            context_str += "\n**Previous comments:**\n"
            for comment in context["comments"]:
                context_str += f"- {comment['author']} ({comment['created_at']}): {comment['content']}\n"
        
        # Format data for the template
        assigned_people = ", ".join([p['name'] for p in context["persons"]]) if context["persons"] else "None"
        projects = ", ".join([p['name'] for p in context["projects"]]) if context["projects"] else "None"
        recent_comments = context_str if context_str else "No recent activity"
        
        # Use template to create prompt
        prompt = CORE_AGENT_TASK_PROMPT_TEMPLATE.format(
            task_id=task.id,
            title=task.title,
            description=task.description or "No description",
            status=task.status.value,
            priority="Not set",  # Priority field doesn't exist in Task model
            created_at=task.created_at.strftime('%Y-%m-%d %H:%M'),
            updated_at=task.updated_at.strftime('%Y-%m-%d %H:%M'),
            assigned_people=assigned_people,
            projects=projects,
            context=context_str if context_str else "No additional context",
            recent_comments=recent_comments
        )
        
        return prompt
    
    async def _update_context(self, ai_output: str, task: Task, context: Dict[str, Any]):
        """Update context based on AI output (placeholder implementation)."""
        # For now, do nothing
        # TODO: Implement OpenMemory updates later
        logger.debug(f"Context update placeholder for task {task.id} ({task.title})")
    
    async def _handle_human_escalation(self, task: Task, interrupts):
        """Handle human escalation interrupts."""
        try:
            # Move task to NEEDS_REVIEW status
            await update_task_tool(
                task_id=str(task.id),
                status="needs_review"
            )
            
            # Extract escalation details from interrupts
            escalation_questions = []
            for interrupt in interrupts:
                if hasattr(interrupt, 'value') and isinstance(interrupt.value, dict):
                    if interrupt.value.get("type") == "human_escalation":
                        question = interrupt.value.get("question", "Human input requested")
                        escalation_questions.append(question)
            
            # Add escalation comment
            if escalation_questions:
                escalation_text = "\n\n".join(escalation_questions)
                await add_task_comment_tool(
                    task_id=str(task.id),
                    content=f"Core Agent is requesting human input:\n\n{escalation_text}\n\n⏸️ Task paused - please respond to continue processing.",
                    author="core_agent"
                )
            else:
                await add_task_comment_tool(
                    task_id=str(task.id),
                    content="Core Agent is requesting human input. Please respond to continue processing.",
                    author="core_agent"
                )
            
            logger.info(f"Moved task {task.id} ({task.title}) to NEEDS_REVIEW due to human escalation")
            
        except Exception as e:
            logger.error(f"Failed to handle human escalation for {task.id} ({task.title}): {e}")

    async def _handle_task_error(self, task: Task, error_message: str):
        """Handle task processing errors."""
        try:
            # Move task to FAILED status
            await update_task_tool(
                task_id=str(task.id),
                status="failed"
            )
            
            # Add error comment
            await add_task_comment_tool(
                task_id=str(task.id),
                content=f"Core Agent encountered an error while processing this task:\n\n{error_message}",
                author="core_agent"
            )
            
            logger.error(f"Moved task {task.id} ({task.title}) to FAILED due to error: {error_message}")
            
        except Exception as e:
            logger.error(f"Failed to handle task error for {task.id} ({task.title}): {e}")
    
    async def get_status(self) -> AgentStatus:
        """Get current agent status."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(AgentStatus).where(AgentStatus.id == self.status_id)
            )
            return result.scalar_one()
    
    async def get_recent_task_history(self, limit: int = 10) -> List[Task]:
        """Get recently processed tasks."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task)
                .where(Task.status.in_([TaskStatus.DONE, TaskStatus.NEEDS_REVIEW, TaskStatus.FAILED]))
                .order_by(Task.updated_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def pause(self):
        """Pause the agent."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(AgentStatus).where(AgentStatus.id == self.status_id)
            )
            status = result.scalar_one()
            status.status = AgentStatusEnum.PAUSED
            await session.commit()
        
        logger.info("Agent paused")
    
    async def resume(self):
        """Resume the agent."""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(AgentStatus).where(AgentStatus.id == self.status_id)
            )
            status = result.scalar_one()
            status.status = AgentStatusEnum.IDLE
            await session.commit()
        
        logger.info("Agent resumed")
    
    async def force_process_task(self, task_id: str) -> str:
        """Force process a specific task (for testing/debugging)."""
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise ValueError(f"Invalid task ID format: {task_id}")
        
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task)
                .options(selectinload(Task.persons), selectinload(Task.projects), selectinload(Task.comments))
                .where(Task.id == task_uuid)
            )
            task = result.scalar_one_or_none()
            
            if not task:
                raise ValueError(f"Task not found: {task_id}")
        
        await self._process_task(task)
        return f"Task {task_id} processed successfully"
    
    async def shutdown(self):
        """Shutdown the agent gracefully."""
        logger.info("Shutting down Core Agent...")
        self.should_stop = True
        
        # Wait for loop to stop with timeout
        timeout = 5.0  # 5 second timeout
        start_time = asyncio.get_event_loop().time()
        while self.is_running:
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning("Core Agent shutdown timed out, forcing stop")
                break
            await asyncio.sleep(0.1)
        
        # Set agent to idle
        if self.status_id:
            try:
                await asyncio.wait_for(self._set_idle(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Setting agent to idle timed out during shutdown")
        
        logger.info("Core Agent shutdown complete") 