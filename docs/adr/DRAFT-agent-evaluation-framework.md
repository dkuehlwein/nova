# ADR-020: Agent Evaluation Framework

**Status**: Accepted
**Date**: 2026-01-11
**Supersedes**: DRAFT-deepeval-integration-for-llm-testing.md

---

## Context

After reviewing Anthropic's "Demystifying Evals for AI Agents" article and analyzing Nova's current testing infrastructure, we identified significant gaps in how we test Nova's agent capabilities:

**Current State:**
- **Strong**: Unit tests for agent initialization, tool loading, status management (58 tests)
- **Good**: Integration tests for calendar/email workflows (98 tests)
- **Limited**: Only 3 end2end tests, all focused on calendar conflict detection
- **Missing**: Multi-turn conversation testing, capacity/stress testing, agent capability evaluation

## Decision

Build a **custom agent evaluation framework** based on Anthropic's evaluation methodology that integrates seamlessly with Nova's existing test infrastructure.

### Key Principles from Anthropic Article

1. **Multi-turn evaluations** are essential for agents that call tools and adapt across multiple steps
2. **pass@k and pass^k metrics** handle non-determinism (success in at least 1 of k tries vs all k tries)
3. **Balanced problem sets** test both when behaviors should occur AND shouldn't (negative cases)
4. **Code-based grading first** - Check database state and function outputs (fast, deterministic)
5. **Start with 20-50 real tasks** from user failures, not perfect theoretical cases
6. **Trial repetition** is critical since LLM outputs vary between runs

### Architecture

```
tests/
├── evals/                          # NEW evaluation framework
│   ├── __init__.py
│   ├── conftest.py                # Eval-specific fixtures
│   │
│   ├── framework/                 # Reusable framework code
│   │   ├── eval_case.py          # EvalCase dataclass definition
│   │   ├── eval_runner.py        # Core runner with k-trial support
│   │   ├── graders.py            # Code-based grading functions
│   │   ├── metrics.py            # pass@k, latency, token tracking
│   │   ├── transcript_store.py   # Transcript persistence
│   │   └── monitoring_hooks.py   # Production metric integration
│   │
│   ├── test_task_management.py   # Task CRUD evals (10 cases)
│   ├── test_escalation_flow.py   # Human escalation evals
│   └── test_error_handling.py    # Error recovery evals
```

### Core Components

#### 1. EvalCase Definition
Defines a single evaluation case with:
- `initial_db_state`: Tasks/projects to create before eval
- `initial_messages`: User/assistant message sequence
- `grading_functions`: Async callables that check outcomes
- `num_trials`: k value for pass@k metrics (default 3)
- `tags`: ["fast", "slow", "task_mgmt"] for CI filtering

```python
@dataclass
class EvalCase:
    name: str
    description: str
    tags: List[str]
    initial_db_state: Dict[str, Any]
    initial_messages: List[Dict[str, str]]
    agent_type: Literal["chat", "core"] = "chat"
    use_real_mcp: bool = False
    num_trials: int = 3
    grading_functions: List[Callable]
    expected_outcomes: Dict[str, Any]
```

#### 2. EvalRunner
Executes k trials per eval case:
- Sets up fresh DB state before each trial
- Runs agent interaction (reuses `create_chat_agent()`)
- Applies grading functions
- Calculates pass@k and pass^k metrics
- Stores transcripts for review
- Reports to monitoring hooks

**Integration Points:**
- Uses `ServiceManager` for pg_pool setup (existing pattern)
- Uses `TestDataCleaner` for cleanup (proven pattern)
- Reuses `create_chat_agent()` and `CoreAgent` (no duplication)
- Stores transcripts in new `EvalTranscript` SQLAlchemy model

#### 3. Code-based Graders
Grader categories:
1. **Database state** - Check tasks, status, tags (`check_task_created`, `check_task_status`)
2. **Memory integration** - Check Graphiti entities (`check_memory_entity_added`)
3. **Agent behavior** - Check tool calls, message patterns (`check_tool_called`)
4. **Performance** - Check latency thresholds
5. **Negative cases** - Check things that should NOT happen (`check_task_not_created`)

