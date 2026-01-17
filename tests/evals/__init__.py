"""
Nova Agent Evaluation Framework

A custom evaluation framework for testing Nova's agent capabilities,
based on Anthropic's "Demystifying Evals for AI Agents" methodology.

Key features:
- Multi-turn conversation testing
- pass@k metrics for handling LLM non-determinism
- Code-based grading (database state, tool calls, message patterns)
- Transcript storage for debugging
- CI integration with fast/slow test suites
"""

from tests.evals.framework.eval_case import EvalCase, EvalResult
from tests.evals.framework.eval_runner import EvalRunner

__all__ = ["EvalCase", "EvalResult", "EvalRunner"]
