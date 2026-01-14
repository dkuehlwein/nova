"""
EvalCase and EvalResult dataclasses for the evaluation framework.

Based on Anthropic's evaluation methodology:
- EvalCase defines a single evaluation scenario
- EvalResult captures the outcome of running an eval
- GradeResult captures individual grading function results
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Literal
from datetime import datetime


@dataclass
class GradeResult:
    """Result from a single grading function."""

    grader_name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Result from running a single trial of an eval case."""

    eval_name: str
    trial_number: int
    passed: bool
    grade_results: list[GradeResult]
    transcript: list[dict[str, Any]]  # Full conversation history
    start_time: datetime
    end_time: datetime
    latency_ms: float
    token_usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    model: str = ""

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class EvalCase:
    """
    Defines a single evaluation case for testing agent capabilities.

    Attributes:
        name: Unique identifier for this eval case
        description: Human-readable description of what this eval tests
        tags: Categories for filtering (e.g., ["fast", "calendar", "conflict"])
        initial_db_state: Database records to create before running eval
        initial_messages: Conversation history to set up context
        grading_functions: Async functions that check outcomes
        expected_outcomes: Data passed to grading functions for verification
        agent_type: Which agent to test ("chat" or "core")
        use_real_mcp: Whether to use real MCP servers or mocks
        num_trials: Number of times to run this eval (for pass@k metrics)
        model: Optional model override (None = use default from config)
        timeout_seconds: Maximum time to wait for agent response
    """

    name: str
    description: str
    tags: list[str]
    grading_functions: list[Callable[..., Awaitable[tuple[bool, str]]]]
    expected_outcomes: dict[str, Any]

    # Setup
    initial_db_state: dict[str, Any] = field(default_factory=dict)
    initial_messages: list[dict[str, str]] = field(default_factory=list)

    # Configuration
    agent_type: Literal["chat", "core"] = "chat"
    use_real_mcp: bool = False
    num_trials: int = 3
    model: str | None = None
    timeout_seconds: float = 300.0  # 5 minutes default

    def __post_init__(self):
        """Validate the eval case configuration."""
        if not self.name:
            raise ValueError("EvalCase name is required")
        if not self.grading_functions:
            raise ValueError("At least one grading function is required")
        if self.num_trials < 1:
            raise ValueError("num_trials must be at least 1")
