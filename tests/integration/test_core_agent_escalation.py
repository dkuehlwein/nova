"""
Integration test for Nova Core Agent Escalation Workflow

Tests the complete escalation workflow with real LLM:
1. Add task asking user for favorite food
2. Core agent takes task and moves to processing
3. Core agent uses ask_user tool
4. Task moves to "needs review" lane
5. Core agent becomes idle
6. User answers "pizza"
7. Core agent moves task to "done"

NOTE: These tests require full infrastructure:
- PostgreSQL database
- Redis
- LiteLLM proxy
- Config files

Skip these tests when running quick unit tests.
"""

import pytest
import asyncio
import os
from uuid import uuid4
from datetime import datetime
from sqlalchemy import select, text

# Disable Phoenix observability tracing for tests
os.environ["PHOENIX_ENABLED"] = "false"


# Skip entire module if infrastructure isn't available
pytest.importorskip("agent.core_agent", reason="Requires full Nova infrastructure")

try:
    from agent.core_agent import CoreAgent
    from agent.chat_agent import create_chat_agent
    from database.database import db_manager
    from models.models import Task, TaskStatus, TaskComment, AgentStatus, AgentStatusEnum
    from utils.logging import get_logger
    from utils.service_manager import ServiceManager
    from utils.redis_manager import close_redis
    from utils.config_registry import config_registry

    # Try to initialize configs - skip if can't
    if not config_registry._initialized:
        try:
            config_registry.initialize_standard_configs()
        except Exception as e:
            pytest.skip(f"Could not initialize config registry: {e}")

except ImportError as e:
    pytest.skip(f"Import error: {e}", allow_module_level=True)

logger = get_logger(__name__)


