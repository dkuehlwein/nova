# ADR-014: Dynamic Pluggable Skills System ("Workflows")

## Status
Proposed

## Date
2026-01-01

## Context

Nova currently operates with a static set of tools. As we add more complex workflows (e.g., "Employee Onboarding", "Release Management"), adding all these instructions and tools to the global context would overwhelm the system prompt and consume unnecessary tokens.

We need a system where the agent is aware of *available* capabilities (Skills) but only loads the heavy instructions and specialized tools when specifically needed for the task at hand. This "On-Demand" approach optimizes context usage and allows for a scalable library of skills.

This approach aligns with the **"Progressive Disclosure"** architecture used by Anthropic's [Claude Code CLI](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview), where skills are filesystem-based resources loaded dynamically to transform the general-purpose agent into a domain specialist.

## Decision

We will implement a **Dynamic Skill Loading System**, mirroring the best practices established by the Claude Code architecture.

### 1. Skill Definition
A "Skill" remains a directory in `backend/skills/` containing:
-   `manifest.yaml`: Metadata (name, description, version). **Crucial**: The `description` here acts as the "advertisement" to the LLM.
-   `instructions.md`: Detailed SOPs/Workflows (only loaded on demand).
-   `tools.py`: Specialized tools (only loaded on demand).

### 2. The "Skill Registry" & Base State
The `SkillManager` will maintain a lightweight registry of all available skills (Name + Description).

**Base Agent State:**
The Core Agent (and Chat Agent) will generally run *without* any specific skill loaded.
However, it will always have access to a **`enable_skill`** tool.

**System Prompt Addition:**
The base system prompt will include a dynamic section listing available skills:
```text
## Available Skills
The following specialized skills are available to you. If a user request matches one of these domains, use the `enable_skill` tool to load it.

- employee_onboarding: Handle new hire setup, emails, and checklists.
- release_management: Manage git versioning, changelogs, and deployments.
- research_assistant: Deep search and report generation capabilities.
...
```

### 3. Dynamic Activation Flow
1.  **Discovery**: User asks "Help me onboard John Doe". The Agent sees `employee_onboarding` in its "Available Skills" list.
2.  **Activation**: Agent calls `enable_skill(skill_name="employee_onboarding")`.
3.  **State Mutation**:
    -   The `enable_skill` tool functionality (handled by the LangGraph node) does NOT just return text.
    -   It triggers a **state update** in the LangGraph agent:
        -   **Instructions**: The content of `skills/employee_onboarding/instructions.md` is appended to the conversation history (as a System Message or a high-priority Tool Output).
        -   **Tools**: The tools defined in `skills/employee_onboarding/tools.py` are *merged* into the list of available tools for subsequent turns.
4.  **Execution**: The Agent now has the knowledge (SOP) and the power (Tools) to execute the workflow.
5.  **Deactivation (Optional)**: A `disable_skill` tool could unload them, or they persist until the task is marked done.

### 4. Technical Implementation Changes

#### `backend/utils/skill_manager.py`
-   Scans `backend/skills/`.
-   Provides `get_skill_summaries()` for the system prompt.
-   Provides `load_skill_context(name)` which returns the tool definitions and instruction text.

#### `backend/agent/chat_agent.py` & LangGraph
-   We need to move away from hardcoded `tools=[...]` in the `create_react_agent`.
-   We will likely need to use `bind_tools` dynamically in the graph node loop, or update the `state["tools"]` if we implement a custom graph.
-   **Refined Plan**: We will wrap the model node. Before calling the model, we check `state.get("active_skills")` and bind the corresponding tools to the model instance for that turn.

### 5. Frontend Implications

To support this system, the Frontend (`nova/frontend`) requires updates:

#### Skills Library UI (`/settings/skills`)
A new settings page to view the "Registry" of available skills.
-   **List View**: Cards showing Skill Name, Description, and Version.
-   **Status**: Indicators for "Installed" (available on disk).
-   **Controls**: (Future) Ability to "pin" skills to be always active, or disable specific skills from being discovered.

#### Chat Interface
-   **Activation Indicator**: When the agent calls `enable_skill`, the UI should render a distinct "System Event" or "Skill Badge" (e.g., "🛠️ **Skill Activated**: Employee Onboarding") so the user knows the agent has switched context.
-   **Skill Status**: The current active skills for the conversation should be visible, perhaps in the side panel or expandable header.

### 6. Compliance & Integration

#### Tool Permission Compliance (ADR-013)
Dynamically loaded tools must NOT bypass the security model.
-   The `SkillManager` must register loaded tools with the `ToolPermissionsManager`.
-   If a skill introduces a sensitive tool (e.g., `delete_database`), it defaults to requiring **Human Approval** unless explicitly whitelisted in `configs/tool_permissions.yaml`.

#### Configuration & Secrets (ADR-004)
Skills often require API keys or configuration.
-   **Secrets**: MUST NOT be stored in the skill directory. They should be loaded from Environment Variables (Tier 2A) or `secrets.yaml`.
-   **Defaults**: Skill-specific defaults can live in `skills/<name>/config.yaml`, but must be overrideable by the standard Configuration System.

## Consequences

### Positive
-   **Token Efficiency**: Heavy instructions and specialized tools are only in context when active.
-   **Scalability**: We can have 100 skills; the agent only pays the cost of 100 short descriptions until one is picked.
-   **Focus**: When a skill is active, the agent is "in the zone" for that specific workflow.

### Negative
-   **Graph Complexity**: Requires a more complex LangGraph setup (dynamic tool binding) than the standard `create_react_agent`.
-   **Latency**: Loading a skill might add a slight overhead (negligible for local files).

## Implementation Roadmap
1.  Implement `SkillManager` to read manifests.
2.  Create the `enable_skill` tool.
3.  Refactor `CoreAgent` / `ChatAgent` to support dynamic tool lists (likely need to customize the graph definition).
4.  Test with a dummy skill.