Grader interface returns `Tuple[bool, str]` for clear failure messages:
```python
async def check_task_created(result: Any, expected: Dict[str, Any]) -> Tuple[bool, str]:
    """Returns (passed: bool, message: str)"""
    expected_title = expected.get("task_title")
    async with db_manager.get_session() as session:
        task = await session.execute(select(Task).where(Task.title == expected_title))
        if task.scalar_one_or_none():
            return True, f"Task '{expected_title}' created"
        return False, f"Task '{expected_title}' not found"
```

#### 4. Metrics Collection
Implements Anthropic's metrics:
- **pass@k**: Probability of success in at least 1 of k trials
- **pass^k**: Probability all k trials succeed (reliability measure)
- **Latency**: P50/P95/P99 across trials
- **Token usage**: Input/output tokens per eval
- **Cost estimation**: USD per eval (for budgeting)

#### 5. Production Monitoring Hooks
Designed from day one:
- Structured logging for eval metrics (ELK, Splunk ingestion)
- Hooks for Prometheus pushgateway (future)
- Hooks for Datadog API (future)

```
Eval Run → Metrics → Structured Logs →
  ├─→ Log Aggregator (immediate)
  ├─→ Prometheus (future)
  └─→ Datadog (future)
```

### Eval Categories

**A. Task Management (10 evals)**:
- Create task from natural language
- Update task status based on conversation
- Break down complex task into subtasks
- Handle duplicate task creation gracefully (negative case)

**B. Context & Memory (8 evals)**:
- Remember user preferences across conversations
- Recall past decisions from memory
- Use meeting memos to inform task context
- Avoid hallucinating past interactions

**C. Tool Usage (8 evals)**:
- Use calendar tools to check availability
- Chain multiple tools together
- Handle tool errors gracefully
- Request approval for sensitive operations

**D. Multi-turn Conversations (8 evals)**:
- Maintain context across 5+ messages
- Ask clarifying questions before acting
- Handle user changing their mind mid-conversation
- Resume interrupted conversations

**E. Edge Cases & Error Handling (6 evals)**:
- Handle empty/null responses from tools
- Recover from LLM refusals
- Process very long task descriptions
- Deal with conflicting instructions

### CI Integration Strategy

**Fast Eval Suite** (every PR):
- Marked with `@pytest.mark.fast`
- Uses `FakeChatModel` and mocked MCP
- Target: <2 minutes total
- ~10 critical evals with k=3 trials

**Slow Eval Suite** (nightly/main branch):
- Marked with `@pytest.mark.slow`
- Uses real LLM and real MCP APIs
- ~40-50 evals with k=10 trials
- Generates comprehensive report

**Model Comparison Suite** (nightly):
- Runs fast evals against multiple models (Phi-4, SmolLM3, etc.)
- Parametrized with `model_parametrization` field
- Identifies model-specific regressions

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal**: Core infrastructure + proof of concept

1. Create directory structure (`tests/evals/framework/`)
2. Implement `EvalCase` and `EvalResult` dataclasses
3. Implement basic `EvalRunner` with single trial support
4. Add `EvalTranscript` SQLAlchemy model + migration
5. Create eval fixtures in `conftest.py`
6. Write first 3 eval cases as proof of concept
7. Validate end-to-end flow

**Deliverable**: Can run basic evals with code-based grading

### Phase 2: Core Functionality (Week 2)
**Goal**: Full k-trial support + metrics

8. Implement k-trial support in `EvalRunner`
9. Implement all database graders (`graders.py`)
10. Implement metrics calculation with pass@k (`metrics.py`)
11. Implement transcript storage (`transcript_store.py`)
12. Write remaining 7 eval cases (total 10)
13. Add model parametrization support

**Deliverable**: Complete eval framework with 10 real evals

### Phase 3: Integration & Monitoring (Week 3)
**Goal**: CI integration + production monitoring hooks

14. Add monitoring hooks with structured logging (`monitoring_hooks.py`)
15. Create GitHub Actions workflow (`.github/workflows/evals.yml`)
16. Separate fast/slow eval suites with pytest markers
17. Implement eval report generator (markdown format for PRs)
18. Test with real agent runs across multiple models
19. Add flake detection (warn if pass rate varies >20% across runs)

**Deliverable**: Evals run automatically in CI with reports

### Phase 4: Expansion (Week 4)
**Goal**: Add more eval categories

