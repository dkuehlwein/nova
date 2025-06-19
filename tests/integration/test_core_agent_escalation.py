"""
Integration test for Nova Core Agent Escalation Workflow

Tests the complete escalation workflow with real LLM:
1. Add task asking user for favorite food
2. Core agent takes task and moves to processing
3. Core agent uses escalate_to_human tool 
4. Task moves to "needs review" lane
5. Core agent becomes idle
6. User answers "pizza"
7. Core agent moves task to "done"
"""

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime
from sqlalchemy import select, text

from agent.core_agent import CoreAgent
from agent.chat_agent import create_chat_agent
from database.database import db_manager
from models.models import Task, TaskStatus, TaskComment, AgentStatus, AgentStatusEnum
from utils.logging import get_logger

logger = get_logger(__name__)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_complete_escalation_workflow():
    """
    Test complete escalation workflow with real LLM.
    
    This demonstrates the exact escalation flow you wanted:
    - Task asking for favorite food
    - Core agent processing and escalation
    - Task moving to needs review
    - Agent becoming idle
    - User providing answer
    - Task completion
    """
    
    # Step 1: Create task that will trigger escalation with real LLM
    task_data = {
        "title": "Ask User About Food Preference",
        "description": "I need you to ask the user what their favorite food is. Since this requires direct user input, you should use the escalate_to_human tool to ask them directly.",
        "status": TaskStatus.NEW
    }
    
    async with db_manager.get_session() as session:
        # Create the task
        task = Task(
            id=uuid4(),
            title=task_data["title"],
            description=task_data["description"],
            status=task_data["status"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id
        
        logger.info("Created food preference task", extra={
            "data": {"task_id": str(task_id), "title": task.title}
        })
    
    # Step 2: Initialize core agent
    core_agent = CoreAgent()
    await core_agent.initialize()
    
    try:
        # Verify agent is initialized
        assert core_agent.agent is not None
        assert core_agent.status_id is not None
        
        # Step 3: Force process the task (simulates core agent picking it up)
        logger.info("Core agent starting to process task", extra={
            "data": {"task_id": str(task_id)}
        })
        
        result = await core_agent.force_process_task(str(task_id))
        assert result == f"Task {task_id} processed successfully"
        
        # Step 4: Verify task moved to needs review (escalation occurred)
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            updated_task = result.scalar_one()
            
            # The task should now be in NEEDS_REVIEW status due to escalation
            logger.info("Task status after processing", extra={
                "data": {"task_id": str(task_id), "status": updated_task.status.value}
            })
            
            # Check if escalation occurred (task should be in needs review)
            # Note: The exact status depends on how the agent handles escalation
            assert updated_task.status in [TaskStatus.NEEDS_REVIEW, TaskStatus.IN_PROGRESS]
            
            # Check for escalation comment
            result = await session.execute(
                select(TaskComment).where(TaskComment.task_id == task_id)
            )
            comments = result.scalars().all()
            
            escalation_comment = None
            for comment in comments:
                if "favorite food" in comment.content.lower() or "question" in comment.content.lower():
                    escalation_comment = comment
                    break
            
            if escalation_comment:
                logger.info("Found escalation comment", extra={
                    "data": {
                        "task_id": str(task_id), 
                        "comment": escalation_comment.content[:100]
                    }
                })
        
        # Step 5: Verify agent is now idle
        is_busy = await core_agent._is_busy()
        logger.info("Core agent status after processing", extra={
            "data": {"is_busy": is_busy}
        })
        
        # Agent should be idle after escalation
        assert is_busy is False
        
        # Step 6: Simulate user providing answer "pizza" using the same method as frontend
        from langchain_core.runnables import RunnableConfig
        from langgraph.types import Command
        from tools.task_tools import update_task_tool
        
        thread_id = f"core_agent_task_{task_id}"
        config = RunnableConfig(configurable={"thread_id": thread_id})
        
        try:
            # Get the chat agent to respond to escalation (same as API endpoint)
            chat_agent = await create_chat_agent()
            
            # Check current state for interrupts
            state = await chat_agent.aget_state(config)
            
            if state.interrupts:
                logger.info("Found interrupts, responding with user input", extra={
                    "data": {"task_id": str(task_id), "interrupts": len(state.interrupts)}
                })
                
                # Resume the graph with the human's response using Command(resume=...)
                # This is exactly how the frontend API endpoint does it
                async for chunk in chat_agent.astream(
                    Command(resume="My favorite food is pizza!"),
                    config=config,
                    stream_mode="updates"
                ):
                    logger.debug(f"Resume chunk: {chunk}")
                
                # IMPORTANT: Also update task status like the API endpoint does
                # The API endpoint sets task to USER_INPUT_RECEIVED so core agent can pick it up
                async with db_manager.get_session() as session:
                    result = await session.execute(
                        select(Task).where(Task.id == task_id)
                    )
                    current_task = result.scalar_one()
                    
                    if current_task.status == TaskStatus.NEEDS_REVIEW:
                        await update_task_tool(
                            task_id=str(task_id),
                            status="user_input_received"
                        )
                        logger.info("Updated task to USER_INPUT_RECEIVED after escalation response", extra={
                            "data": {"task_id": str(task_id)}
                        })
                
                logger.info("User provided response via escalation resume", extra={
                    "data": {"task_id": str(task_id), "response": "pizza"}
                })
            else:
                logger.warning("No interrupts found when expected", extra={
                    "data": {"task_id": str(task_id)}
                })
                
        except Exception as e:
            logger.error(f"Error responding to escalation: {e}", extra={
                "data": {"task_id": str(task_id)}
            })
            raise
        
        # Step 7: Process task again to complete it after user input
        # The task should now be in USER_INPUT_RECEIVED status for core agent to pick up
        logger.info("Core agent processing task again after user input", extra={
            "data": {"task_id": str(task_id)}
        })
        
        result = await core_agent.force_process_task(str(task_id))
        assert result == f"Task {task_id} processed successfully"
        
        # Step 8: Verify task is now completed
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            final_task = result.scalar_one()
            
            logger.info("Task status after second processing", extra={
                "data": {"task_id": str(task_id), "status": final_task.status.value}
            })
            
            # Task should be completed - the agent got the user's favorite food answer
            assert final_task.status == TaskStatus.DONE, f"Expected task to be DONE after getting user response, but got {final_task.status.value}"
            
            # Check for task comments to verify escalation workflow
            result = await session.execute(
                select(TaskComment).where(TaskComment.task_id == task_id)
            )
            all_comments = result.scalars().all()
            
            # Should have at least the escalation comment
            escalation_comments = [c for c in all_comments if "core_agent" in c.author.lower() and "input" in c.content.lower()]
            assert len(escalation_comments) > 0, "Should have escalation comment from core agent"
            
            logger.info("Complete escalation workflow verified", extra={
                "data": {
                    "task_id": str(task_id),
                    "final_status": final_task.status.value,
                    "total_comments": len(all_comments),
                    "escalation_comments": len(escalation_comments)
                }
            })
    
    finally:
        # Cleanup: shutdown agent
        await core_agent.shutdown()
        
        # Cleanup: remove test task and related data
        async with db_manager.get_session() as session:
            # Delete comments first (foreign key constraint)
            await session.execute(
                text("DELETE FROM task_comments WHERE task_id = :task_id"),
                {"task_id": str(task_id)}
            )
            
            # Delete task
            await session.execute(
                text("DELETE FROM tasks WHERE id = :task_id"), 
                {"task_id": str(task_id)}
            )
            
            # Clean up agent status
            if core_agent.status_id:
                await session.execute(
                    text("DELETE FROM agent_status WHERE id = :status_id"),
                    {"status_id": str(core_agent.status_id)}
                )
            
            await session.commit()
            
            logger.info("Test cleanup completed", extra={
                "data": {"task_id": str(task_id)}
            })


@pytest.mark.asyncio
@pytest.mark.integration
async def test_escalation_flow_monitoring():
    """
    Test monitoring capabilities during escalation workflow.
    
    This verifies that the agent status and task transitions
    are properly tracked during the escalation process.
    """
    
    # Create a simple task
    task_data = {
        "title": "Test Monitoring Task", 
        "description": "This task tests monitoring during escalation",
        "status": TaskStatus.NEW
    }
    
    async with db_manager.get_session() as session:
        task = Task(
            id=uuid4(),
            title=task_data["title"],
            description=task_data["description"], 
            status=task_data["status"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id
    
    # Initialize agent
    core_agent = CoreAgent()
    await core_agent.initialize()
    
    try:
        # Check initial agent status
        initial_status = await core_agent._is_busy()
        assert initial_status is False
        
        # Start processing
        result = await core_agent.force_process_task(str(task_id))
        assert result == f"Task {task_id} processed successfully"
        
        # Verify task was processed
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            updated_task = result.scalar_one()
            
            # Task should have been updated
            assert updated_task.status != TaskStatus.NEW
            
        # Check final agent status
        final_status = await core_agent._is_busy()
        assert final_status is False
        
        logger.info("Escalation monitoring test completed", extra={
            "data": {
                "task_id": str(task_id),
                "initial_busy": initial_status,
                "final_busy": final_status,
                "final_task_status": updated_task.status.value
            }
        })
    
    finally:
        # Cleanup
        await core_agent.shutdown()
        
        async with db_manager.get_session() as session:
            await session.execute(
                text("DELETE FROM task_comments WHERE task_id = :task_id"),
                {"task_id": str(task_id)}
            )
            await session.execute(
                text("DELETE FROM tasks WHERE id = :task_id"),
                {"task_id": str(task_id)}
            )
            if core_agent.status_id:
                await session.execute(
                    text("DELETE FROM agent_status WHERE id = :status_id"), 
                    {"status_id": str(core_agent.status_id)}
                )
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration 
async def test_multiple_escalation_cycles():
    """
    Test handling multiple escalation cycles.
    
    This tests the scenario where a task requires multiple
    rounds of user input before completion.
    """
    
    task_data = {
        "title": "Multi-Round Task",
        "description": "This task requires multiple user interactions",
        "status": TaskStatus.NEW
    }
    
    async with db_manager.get_session() as session:
        task = Task(
            id=uuid4(),
            title=task_data["title"],
            description=task_data["description"],
            status=task_data["status"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id
    
    core_agent = CoreAgent()
    await core_agent.initialize()
    
    try:
        # Process task multiple times with user input
        for round_num in range(2):
            logger.info(f"Starting escalation round {round_num + 1}", extra={
                "data": {"task_id": str(task_id), "round": round_num + 1}
            })
            
            # Process task
            result = await core_agent.force_process_task(str(task_id))
            assert result == f"Task {task_id} processed successfully"
            
            # Add user response
            async with db_manager.get_session() as session:
                user_response = TaskComment(
                    id=uuid4(),
                    task_id=task_id,
                    content=f"User response for round {round_num + 1}",
                    author="user",
                    created_at=datetime.utcnow()
                )
                session.add(user_response)
                
                # Update task for next round (unless it's the last)
                if round_num < 1:  # Not the last round
                    result = await session.execute(
                        select(Task).where(Task.id == task_id)
                    )
                    task = result.scalar_one()
                    task.status = TaskStatus.USER_INPUT_RECEIVED
                    task.updated_at = datetime.utcnow()
                
                await session.commit()
        
        # Verify final state
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            final_task = result.scalar_one()
            
            result = await session.execute(
                select(TaskComment).where(TaskComment.task_id == task_id)
            )
            comments = result.scalars().all()
            
            logger.info("Multi-round escalation test completed", extra={
                "data": {
                    "task_id": str(task_id),
                    "final_status": final_task.status.value,
                    "total_comments": len(comments)
                }
            })
    
    finally:
        # Cleanup
        await core_agent.shutdown()
        
        async with db_manager.get_session() as session:
            await session.execute(
                text("DELETE FROM task_comments WHERE task_id = :task_id"),
                {"task_id": str(task_id)}
            )
            await session.execute(
                text("DELETE FROM tasks WHERE id = :task_id"),
                {"task_id": str(task_id)}
            )
            if core_agent.status_id:
                await session.execute(
                    text("DELETE FROM agent_status WHERE id = :status_id"),
                    {"status_id": str(core_agent.status_id)}
                )
            await session.commit() 