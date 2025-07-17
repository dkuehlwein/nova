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
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from agent.chat_agent import create_chat_agent
from database.database import db_manager
from models.models import Task, TaskStatus, TaskComment, AgentStatus, AgentStatusEnum
from tools.task_tools import update_task_tool

logger = logging.getLogger(__name__)


class CoreAgent:
    """
    The Nova Core Agent - autonomous task processor.
    
    Continuously monitors kanban lanes and processes tasks using AI,
    following the user's specified logic flow.
    """
    
    def __init__(self, pg_pool):
        self.agent = None
        self.status_id = None
        self.is_running = False
        self.should_stop = False
        self.pg_pool = pg_pool  # Required PostgreSQL pool from ServiceManager
        
        # Configuration
        self.check_interval = 30  # seconds
        self.timeout_minutes = 30  # timeout for stuck tasks
    
    async def initialize(self):
        """Initialize the core agent."""
        logger.info("Initializing Core Agent...")
        
        # Create the LangGraph agent using the PostgreSQL pool
        self.agent = await create_chat_agent(pg_pool=self.pg_pool, include_escalation=True)
        logger.info("Core Agent using PostgreSQL pool from ServiceManager")
        
        # Initialize or get agent status record
        await self._initialize_status()
        
        logger.info("Core Agent initialized successfully")
    
    async def reload_agent(self):
        """Reload the agent with updated prompt."""
        logger.info("Reloading Core Agent with updated prompt...")
        
        try:
            # Recreate the agent with new prompt and tools using the PostgreSQL pool
            self.agent = await create_chat_agent(pg_pool=self.pg_pool, use_cache=False, include_escalation=True)
            logger.info("Core Agent reloaded with PostgreSQL pool")
            
            logger.info("Core Agent reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload Core Agent: {e}")
            # Keep the old agent if reload fails
            raise
    
    async def _initialize_status(self):
        """Initialize the agent status in database."""
        async with db_manager.get_session() as session:
            # Clean up any existing agent status records (there should only be one)
            await session.execute(delete(AgentStatus))
            
            # Create new status record
            status = AgentStatus(
                status=AgentStatusEnum.IDLE,
                started_at=datetime.utcnow()
            )
            session.add(status)
            await session.commit()
            await session.refresh(status)
            
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
                .options(selectinload(Task.comments))
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
                .options(selectinload(Task.comments))
                .where(Task.status == TaskStatus.NEW)
                .order_by(Task.updated_at.asc())
                .limit(1)
            )
            task = result.scalar_one_or_none()
            
            if task:
                logger.info(f"Selected NEW task: {task.id} - {task.title}")
                return task
            
            logger.info("No tasks available for processing")
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
        logger.info(f"Processing task {task.id}: {task.title} (current status: {task.status.value})")
        
        # If task is already completed, don't process it again
        if task.status in [TaskStatus.DONE, TaskStatus.FAILED]:
            logger.warning(f"UNEXPECTED: Attempting to process already completed task {task.id} ({task.title}) "
                          f"with status {task.status.value}.")
            return
        
        # Move task to IN_PROGRESS
        await self._move_task_to_in_progress(task)
        
        # Get context
        context = await self._get_context(task)
        
        # Process with AI using LangGraph with unique thread_id for rollback capability
        thread_id = f"core_agent_task_{task.id}"
        config = RunnableConfig(configurable={"thread_id": thread_id})
        
        try:
            # Check if thread already has messages (i.e., this is a resumed conversation)
            state = await self.agent.aget_state(config)
            has_existing_messages = bool(state.values.get("messages", []))
            existing_message_count = len(state.values.get("messages", []))
            
            # Initialize interrupt tracking variables and messages
            interrupt_detected = False
            interrupt_data = None
            messages = []
            
            if has_existing_messages:
                logger.info(f"Resuming conversation for task {task.id} with {existing_message_count} messages")
                # Get the current messages to extract the AI response
                messages = state.values.get("messages", [])
            else:
                logger.info(f"Starting new conversation for task {task.id}")
                
                # Create separate messages for proper conversation structure
                task_messages = await self._create_task_messages(task, context)
                
                # Stream the agent response
                messages = []
                
                async for chunk in self.agent.astream(
                    {"messages": task_messages},
                    config=config,
                    stream_mode="updates"
                ):
                    # Handle the different structure of updates mode
                    for node_name, node_output in chunk.items():
                        # Handle message nodes
                        if isinstance(node_output, dict) and "messages" in node_output and node_output["messages"]:
                            # Accumulate all messages from the stream
                            messages.extend(node_output["messages"])
                        # Handle interrupt nodes (interrupt data is stored directly in chunk)
                        if node_name == "__interrupt__":
                            interrupt_detected = True
                            interrupt_data = node_output  # This is the interrupt tuple
               
            
            # Handle interrupts first (regardless of messages)
            if interrupt_detected and interrupt_data:
                logger.info(f"Handling user question for task {task.id}")
                await self._handle_user_question(task, interrupt_data)
                return
            
            # Extract and save AI response if we have messages
            if messages:
                ai_response = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
                logger.info(f"AI response for task {task.id} ({task.title}): {ai_response[:200]}...")
            else:
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
        logger.debug(f"Moved task {task.id} ({task.title}) to IN_PROGRESS")
    
    async def _get_context(self, task: Task) -> Dict[str, Any]:
        """Get context for the task using memory search."""
        from memory.memory_functions import search_memory, MemorySearchError
        
        # Build search query from task information
        search_parts = [task.title]
        if task.description:
            search_parts.append(task.description)
        
        # Add recent comments to search context
        if task.comments:
            recent_comments = [comment.content for comment in task.comments[-3:]]  # Last 3 comments
            search_parts.extend(recent_comments)
        
        search_query = " ".join(search_parts)
        
        # Search memory for relevant context
        memory_context = []
        try:
            memory_result = await search_memory(search_query)
            if memory_result["success"] and memory_result["results"]:
                memory_context = [result["fact"] for result in memory_result["results"]]
                logger.debug(f"Found {len(memory_context)} memory facts for task {task.id}")
            else:
                logger.debug(f"No memory context found for task {task.id}")
        except MemorySearchError as e:
            logger.warning(f"Memory search failed for task {task.id}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error during memory search for task {task.id}: {e}")
        
        context = {
            "task": {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
                "tags": task.tags
            },
            "memory_context": memory_context,
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
    
    async def _create_task_messages(self, task: Task, context: Dict[str, Any]) -> List:
        """Create separate messages for task processing conversation structure."""
        from agent.prompts import TASK_CONTEXT_TEMPLATE, CURRENT_TASK_TEMPLATE
        from langchain_core.messages import HumanMessage, AIMessage
        
        # Format memory context (only for Memory Context section)
        memory_context_str = ""
        if context["memory_context"]:
            memory_context_str = "\n".join([f"- {fact}" for fact in context["memory_context"]])
        else:
            memory_context_str = "No relevant memory found"
        
        # Format recent comments (actual task comments only)
        recent_comments_str = ""
        if context["comments"]:
            recent_comments_str = "\n".join([
                f"- {comment['author']} ({comment['created_at']}): {comment['content']}" 
                for comment in context["comments"]
            ])
        else:
            recent_comments_str = "No recent comments"
        
        # Create task context using template (clean content without header - metadata provides title)
        task_context_content = TASK_CONTEXT_TEMPLATE.format(
            task_id=str(task.id),
            status=task.status.value,
            priority="Not set",  # Priority field doesn't exist in Task model
            created_at=task.created_at.strftime('%Y-%m-%d %H:%M'),
            updated_at=task.updated_at.strftime('%Y-%m-%d %H:%M'),
            memory_context=memory_context_str,
            recent_comments=recent_comments_str
        )
        
        # Create the current task section
        current_task = CURRENT_TASK_TEMPLATE.format(
            title=task.title,
            description=task.description or "No description"
        )
        
        # Return separate messages with proper metadata for task context
        return [
            HumanMessage(content=current_task),
            AIMessage(
                content=task_context_content,
                additional_kwargs={
                    "metadata": {
                        "type": "task_context",
                        "is_collapsible": True,
                        "title": "Task Context"
                    }
                }
            )
        ]
    
    
    async def _handle_user_question(self, task: Task, interrupts):
        """Handle user question interrupts."""
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
                    if interrupt.value.get("type") == "user_question":
                        question = interrupt.value.get("question", "Human input requested")
                        escalation_questions.append(question)
            
            # Add escalation comment
            if escalation_questions:
                escalation_text = "\n\n".join(escalation_questions)
                await update_task_tool(
                    task_id=str(task.id),
                    comment=f"Core Agent is requesting human input:\n\n{escalation_text}\n\n⏸️ Task paused - please respond to continue processing."
                )
            else:
                await update_task_tool(
                    task_id=str(task.id),
                    comment="Core Agent is requesting human input. Please respond to continue processing."
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
            await update_task_tool(
                task_id=str(task.id),
                comment=f"Core Agent encountered an error while processing this task:\n\n{error_message}"
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
                .options(selectinload(Task.comments))
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
        
        # Clear chat agent cache to prevent event loop issues with Google AI client
        from agent.chat_agent import clear_chat_agent_cache
        clear_chat_agent_cache()
        logger.info("Cleared chat agent cache during shutdown")
        
        logger.info("Core Agent shutdown complete") 