# ADR 012: Hierarchical Agent Architecture for Chat

## Status

Proposed

## Context

### Clarifying the Existing Architecture & Addressing Feedback

A review of the initial version of this ADR raised critical questions about whether this proposal duplicates existing functionality. This feedback was valuable as it prompted a deeper analysis of the codebase, which has confirmed the necessity of this proposal. The core misunderstanding stems from the relationship between the `chat_agent` and the `core_agent`.

**The reviewer asserted that Nova already has a Supervisor/Worker pattern. A code review shows this is incorrect.**

1.  **`chat_agent` and `core_agent` are Independent Peers, Not a Hierarchy:**
    *   The `chat_agent` used by the web UI (`start_website.py`) and the `CoreAgent` in `start_core_agent.py` are two separate services.
    *   The `CoreAgent` is an autonomous loop that pulls tasks from a database. It instantiates its *own* version of the `chat_agent` to process those tasks.
    *   Crucially, there is **no code path** for the user-facing `chat_agent` to delegate tasks to the `CoreAgent`. They are isolated. The user's chat session cannot trigger or interact with the `CoreAgent`'s loop.

2.  **The User-Facing `chat_agent` is a Simple Reactive Agent:**
    *   The agent created in `create_chat_agent` is a standard `create_react_agent`. It can react to a user prompt and use tools, but it has no built-in mechanism for multi-step planning, execution, and verification. It is "monolithic" in the sense that a single chain of thought must accomplish the entire task.

3.  **This Proposal Introduces a *New* Capability:**
    *   This ADR proposes to evolve the user-facing `chat_agent` from a simple reactive agent into a true **Supervisor Agent**. This Supervisor will then delegate steps of its plan to a **Worker Agent** (a new, lightweight graph). This creates the hierarchical control flow that is currently missing.

### The Problem

The current `chat_agent` struggles with complex, multi-step instructions because it lacks a formal planning and execution mechanism. It can lose focus, fail to complete all required steps, and has no way to verify its own work against an initial plan. This leads to unreliable task completion and requires significant user oversight.

The goal is to introduce a robust hierarchical structure **within the chat service** to enable the agent to:
1.  Decompose complex requests into a clear, visible plan (a to-do list).
2.  Execute each step of the plan methodically.
3.  Verify the completion of the entire plan before finishing.

## Decision

We will refactor the `chat_agent` into a **Hierarchical Agent** composed of two primary components: a **Supervisor Agent** and a **Worker Agent**. This hierarchy will exist *within the context of a single user chat session*.

### 1. The Supervisor Agent

The Supervisor will be the main entry point for all user chat requests. Its responsibilities are:

-   **Planning:** Analyze the user's request and generate a structured plan (a to-do list). This plan will be stored in the `AgentState`, which is automatically persisted by Nova's existing PostgreSQL checkpointer.
-   **Delegation:** For each item in the plan, the Supervisor will invoke the Worker Agent *as a tool*. It will pass only the specific context needed for that single task.
-   **State Management:** The Supervisor will maintain the master to-do list within the `AgentState`, tracking the status of each item.
-   **Streaming & Transparency:** The Supervisor will stream its plan to the UI via WebSockets *before* execution. It will then stream updates as each step is completed. This enhances, rather than breaks, our streaming architecture by providing more granular, real-time feedback.
-   **Synthesis:** Once all tasks are complete, the Supervisor will synthesize the results into a final response.

### 2. The Worker Agent

The Worker will be a new, simpler LangGraph instance, compiled into a tool. Its responsibilities are:

-   **Task Execution:** Perform a single, well-defined task using the existing suite of complex tools (MCP, memory, etc.).
-   **Focused Context:** The Worker operates on a minimal state passed down from the Supervisor, preventing it from getting distracted.
-   **Result Reporting:** It returns its result to the Supervisor.

### High-Level Workflow

1.  User submits a complex request.
2.  The `chat_agent` (now the Supervisor) is invoked.
3.  **Supervisor Planner Node:** Creates a to-do list and stores it in the `AgentState`. Streams the plan to the UI.
4.  **Supervisor Control Loop:**
    a. Selects the first pending task.
    b. Invokes the Worker Agent tool with the specific instruction for that task.
5.  **Worker Agent:**
    a. Executes the single task using Nova's full toolset.
    b. Returns the result.
6.  **Supervisor Control Loop:**
    a. Receives the result.
    b. Updates the `AgentState` and streams the progress to the UI.
    c. Loops to the next task until the plan is complete.
7.  **Supervisor Synthesizer Node:** Generates the final answer for the user.

## Consequences

### Positive

-   **Increased Reliability:** Decomposing tasks will dramatically improve the agent's ability to complete complex instructions.
-   **Enhanced Transparency:** The user sees the plan upfront and watches its execution in real-time, improving trust and user experience.
-   **Architecturally Sound:** This implements a standard, best-practice agentic pattern that is currently missing from the chat service.
-   **Leverages Existing Infrastructure:** This design correctly uses the existing `PostgresSaver` for state persistence and `WebSockets` for streaming.

### Negative

-   **Increased Latency:** The planning step adds an upfront LLM call. This is a necessary trade-off for reliability on complex tasks, and the perceived latency will be mitigated by streaming the plan to the user immediately.
-   **Implementation Complexity:** This is a significant and necessary refactoring of the chat agent logic.

## Next Steps

1.  Create a new file `backend/agent/worker_agent.py` to define the worker graph.
2.  Refactor `backend/agent/chat_agent.py` to implement the Supervisor graph logic.
3.  Update the agent creation logic in `create_chat_agent` to build and compile both graphs and make the worker a tool for the supervisor.
4.  Develop tests for the new hierarchical interaction.
