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

We will implement a **Dynamic Skill Loading System**, leveraging LangGraph's [Dynamic Tool Calling](https://langchain-ai.github.io/langgraph/how-tos/many-tools/) pattern for per-turn tool binding.

### 1. Skill Definition

A "Skill" is a directory in `backend/skills/` containing:

```
backend/skills/<skill_name>/
├── manifest.yaml      # Metadata (name, description, version)
├── instructions.md    # Detailed SOPs/Workflows (loaded on demand)
├── tools.py          # Specialized tools (loaded on demand)
└── config.yaml       # Optional skill-specific configuration
```

**Manifest Schema:**
```yaml
name: employee_onboarding
version: "1.0.0"
description: "Handle new hire setup, emails, and checklists."  # LLM "advertisement"
author: nova-team
tags: [hr, onboarding, workflow]
```

### 2. Agent State Schema

We extend the agent state to track active skills explicitly:

```python
from typing import TypedDict, Annotated
from langgraph.graph import add_messages

class SkillActivation(TypedDict):
    """Metadata for an active skill."""
    activated_at_turn: int      # Turn number when activated
    tools: list[str]            # Tool names provided by this skill

class SkillAwareAgentState(TypedDict):
    """Extended agent state with skill tracking."""
    messages: Annotated[list, add_messages]
    active_skills: dict[str, SkillActivation]  # skill_name -> activation metadata
```

### 3. The "Skill Registry" & Base State

The `SkillManager` maintains a lightweight registry of all available skills (Name + Description only).

**Base Agent State:**
- The agent runs *without* any specific skill loaded by default
- Always has access to `enable_skill` and `disable_skill` tools
- System prompt includes dynamic skill listing

**System Prompt Addition:**

The base system prompt template will include a dynamic section populated at runtime:

```text
## Available Skills
The following specialized skills are available. If a user request matches
one of these domains, use the `enable_skill` tool to load it.

{available_skills}
```

Where `{available_skills}` is populated by `SkillManager.get_skill_summaries()`, rendering as (example):

```text
- employee_onboarding: Handle new hire setup, emails, and checklists.
- release_management: Manage git versioning, changelogs, and deployments.
- research_assistant: Deep search and report generation capabilities.
```

If no skills are installed, this section is omitted from the prompt entirely.

### 4. Dynamic Activation Flow

1. **Discovery**: User asks "Help me onboard John Doe". The Agent sees `employee_onboarding` in its "Available Skills" list.

2. **Activation**: Agent calls `enable_skill(skill_name="employee_onboarding")`.

3. **State Update**: The `enable_skill` tool:
    - Loads skill instructions and tools via `SkillManager`
    - Updates `state["active_skills"]` with the new skill
    - Returns instructions as tool output (natural conversation flow)

4. **Dynamic Tool Binding**: On the next LLM invocation, the agent node:
    - Reads `state["active_skills"]`
    - Binds base tools + active skill tools via `llm.bind_tools()`

5. **Execution**: The Agent now has the knowledge (instructions in context) and power (tools bound) to execute the workflow.

6. **Deactivation**: Via `disable_skill(skill_name)` or automatic (new conversation).

### 5. Technical Implementation

#### 5.1 SkillManager (`backend/utils/skill_manager.py`)

Follows Nova's `BaseConfigManager` pattern for ConfigRegistry integration:

```python
from utils.config_registry import BaseConfigManager

class SkillManager(BaseConfigManager):
    """Manages skill discovery and loading with hot-reload support."""

    def __init__(self, skills_path: Path):
        self.skills_path = skills_path
        self._registry: dict[str, SkillManifest] = {}
        self._scan_skills()

    def get_skill_summaries(self) -> dict[str, str]:
        """Return name -> description for system prompt injection."""
        return {name: info.description for name, info in self._registry.items()}

    async def load_skill(self, name: str) -> SkillDefinition:
        """Load full skill definition (instructions + tools)."""
        if name not in self._registry:
            raise SkillNotFoundError(f"Unknown skill: {name}")

        skill_path = self.skills_path / name
        manifest = self._registry[name]
        instructions = (skill_path / "instructions.md").read_text()
        tools = await self._import_tools(skill_path / "tools.py")

        return SkillDefinition(
            manifest=manifest,
            instructions=instructions,
            tools=tools
        )

    async def get_skill_tools(self, name: str) -> list[BaseTool]:
        """Get tools for a specific skill, wrapped for approval."""
        skill = await self.load_skill(name)
        # Namespace tools to avoid conflicts: skill_name__tool_name
        namespaced = self._namespace_tools(name, skill.tools)
        return wrap_tools_for_approval(namespaced)
```