20. Add 10 escalation flow evals (`test_escalation_flow.py`)
21. Add 10 error handling evals (`test_error_handling.py`)
22. Add multi-turn conversation integration tests
23. Add capacity testing suite (`tests/end2end/test_capacity.py`)
24. Document eval creation process
25. Create eval failure runbook

**Deliverable**: 30+ evals covering major agent capabilities

## Consequences

### Positive

- **No external dependencies**: Built on existing test infrastructure (pytest, fixtures)
- **Nova-specific**: Tests actual agent capabilities, not generic metrics
- **Handles non-determinism**: pass@k metrics designed for LLM variance
- **Production-ready**: Monitoring hooks from day one
- **Fast feedback**: Fast eval suite <2 minutes for CI
- **Comprehensive coverage**: 30-50 evals covering all major agent capabilities
- **Easy to extend**: Simple pattern for adding new evals
- **Debugging-friendly**: Stores transcripts, clear grading messages

### Negative

- **Custom code to maintain**: Not using off-the-shelf solution
- **Initial development effort**: 3-4 weeks for full implementation
- **Learning curve**: Team needs to learn eval framework patterns

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Eval execution too slow for CI | Tag as fast/slow; fast suite uses FakeChatModel; target <2 min |
| Non-determinism causes flake | Run k≥3 trials; use pass@k metric; store transcripts |
| Incomplete DB cleanup | Reuse TestDataCleaner; function-scoped fixtures |
| Graders too rigid | Return descriptive messages; easy to add/modify |

## Success Criteria

1. **Coverage**: 30-50 evals covering all major agent capabilities by end of Phase 4
2. **Reliability**: Fast evals have <10% flake rate
3. **Speed**: Fast regression suite runs in <2 minutes on CI
4. **Actionability**: Failed evals provide clear debugging info (transcripts, grading messages)
5. **Continuous**: Fast evals run on every PR, slow evals run nightly
6. **Living**: Process to convert user-reported failures into new evals
7. **Production-ready**: Monitoring hooks emit structured logs

## Alternatives Considered

### DeepEval (External Framework)
**Pros**: Off-the-shelf metrics, less code to maintain
**Cons**: External dependency, generic metrics not tailored to Nova, doesn't align with existing test patterns
**Decision**: Rejected in favor of custom framework

### Simple pytest tests without eval framework
**Pros**: Minimal complexity
**Cons**: No handling of non-determinism, no pass@k metrics, no transcript storage, no monitoring integration
**Decision**: Insufficient for agent testing needs

### Model-based grading (LLM judges outputs)
**Pros**: More flexible than code-based grading
**Cons**: Non-deterministic, costly, adds complexity
**Decision**: Deferred to future enhancement; start with code-based grading

## Future Enhancements (Post-Phase 4)

Out of scope for initial implementation but designed for:
1. **Model-based grading** - Use LLM to judge response quality
2. **Human review UI** - Web interface to review failed eval transcripts
3. **Eval versioning** - Track eval definitions over time
4. **Production eval replay** - Capture real user interactions and replay as evals
5. **Continuous benchmarking** - Track pass@k metrics over time
6. **Multi-agent evals** - Test coordination between chat agent and core agent
7. **Adversarial evals** - Test robustness against prompt injection

## References

- [Anthropic: Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Nova testing infrastructure: `tests/unit/`, `tests/integration/`, `tests/end2end/`
- Existing patterns: `ServiceManager`, `db_manager`, `TestDataCleaner`, `FakeChatModel`

---

**Implementation Status**: Phase 1 In Progress

### Phase 1 Progress (2026-01-14)

Implemented:
- [x] Directory structure (`tests/evals/framework/`)
- [x] `EvalCase` and `EvalResult` dataclasses (`eval_case.py`)
- [x] Basic `EvalRunner` with single trial support (`eval_runner.py`)
- [x] Initial graders: `check_task_status`, `check_tool_called`, `check_ask_user_for_conflict` (`graders.py`)
- [x] Eval fixtures in `conftest.py` (DB setup, service manager, cleanup)
- [x] Model configuration file (`models.yaml`)
- [x] First eval case: Calendar conflict detection (`test_calendar_conflict.py`)

Next steps:
- [ ] Run first eval end-to-end with real LLM
- [ ] Add k-trial support to EvalRunner
- [ ] Implement transcript storage
- [ ] Add more graders as needed
