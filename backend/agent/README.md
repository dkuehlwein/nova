# Nova LangGraph Agent

This directory contains the Nova LangGraph chat agent implementation, refactored to use LangGraph's latest best practices and patterns.

## Architecture

### Modules

- **`llm.py`**: Centralized LLM initialization and configuration
- **`chat_agent.py`**: Main LangGraph agent implementation using built-in components

### Key Features

- **Simplified Graph Structure**: Uses LangGraph's `ToolNode` and `tools_condition` for cleaner code
- **Flexible Checkpointing**: Supports both in-memory and PostgreSQL persistence
- **Centralized LLM Management**: Separated model initialization for better modularity
- **Thread-Level Persistence**: Maintains conversation history across interactions

## Configuration

### Environment Variables

```bash
# Required
GOOGLE_API_KEY="your-google-api-key"

# Optional
GOOGLE_MODEL_NAME="gemini-2.5-flash-preview-04-17"  # Default model
DATABASE_URL="postgresql://user:password@localhost:5432/nova"  # For persistence

# LangSmith (Optional)
LANGCHAIN_TRACING_V2="true"
LANGCHAIN_API_KEY="your-langsmith-api-key"
LANGCHAIN_PROJECT="nova-agent"
```

### Agent Configuration

The agent accepts runtime configuration through the `configurable` parameter:

```python
config = {
    "configurable": {
        "thread_id": "user-session-123",  # Required for persistence
        "model_name": "gemini-2.5-flash-preview-04-17",  # Optional
        "temperature": 0.7  # Optional
    }
}
```

## Usage

### Basic Usage

```python
from backend.agent.chat_agent import graph
from langchain_core.messages import HumanMessage

# Configuration with thread ID for persistence
config = {
    "configurable": {
        "thread_id": "conversation-1"
    }
}

# Invoke the agent
result = await graph.ainvoke({
    "messages": [HumanMessage(content="Create a new task called 'Review code'")]
}, config=config)

print(result['messages'][-1].content)
```

### Streaming Usage

```python
# Stream responses for real-time interaction
async for event in graph.astream({
    "messages": [HumanMessage(content="What tasks do I have today?")]
}, config=config):
    print(event)
```

### Continuing Conversations

```python
# The agent automatically maintains conversation history
config = {"configurable": {"thread_id": "conversation-1"}}

# First interaction
await graph.ainvoke({
    "messages": [HumanMessage(content="Create a task called 'Meeting prep'")]
}, config=config)

# Later interaction - agent remembers previous context
await graph.ainvoke({
    "messages": [HumanMessage(content="Update that task's priority to high")]
}, config=config)
```

## Persistence

### In-Memory (Default)

If no `DATABASE_URL` is configured, the agent uses in-memory persistence:

```python
# Conversations persist only during application runtime
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()
```

### PostgreSQL Persistence

Configure PostgreSQL for persistent conversations across application restarts:

1. **Install Dependencies** (already included in pyproject.toml):
   ```bash
   pip install langgraph-checkpoint-postgres psycopg[binary,pool]
   ```

2. **Set Database URL**:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost:5432/nova"
   ```

3. **Setup Database Tables** (automatic on first use):
   ```python
   from langgraph.checkpoint.postgres import PostgresSaver
   checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
   await checkpointer.setup()  # Creates necessary tables
   ```

### Database Schema

The PostgreSQL checkpointer creates these tables:

- `checkpoints`: Stores conversation state snapshots
- `checkpoint_writes`: Stores pending writes for fault tolerance

## Development

### Testing

```python
# Run the built-in test
python -m backend.agent.chat_agent
```

### Adding Tools

Tools are automatically loaded from the `tools` module:

```python
# In tools/__init__.py
def get_all_tools():
    tools = []
    tools.extend(get_task_tools())
    tools.extend(get_person_tools())
    tools.extend(get_project_tools())
    return tools
```

### Custom LLM Configuration

Modify `llm.py` to support additional model providers:

```python
def create_llm(config: Optional[RunnableConfig] = None):
    # Add support for other providers
    provider = config.get("configurable", {}).get("provider", "google")
    
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(...)
    else:
        # Default to Google
        return ChatGoogleGenerativeAI(...)
```

## Best Practices

### Thread Management

- Use consistent `thread_id` values for the same conversation
- Use UUIDs or user-session IDs as thread identifiers
- Different threads maintain separate conversation histories

### Error Handling

```python
try:
    result = await graph.ainvoke(input_data, config=config)
except Exception as e:
    # Handle tool errors, API failures, etc.
    print(f"Agent error: {e}")
```

### Resource Management

For production deployments:

```python
# Use connection pooling for PostgreSQL
from psycopg_pool import AsyncConnectionPool

async with AsyncConnectionPool(
    conninfo=DATABASE_URL,
    max_size=20,
    kwargs=connection_kwargs
) as pool:
    checkpointer = AsyncPostgresSaver(pool)
    graph = create_graph_with_checkpointer(checkpointer)
```

## Troubleshooting

### Common Issues

1. **Missing GOOGLE_API_KEY**: Ensure API key is set in environment
2. **Database Connection**: Verify DATABASE_URL format and database accessibility
3. **Tool Import Errors**: Check that all tool modules are properly installed
4. **Memory Usage**: Consider PostgreSQL persistence for production workloads

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### LangSmith Integration

For debugging and monitoring:

```bash
export LANGCHAIN_TRACING_V2="true"
export LANGCHAIN_API_KEY="your-api-key"
export LANGCHAIN_PROJECT="nova-debugging"
``` 