**ConfigRegistry Integration:**
```python
# In config_registry.initialize_standard_configs()
skill_manager = SkillManager(skills_path=Path("backend/skills"))
config_registry.register("skills", skill_manager)
```

#### 5.2 Custom LangGraph Agent (`backend/agent/chat_agent.py`)

Replace `create_react_agent` with custom `StateGraph` for dynamic tool binding:

```python
from langgraph.graph import StateGraph, START, END

def create_skill_aware_agent(checkpointer, skill_manager: SkillManager):
    """Create agent with dynamic tool binding support."""

    # Tool registries
    base_tools = get_base_tools()  # Always available
    skill_tools_cache = {}  # Loaded on demand

    async def agent_node(state: SkillAwareAgentState):
        """LLM node with per-turn tool binding."""
        # Collect active skill tools
        active_tools = list(base_tools)
        for skill_name in state.get("active_skills", {}):
            if skill_name not in skill_tools_cache:
                skill_tools_cache[skill_name] = await skill_manager.get_skill_tools(skill_name)
            active_tools.extend(skill_tools_cache[skill_name])

        # Bind tools for this turn
        llm_with_tools = llm.bind_tools(active_tools)
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    async def tool_node(state: SkillAwareAgentState):
        """Execute tool calls, handling skill activation specially."""
        # ... tool execution logic
        # If enable_skill called, update state["active_skills"]
        pass

    # Build graph
    graph = StateGraph(SkillAwareAgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)
```

#### 5.3 Skill Tools (`backend/tools/skill_tools.py`)

```python
@tool
async def enable_skill(skill_name: str) -> str:
    """
    Activate a specialized skill to gain domain-specific tools and knowledge.

    Use this when a user request matches one of the available skills listed
    in your system prompt. The skill's instructions and tools will become
    available for subsequent turns.

    Args:
        skill_name: Name of the skill to activate (e.g., "employee_onboarding")

    Returns:
        Skill instructions and list of newly available tools
    """
    from utils.config_registry import config_registry
    skill_manager = config_registry.get("skills")

    try:
        skill = await skill_manager.load_skill(skill_name)
    except SkillNotFoundError:
        available = list(skill_manager.get_skill_summaries().keys())
        return f"Unknown skill '{skill_name}'. Available: {', '.join(available)}"

    # Return instructions as tool output (appears naturally in conversation)
    tool_names = [t.name for t in skill.tools]
    return f"""## Skill Activated: {skill.manifest.name} v{skill.manifest.version}

{skill.instructions}

**New tools available:** {', '.join(tool_names)}

You now have the knowledge and tools to proceed with this workflow.
"""


@tool
async def disable_skill(skill_name: str) -> str:
    """
    Deactivate a skill, removing its tools from availability.

    Args:
        skill_name: Name of the skill to deactivate

    Returns:
        Confirmation message
    """
    # State update handled by tool_node
    return f"Skill '{skill_name}' deactivated. Its tools are no longer available."
```

### 6. Skill Lifecycle

| Phase | Trigger | State Change |
|-------|---------|--------------|
| **Inactive** | Default state | `active_skills = {}` |
| **Activation** | `enable_skill(name)` called | `active_skills[name] = {activated_at, tools}` |
| **Active** | Skill in `active_skills` | Tools bound on each LLM turn |
| **Deactivation** | `disable_skill(name)` called | `del active_skills[name]` |
| **Reset** | New conversation | `active_skills = {}` (fresh state) |

**Optional Auto-Deactivation:** Skills could auto-deactivate after N turns without using their tools (future enhancement).

### 7. Error Handling

| Error | Handling |
|-------|----------|
| Unknown skill name | Return available skills list |
| Skill load failure (bad manifest/tools) | Log error, return graceful message, skip skill |
| Tool name conflict | Namespace as `{skill_name}__{tool_name}` |
| Multiple skills active | All tools merged, no conflict due to namespacing |