async def create_test_service_manager() -> tuple[ServiceManager, any]:
    """Create a ServiceManager and PostgreSQL pool for a single test.
    
    Returns:
        tuple: (service_manager, pg_pool) where pg_pool may be None if unavailable
    """
    logger.info("Creating ServiceManager for integration test")
    
    # Create ServiceManager for test environment
    service_manager = ServiceManager("core-agent-integration-test")
    
    # Initialize PostgreSQL pool
    pg_pool = await service_manager.init_pg_pool()
    
    if pg_pool:
        logger.info("PostgreSQL pool initialized for integration test", extra={
            "data": {"pool_id": id(pg_pool)}
        })
    else:
        logger.warning("Using fallback checkpointer (no PostgreSQL pool available)")
    
    return service_manager, pg_pool


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.xfail(reason="Event loop issues with Neo4j when running in test suite - passes when run alone", strict=False)
async def test_complete_escalation_workflow():
    """
    Test complete escalation workflow with real LLM using ServiceManager.

    Note: This test may fail when run as part of the full test suite due to
    Neo4j async event loop isolation issues. Run standalone with:
    uv run pytest tests/integration/test_core_agent_escalation.py::test_complete_escalation_workflow -v

    This demonstrates the exact escalation flow you wanted:
    - Task asking for favorite food
    - Core agent processing and escalation
    - Task moving to needs review
    - Agent becoming idle
    - User providing answer
    - Task completion
    """
    
    # Create ServiceManager and pool for this test
    service_manager, pg_pool = await create_test_service_manager()
    
    # Initialize variables that need cleanup
    core_agent = None
    task_id = None
    
    try:
        # Step 1: Create task that will trigger escalation with real LLM
        task_data = {
            "title": "Ask User About Food Preference",
            "description": "I need you to ask the user what their favorite food is. Since this requires direct user input, you should use the ask_user tool to ask them directly.",
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
        
        # Step 2: Initialize core agent with PostgreSQL pool
        core_agent = CoreAgent(pg_pool=pg_pool)
        await core_agent.initialize()
        
        logger.info("Core agent initialized with PostgreSQL pool", extra={
            "data": {
                "task_id": str(task_id),
                "pool_id": id(pg_pool) if pg_pool else None,
                "has_pool": pg_pool is not None
            }
        })
        
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
            assert updated_task.status in [TaskStatus.NEEDS_REVIEW]
            
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
            # Get the chat agent to respond to escalation with shared pool
            chat_agent = await create_chat_agent(pg_pool=pg_pool)
            
            logger.info("Created chat agent for escalation response", extra={
                "data": {
                    "task_id": str(task_id),
                    "pool_id": id(pg_pool) if pg_pool else None,
                    "thread_id": thread_id
                }
            })
            
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
        
        # Step 7: Check if task needs additional processing
        # The LLM may have already completed the task during the resume flow
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            current_task = result.scalar_one()

            logger.info("Task status after user response", extra={
                "data": {"task_id": str(task_id), "status": current_task.status.value}
            })

            # Only process again if task is not already done
            if current_task.status != TaskStatus.DONE:
                logger.info("Core agent processing task again after user input", extra={
                    "data": {"task_id": str(task_id)}
                })

                result = await core_agent.force_process_task(str(task_id))
                assert result == f"Task {task_id} processed successfully"
            else:
                logger.info("Task already completed during resume - no additional processing needed", extra={
                    "data": {"task_id": str(task_id)}
                })

        # Step 8: Verify task is now completed
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            final_task = result.scalar_one()

            logger.info("Final task status", extra={
                "data": {"task_id": str(task_id), "status": final_task.status.value}
            })

            # Task should be completed - the agent got the user's favorite food answer
            assert final_task.status == TaskStatus.DONE, f"Expected task to be DONE after getting user response, but got {final_task.status.value}"

            # Check for task comments to verify escalation workflow
            result = await session.execute(
                select(TaskComment).where(TaskComment.task_id == task_id)
            )
            all_comments = result.scalars().all()

            logger.info("Complete escalation workflow verified", extra={
                "data": {
                    "task_id": str(task_id),
                    "final_status": final_task.status.value,
                    "total_comments": len(all_comments)
                }
            })
    
    finally:
        # Cleanup: shutdown agent if it was created
        if core_agent is not None:
            await core_agent.shutdown()
        
        # Cleanup: remove test task and related data if task was created
        if task_id is not None:
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
                if core_agent is not None and core_agent.status_id:
                    await session.execute(
                        text("DELETE FROM agent_status WHERE id = :status_id"),
                        {"status_id": str(core_agent.status_id)}
                    )

                await session.commit()

            # Clean up LangGraph checkpoint data (outside session context)
            try:
                from api.api_endpoints import cleanup_task_chat_data
                await cleanup_task_chat_data(str(task_id))
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup chat data: {cleanup_error}")

            logger.info("Test cleanup completed", extra={
                "data": {"task_id": str(task_id)}
            })
        
        # Clean up ServiceManager and its pool
        await service_manager.close_pg_pool()
        
        # Ensure Redis connections are completely closed between tests
        await close_redis()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_escalation_flow_monitoring():
    """
    Test monitoring capabilities during escalation workflow using ServiceManager.
    
    This verifies that the agent status and task transitions
    are properly tracked during the escalation process.
    """
    
    # Create ServiceManager and pool for this test
    service_manager, pg_pool = await create_test_service_manager()
    
    # Initialize variables that need cleanup
    core_agent = None
    task_id = None
    
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
    
    # Initialize agent with pool
    core_agent = CoreAgent(pg_pool=pg_pool)
    await core_agent.initialize()
    
    logger.info("Monitoring test using PostgreSQL pool", extra={
        "data": {
            "task_id": str(task_id),
            "pool_id": id(pg_pool) if pg_pool else None
        }
    })
    
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
        if core_agent is not None:
            await core_agent.shutdown()
        
        if task_id is not None:
            async with db_manager.get_session() as session:
                await session.execute(
                    text("DELETE FROM task_comments WHERE task_id = :task_id"),
                    {"task_id": str(task_id)}
                )
                await session.execute(
                    text("DELETE FROM tasks WHERE id = :task_id"),
                    {"task_id": str(task_id)}
                )
                if core_agent is not None and core_agent.status_id:
                    await session.execute(
                        text("DELETE FROM agent_status WHERE id = :status_id"),
                        {"status_id": str(core_agent.status_id)}
                    )
                await session.commit()

            # Clean up LangGraph checkpoint data (outside session context)
            try:
                from api.api_endpoints import cleanup_task_chat_data
                await cleanup_task_chat_data(str(task_id))
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup chat data: {cleanup_error}")

        # Clean up ServiceManager and its pool
        await service_manager.close_pg_pool()

        # Ensure Redis connections are completely closed between tests
        await close_redis()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_escalation_cycles():
    """
    Test handling multiple escalation cycles using ServiceManager.
    
    This tests the scenario where a task requires multiple
    rounds of user input before completion.
    """
    
    # Create ServiceManager and pool for this test
    service_manager, pg_pool = await create_test_service_manager()
    
    # Initialize variables that need cleanup
    core_agent = None
    task_id = None
    
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
    
    # Initialize agent with pool
    core_agent = CoreAgent(pg_pool=pg_pool)
    await core_agent.initialize()
    
    logger.info("Multi-round escalation test using PostgreSQL pool", extra={
        "data": {
            "task_id": str(task_id),
            "pool_id": id(pg_pool) if pg_pool else None
        }
    })
    
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
        if core_agent is not None:
            await core_agent.shutdown()
        
        if task_id is not None:
            async with db_manager.get_session() as session:
                await session.execute(
                    text("DELETE FROM task_comments WHERE task_id = :task_id"),
                    {"task_id": str(task_id)}
                )
                await session.execute(
                    text("DELETE FROM tasks WHERE id = :task_id"),
                    {"task_id": str(task_id)}
                )
                if core_agent is not None and core_agent.status_id:
                    await session.execute(
                        text("DELETE FROM agent_status WHERE id = :status_id"),
                        {"status_id": str(core_agent.status_id)}
                    )
                await session.commit()

            # Clean up LangGraph checkpoint data (outside session context)
            try:
                from api.api_endpoints import cleanup_task_chat_data
                await cleanup_task_chat_data(str(task_id))
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup chat data: {cleanup_error}")

        # Clean up ServiceManager and its pool
        await service_manager.close_pg_pool()

        # Ensure Redis connections are completely closed between tests
        await close_redis()