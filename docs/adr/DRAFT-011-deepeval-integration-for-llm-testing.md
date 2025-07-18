# ADR 011: DeepEval Integration for LLM Testing and Evaluation

## Status

**PROPOSED** - 2025-07-16

## Context

Nova currently lacks a systematic approach to test and evaluate LLM model performance, tool calling capabilities, and prompt changes. As we scale with multiple models (phi-4-Q6_K, Qwen3-14B, etc.) and evolve our prompts and agent architecture, we need:

1. **Regression Testing**: Ensure model/prompt changes don't break existing functionality
2. **Model Comparison**: Systematically compare different models' performance
3. **Tool Calling Validation**: Verify escalation and other tools work correctly
4. **Production Monitoring**: Track model performance in production
5. **Automated CI/CD Integration**: Prevent broken deployments

### Current State

- Manual testing with custom scripts (`test_model_suite.py`, `test_simple_escalation.py`)
- No systematic evaluation framework
- No regression testing for prompt changes
- Limited tool calling validation
- No production performance monitoring

### Problems

1. **Manual Testing Burden**: Each model change requires manual verification
2. **Regression Risk**: Prompt changes can break tool calling without detection
3. **Inconsistent Evaluation**: No standardized metrics across models
4. **Production Blind Spots**: No visibility into model performance degradation
5. **CI/CD Gap**: No automated testing prevents broken deployments

## Decision

We will integrate **DeepEval** as Nova's primary LLM evaluation framework, leveraging its compatibility with our existing LiteLLM proxy and local models.

### Key Components

1. **DeepEval Framework**: Open-source LLM evaluation with 14+ metrics
2. **LiteLLM Integration**: Direct integration with Nova's existing LiteLLM proxy
3. **Agent Evaluation**: Specialized testing for LangGraph chat agents
4. **Custom Metrics**: Nova-specific evaluation criteria
5. **CI/CD Integration**: Automated testing in deployment pipeline

## Implementation Plan

### Phase 1: Core Integration (Week 1-2)

#### 1.1 DeepEval Setup
```bash
# Install DeepEval in Nova backend
cd backend && uv add deepeval
```

#### 1.2 Model Configuration
```python
# nova/evaluation/models.py
from deepeval.models import LiteLLMModel

def get_nova_model(model_name: str) -> LiteLLMModel:
    return LiteLLMModel(
        model=model_name,
        api_base="http://localhost:4000",  # Nova's LiteLLM proxy
        api_key="sk-1234"  # Nova's master key
    )
```

#### 1.3 Core Metrics Implementation
```python
# nova/evaluation/metrics.py
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    FunctionalMetric
)

class NovaToolCallingMetric(FunctionalMetric):
    def __init__(self, threshold: float = 0.8):
        def evaluate_tool_calling(actual_output, expected_output, context):
            # Check if escalate_to_human tool was called correctly
            if "escalate_to_human" in actual_output:
                return 1.0
            return 0.0
        
        super().__init__(
            name="Nova Tool Calling",
            evaluation_function=evaluate_tool_calling,
            threshold=threshold
        )
```

### Phase 2: Test Suite Development (Week 2-3)

#### 2.1 Golden Dataset Creation
```python
# nova/evaluation/datasets.py
NOVA_GOLDEN_DATASET = [
    {
        "input": "**ask user** - Ask the user what his favourite ice cream is",
        "expected_output": "escalate_to_human",
        "context": ["Nova task format", "User interaction required"],
        "test_type": "tool_calling"
    },
    {
        "input": "**Current Task:** Create a follow-up task for the meeting",
        "expected_output": "create_task",
        "context": ["Nova task management"],
        "test_type": "task_management"
    }
    # ... additional test cases
]
```

#### 2.2 Agent Evaluation Framework
```python
# nova/evaluation/agent_evaluator.py
class NovaAgentEvaluator:
    def __init__(self, model_name: str):
        self.model = get_nova_model(model_name)
        self.metrics = [
            NovaToolCallingMetric(),
            AnswerRelevancyMetric(model=self.model),
            FaithfulnessMetric(model=self.model)
        ]
    
    async def evaluate_chat_agent(self, test_cases: List[Dict]) -> Dict:
        # Create Nova chat agent
        agent = await create_chat_agent(include_escalation=True)
        
        results = []
        for test_case in test_cases:
            # Run agent with test input
            response = await agent.ainvoke({
                "messages": [{"role": "user", "content": test_case["input"]}]
            })
            
            # Evaluate response
            test_result = evaluate(
                test_cases=[LLMTestCase(
                    input=test_case["input"],
                    actual_output=response["messages"][-1].content,
                    expected_output=test_case["expected_output"],
                    context=test_case["context"]
                )],
                metrics=self.metrics,
                model=self.model
            )
            results.append(test_result)
        
        return self._aggregate_results(results)
```

### Phase 3: CI/CD Integration (Week 3-4)

#### 3.1 GitHub Actions Workflow
```yaml
# .github/workflows/llm-evaluation.yml
name: LLM Model Evaluation

on:
  push:
    paths:
      - 'backend/agent/prompts/**'
      - 'configs/litellm_config.yaml'
      - 'backend/agent/llm.py'

jobs:
  evaluate-models:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Nova Test Environment
        run: |
          docker-compose up -d postgres redis llamacpp litellm
          sleep 30
      
      - name: Run DeepEval Test Suite
        run: |
          cd backend
          uv run python -m nova.evaluation.runner --model phi-4-Q6_K
          
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: evaluation-results
          path: evaluation_results.json
```