### 8. Frontend Implications

#### Skills Library UI (`/settings/skills`)
- **List View**: Cards showing Skill Name, Description, and Version
- **Status**: Indicators for "Installed" (available on disk)
- **Controls**: (Future) Ability to "pin" skills to be always active, or disable specific skills from being discovered

#### Chat Interface
- **Activation Indicator**: When the agent calls `enable_skill`, render a distinct "Skill Badge" so the user knows the agent has switched context
- **Skill Status**: Current active skills visible in side panel or expandable header

### 9. Compliance & Integration

#### Tool Permission Compliance (ADR-013)
Dynamically loaded tools must NOT bypass the security model:
- Skill tools are wrapped via `wrap_tools_for_approval()` during loading
- Default: Skill tools require **Human Approval** unless explicitly whitelisted
- Pattern matching supports skill namespacing: `employee_onboarding__send_email(*)`

```yaml
# configs/tool_permissions.yaml
permissions:
  allow:
    - search_memory                    # Base tool, always allowed
    - "employee_onboarding__*"         # All tools in this skill allowed
  deny:
    - "*__delete_*"                    # No delete tools from any skill
  human_approval:
    - "release_management__deploy_*"   # Deployments need approval
```

#### Configuration & Secrets (ADR-004)
- **Secrets**: MUST NOT be stored in skill directory. Load from Environment Variables or `secrets.yaml`
- **Skill Config**: Optional `skills/<name>/config.yaml` for skill-specific defaults, overrideable by standard Configuration System

#### ConfigRegistry Integration (ADR-004, ADR-005)
- `SkillManager` registered with ConfigRegistry at startup
- Hot-reload support via file watchers (same pattern as MCP servers, prompts)
- Skill changes detected and registry refreshed automatically

## Consequences

### Positive
- **Token Efficiency**: Heavy instructions and specialized tools only in context when active
- **Scalability**: 100+ skills possible; agent only pays cost of short descriptions until activated
- **Focus**: Active skill puts agent "in the zone" for that specific workflow
- **Security**: Skill tools go through same approval pipeline as base tools
- **Extensibility**: New skills added by creating directory, no code changes needed

### Negative
- **Graph Complexity**: Custom LangGraph graph instead of `create_react_agent`
- **State Overhead**: `active_skills` tracking adds to state size (minimal)
- **Latency**: Skill loading adds slight overhead on first activation (negligible for local files)

## Implementation Roadmap

### Phase 1: Infrastructure
1. Create `backend/skills/` directory structure
2. Implement `SkillManager` following `BaseConfigManager` pattern
3. Register with ConfigRegistry, add hot-reload support
4. Create skill manifest schema and validation

### Phase 2: Custom Graph
1. Define `SkillAwareAgentState` with `active_skills` field
2. Replace `create_react_agent` with custom `StateGraph`
3. Implement dynamic `bind_tools()` in agent node
4. Update tool node to handle skill state updates

### Phase 3: Skill Tools
1. Implement `enable_skill` tool with instruction return
2. Implement `disable_skill` tool
3. Update system prompt template with `{available_skills}` variable
4. Add tool namespacing to avoid conflicts

### Phase 4: Integration & Security
1. Integrate skill tools with `ToolPermissionsManager`
2. Add skill tool patterns to permissions config
3. Update `get_all_tools()` to include skill management tools
4. Test permission flows with skill tools

### Phase 5: Testing & Validation
1. Create example skills (`employee_onboarding`, `test_skill`)
2. Unit tests for `SkillManager`
3. Integration tests for skill activation/deactivation
4. Test multi-skill scenarios
5. Test hot-reload behavior

### Phase 6: Frontend & Observability
1. Add "Available Skills" API endpoint
2. Skills settings page (`/settings/skills`)
3. Chat UI skill activation indicators
4. Health monitor skill usage tracking

## References

- [LangGraph Dynamic Tool Calling](https://langchain-ai.github.io/langgraph/how-tos/many-tools/)
- [Claude Code Skills Architecture](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview)
- [ADR-004: Configuration Management](./004-configuration-management.md)
- [ADR-013: Tool Approval System](./013-tool-approval-system.md)
