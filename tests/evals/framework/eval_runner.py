"""
EvalRunner - Core evaluation execution engine.

Executes eval cases, manages trials, applies grading functions,
and collects metrics. Designed to work with Nova's existing
test infrastructure (ServiceManager, db_manager, etc.).
"""

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from tests.evals.framework.eval_case import EvalCase, EvalResult, GradeResult

logger = logging.getLogger(__name__)


class EvalRunner:
    """
    Executes evaluation cases and collects results.

    The runner handles:
    - Database setup/teardown per trial
    - Agent invocation with proper configuration
    - Grading function execution
    - Metrics collection (latency, tokens, pass@k)
    - Transcript storage for debugging
    """

    def __init__(
        self,
        pg_pool,
        checkpointer=None,
        model_override: str | None = None,
    ):
        """
        Initialize the eval runner.

        Args:
            pg_pool: PostgreSQL connection pool for database operations
            checkpointer: Optional LangGraph checkpointer (created from pool if not provided)
            model_override: Optional model to use instead of eval case default
        """
        self.pg_pool = pg_pool
        self.checkpointer = checkpointer
        self.model_override = model_override
        self._agent = None
        self._db_session = None

    async def run_eval(self, eval_case: EvalCase) -> list[EvalResult]:
        """
        Run all trials for an eval case.

        Args:
            eval_case: The evaluation case to run

        Returns:
            List of EvalResult, one per trial
        """
        results = []
        model = self.model_override or eval_case.model

        logger.info(
            f"Starting eval '{eval_case.name}' with {eval_case.num_trials} trials"
        )

        for trial in range(1, eval_case.num_trials + 1):
            logger.info(f"Running trial {trial}/{eval_case.num_trials}")

            try:
                result = await self._run_single_trial(eval_case, trial, model)
                results.append(result)

                if result.passed:
                    logger.info(f"Trial {trial} PASSED")
                else:
                    failed_graders = [
                        gr.grader_name for gr in result.grade_results if not gr.passed
                    ]
                    logger.warning(
                        f"Trial {trial} FAILED - graders: {failed_graders}"
                    )

            except Exception as e:
                logger.error(f"Trial {trial} ERROR: {e}")
                results.append(
                    EvalResult(
                        eval_name=eval_case.name,
                        trial_number=trial,
                        passed=False,
                        grade_results=[],
                        transcript=[],
                        start_time=datetime.utcnow(),
                        end_time=datetime.utcnow(),
                        latency_ms=0,
                        error=str(e),
                        model=model or "",
                    )
                )

        return results

    async def _run_single_trial(
        self, eval_case: EvalCase, trial_number: int, model: str | None
    ) -> EvalResult:
        """Run a single trial of an eval case."""
        start_time = datetime.utcnow()
        transcript = []
        grade_results = []

        # Generate unique thread ID for this trial
        thread_id = f"eval_{eval_case.name}_{trial_number}_{uuid4().hex[:8]}"

        try:
            # Setup: Create initial DB state
            db_context = await self._setup_db_state(eval_case.initial_db_state)

            # Create or get agent
            agent = await self._get_agent(eval_case, model)

            # Build initial messages
            messages = self._build_messages(eval_case.initial_messages)
            transcript.extend(
                [{"role": m.type, "content": m.content} for m in messages]
            )

            # Invoke agent with timeout
            config = RunnableConfig(configurable={"thread_id": thread_id})

            result = await asyncio.wait_for(
                agent.ainvoke({"messages": messages}, config),
                timeout=eval_case.timeout_seconds,
            )

            # Extract transcript from result
            if "messages" in result:
                for msg in result["messages"]:
                    transcript.append(self._message_to_dict(msg))

            # Run grading functions
            grade_results = await self._run_graders(
                eval_case, result, db_context, thread_id
            )

            # Determine overall pass/fail
            passed = all(gr.passed for gr in grade_results)

        except asyncio.TimeoutError:
            grade_results = [
                GradeResult(
                    grader_name="timeout",
                    passed=False,
                    message=f"Eval timed out after {eval_case.timeout_seconds}s",
                )
            ]
            passed = False

        except Exception as e:
            grade_results = [
                GradeResult(
                    grader_name="exception",
                    passed=False,
                    message=f"Eval raised exception: {e}",
                )
            ]
            passed = False

        finally:
            # Cleanup: Remove test data
            await self._cleanup_db_state(db_context if "db_context" in dir() else {})

        end_time = datetime.utcnow()
        latency_ms = (end_time - start_time).total_seconds() * 1000

        return EvalResult(
            eval_name=eval_case.name,
            trial_number=trial_number,
            passed=passed,
            grade_results=grade_results,
            transcript=transcript,
            start_time=start_time,
            end_time=end_time,
            latency_ms=latency_ms,
            model=model or "",
        )

    async def _get_agent(self, eval_case: EvalCase, model: str | None):
        """Get or create the agent for this eval.

        Args:
            eval_case: The evaluation case being run
            model: Optional model name to use for this eval
        """
        if self._agent is not None:
            return self._agent

        # Import here to avoid circular imports
        from agent.chat_agent import create_chat_agent

        # Create agent with appropriate configuration
        self._agent = await create_chat_agent(
            pg_pool=self.pg_pool,
            include_escalation=(eval_case.agent_type == "core"),
            model_override=model,
        )

        return self._agent

    def _build_messages(
        self, initial_messages: list[dict[str, str]]
    ) -> list[HumanMessage | AIMessage]:
        """Convert initial message dicts to LangChain messages."""
        messages = []
        for msg in initial_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        return messages

    def _message_to_dict(self, msg) -> dict[str, Any]:
        """Convert a LangChain message to a serializable dict."""
        result = {
            "role": getattr(msg, "type", "unknown"),
            "content": getattr(msg, "content", ""),
        }

        # Capture tool calls if present
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            result["tool_calls"] = [
                {
                    "name": tc.get("name", tc.get("tool", "")),
                    "args": tc.get("args", {}),
                    "id": tc.get("id", ""),
                }
                for tc in msg.tool_calls
            ]

        # Capture tool message details
        if isinstance(msg, ToolMessage):
            result["tool_call_id"] = getattr(msg, "tool_call_id", "")
            result["name"] = getattr(msg, "name", "")

        return result

    async def _setup_db_state(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        """
        Set up initial database state for the eval.

        Returns context dict with created entity IDs for cleanup.
        """
        context = {"created_task_ids": [], "created_project_ids": []}

        if not initial_state:
            return context

        # Import database manager
        from database.database import db_manager
        from models.models import Task, TaskStatus

        async with db_manager.get_session() as session:
            # Create tasks if specified
            for task_data in initial_state.get("tasks", []):
                task = Task(
                    title=task_data.get("title", "Eval Test Task"),
                    description=task_data.get("description", ""),
                    status=TaskStatus(task_data.get("status", "new")),
                )
                session.add(task)
                await session.flush()
                context["created_task_ids"].append(str(task.id))

            await session.commit()

        return context

    async def _cleanup_db_state(self, context: dict[str, Any]):
        """Clean up database state created during eval."""
        if not context:
            return

        from database.database import db_manager
        from models.models import Task
        from sqlalchemy import delete

        async with db_manager.get_session() as session:
            # Delete created tasks
            for task_id in context.get("created_task_ids", []):
                try:
                    await session.execute(
                        delete(Task).where(Task.id == task_id)
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete task {task_id}: {e}")

            await session.commit()

    async def _run_graders(
        self,
        eval_case: EvalCase,
        agent_result: dict[str, Any],
        db_context: dict[str, Any],
        thread_id: str,
    ) -> list[GradeResult]:
        """Run all grading functions for the eval case."""
        results = []

        for grader_fn in eval_case.grading_functions:
            grader_name = getattr(grader_fn, "__name__", str(grader_fn))

            try:
                passed, message = await grader_fn(
                    result=agent_result,
                    expected=eval_case.expected_outcomes,
                    db_context=db_context,
                    thread_id=thread_id,
                )
                results.append(
                    GradeResult(grader_name=grader_name, passed=passed, message=message)
                )
            except Exception as e:
                results.append(
                    GradeResult(
                        grader_name=grader_name,
                        passed=False,
                        message=f"Grader raised exception: {e}",
                    )
                )

        return results


def calculate_pass_at_k(results: list[EvalResult]) -> float:
    """
    Calculate pass@k metric: probability of at least one success in k trials.

    Returns a value between 0.0 and 1.0.
    """
    if not results:
        return 0.0

    # pass@k = 1 if at least one trial passed
    return 1.0 if any(r.passed for r in results) else 0.0


def calculate_pass_all_k(results: list[EvalResult]) -> float:
    """
    Calculate pass^k metric: probability of all k trials succeeding.

    This measures reliability - a high pass^k means consistent behavior.
    Returns a value between 0.0 and 1.0.
    """
    if not results:
        return 0.0

    return 1.0 if all(r.passed for r in results) else 0.0