#### 3.2 Automated Regression Testing
```python
# nova/evaluation/regression_tester.py
class NovaRegressionTester:
    def __init__(self):
        self.baseline_results = self.load_baseline()
        
    def run_regression_test(self, model_name: str) -> bool:
        current_results = self.evaluate_model(model_name)
        
        # Compare against baseline
        for metric_name, baseline_score in self.baseline_results.items():
            current_score = current_results[metric_name]
            
            if current_score < baseline_score - 0.1:  # 10% degradation threshold
                raise RegressionError(
                    f"Regression detected in {metric_name}: "
                    f"{current_score} < {baseline_score}"
                )
        
        return True
```

### Phase 4: Production Monitoring (Week 4-5)

#### 4.1 Real-time Evaluation
```python
# nova/evaluation/production_monitor.py
class NovaProductionMonitor:
    def __init__(self):
        self.metrics = [NovaToolCallingMetric()]
        
    async def monitor_chat_response(self, user_input: str, agent_response: str):
        """Monitor production chat responses."""
        test_case = LLMTestCase(
            input=user_input,
            actual_output=agent_response,
            context=["production_monitoring"]
        )
        
        results = evaluate(
            test_cases=[test_case],
            metrics=self.metrics
        )
        
        # Log to monitoring system
        await self.log_evaluation_results(results)
```

#### 4.2 Performance Dashboard
```python
# nova/evaluation/dashboard.py
class NovaEvaluationDashboard:
    def get_model_performance_summary(self, model_name: str) -> Dict:
        return {
            "tool_calling_accuracy": self.get_metric_history("tool_calling"),
            "response_quality": self.get_metric_history("answer_relevancy"),
            "regression_alerts": self.get_recent_regressions(),
            "model_comparison": self.compare_models()
        }
```

## Integration Points

### 1. LiteLLM Proxy Integration
DeepEval will connect to Nova's existing LiteLLM proxy:
```python
model = LiteLLMModel(
    model="phi-4-Q6_K",
    api_base="http://localhost:4000",
    api_key="sk-1234"
)
```

### 2. Chat Agent Integration
Direct integration with Nova's `create_chat_agent()`:
```python
agent = await create_chat_agent(include_escalation=True)
response = await agent.ainvoke(test_input)
# Evaluate response with DeepEval
```

### 3. Configuration Management
Leverage Nova's existing config system:
```python
evaluation_config = await get_evaluation_config()
```

## Benefits

### 1. Systematic Evaluation
- Consistent metrics across all models
- Automated regression detection
- Standardized evaluation process

### 2. Production Quality
- Prevent broken deployments
- Monitor model performance in real-time
- Early detection of issues

### 3. Development Efficiency
- Automated testing reduces manual effort
- Faster model comparison and selection
- Continuous improvement feedback

### 4. Risk Mitigation
- Catch regressions before deployment
- Validate tool calling functionality
- Monitor production performance

## Risks and Mitigation

### Risk 1: DeepEval Dependency
- **Mitigation**: DeepEval is open-source and actively maintained
- **Fallback**: Custom evaluation functions if needed

### Risk 2: Evaluation Latency
- **Mitigation**: Async evaluation, background processing
- **Monitoring**: Track evaluation performance

### Risk 3: False Positives
- **Mitigation**: Carefully tuned thresholds, human review
- **Iteration**: Continuous improvement of metrics

## Alternatives Considered

### 1. Custom Evaluation Framework
- **Pros**: Full control, tailored to Nova
- **Cons**: High development cost, maintenance burden

### 2. Langfuse Integration
- **Pros**: Good LangChain integration
- **Cons**: More complex setup, less comprehensive metrics

### 3. MLFlow Evaluation
- **Pros**: Mature platform
- **Cons**: Heavyweight, less LLM-specific

## Implementation Timeline

- **Week 1**: Core DeepEval integration, basic metrics
- **Week 2**: Agent evaluation framework, golden dataset
- **Week 3**: CI/CD integration, automated testing
- **Week 4**: Production monitoring setup
- **Week 5**: Dashboard and reporting

## Success Metrics

1. **Automated Testing**: 100% of model changes tested automatically
2. **Regression Prevention**: Zero production regressions due to model changes
3. **Development Speed**: 50% reduction in manual testing time
4. **Model Quality**: Consistent evaluation metrics across all models
5. **Production Monitoring**: Real-time visibility into model performance

## Next Steps

1. Install DeepEval in Nova backend environment
2. Create initial model configuration for phi-4-Q6_K
3. Implement core Nova-specific metrics
4. Build golden dataset with key Nova scenarios
5. Set up CI/CD integration for automated testing

## References

- [DeepEval Documentation](https://deepeval.com/docs/metrics-introduction)
- [LiteLLM Integration](https://deepeval.com/integrations/models/litellm)
- [LangGraph Agent Evaluation](https://langfuse.com/docs/integrations/langchain/example-langgraph-agents)
- [Nova Test Suite Implementation](../test_model_suite.py)