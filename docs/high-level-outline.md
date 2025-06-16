# Nova

Nova is an AI assistant for an director in an IT consultancy. 
This is the high-level requirements document for Nova.

# Project Structure

Nova follows a clean, function-based architecture with clear separation of concerns:

```
nova/
├── backend/                    # Core Nova agent and business logic
│   ├── api/                   # REST endpoints for frontend
│   ├── tools/                 # Tools for agent
│   ├── agent/                # Agent logic
│   ├── models/                # Database schemas and data models
│   ├── database/              # Database management and connections
│   └── main.py               # Backend (APIs + Agent) entry point
├── tests/                     # Integration tests and sample data
│   ├── test_mcp_connection.py # MCP protocol tests
│   ├── test_sample_data.py   # Sample data generation
│   └── README.md             # Testing documentation
├── frontend/                  # Nova main UI (Next.js)
├── mcp_servers/              # Independent MCP servers
│   ├── gmail/                # Gmail MCP server
│   └── ...                   # Future MCP servers
```

# Techstack
## Agent Techstack:
- python 3.13 with uv for venvs and pytest for tests
- langchain/langgraph 
- memory: OpenMemory MCP for contextual memory (#person, #project relationships). Separate from kanban task management.
    - Preference for OpenMemory https://mem0.ai/openmemory-mcp 
    - Benefit: Works with Ollama https://github.com/mem0ai/mem0/discussions/2811
- fastMCP for mcp servers
- celery for recurring tasks (loading new mails → creating tasks, NOT triggering agent actions)


# MCP Servers
- GMail incl Calendar
- Markitdown for conversions (https://github.com/microsoft/markitdown). This also needs normal API endpoints like the Kanban board

## UI Techstack:
- **Framework**: Next.js 15.1 + React 19 + TypeScript 5.x
- **UI/Styling**: Tailwind CSS + shadcn/ui (business/clean + dark theme) + Lucide React
- **State Management**: React built-in + API state management (deferred until needed)
- **HTTP Layer**: Direct fetch() API to MCP servers
- **Integration**: Direct connection to MCP server `/api/` endpoints (no proxy needed)

Nova should look modern, business and clean with a dark theme and only use well established frameworks.
React 19 is required for best integration with langchain: https://langchain-ai.github.io/langgraph/cloud/how-tos/use_stream_react/#loading-states

# UI
Nova needs a unified frontend (nova/frontend/) that provides Nova-specific features with fully integrated components.

## A quick overview of the current state. 
- # of open tasks (on click, linked to kanban lane)
- # of blocked tasks (on click, linked to kanban lane)
- Current Task that Nova is working on (Task title, on click link to task)

## Settings
- Which MCP servers are integrated. On-Off buttons for integrations
- Which LLM is used
- Show and potentially edit the system prompt of Nova
- Show and potentially edit the celery jobs (how often to check for new mails, other messages)

## Chat
The chat interface needs to show all human feedback requests (i.e. Nova sends a message to the user) and allow the user to send a new message to Nova.
It shows old chats and the user can click on old chats to continue the conversation.
Examples: 
- https://github.com/langchain-ai/agent-chat-ui
- https://github.com/langchain-ai/agent-inbox?tab=readme-ov-file 
A canvas to show e.g. e-mail drafts would be nice, but not for the first iteration.

## Kanban board
The Kanban board shows all tasks, the lane, status, and all related info (comments, project, chats, etc). The user can add new comments. Adding a new comment will put the task back in "Todo"

**Integration**: Fully integrated Nova component using kanban MCP API endpoints. This provides:
- Consistent architecture with chat component
- Seamless UX with shared state and theming  
- Single codebase maintenance
- Direct API integration without embedding complexity

The kanban MCP server continues to provide both `/mcp/` endpoints (for agent) and `/api/` endpoints (for frontend).


# Data Structures

## Task
- Unique ID
- Status 
    - New: For brand new tasks (e.g., new email).
    - User Input Received: Tasks where the user has provided feedback and are ready for Nova to continue.
    - Needs Review: Tasks processed by Nova that require user attention (e.g., a summary of an email, a question).
    - Waiting: Waiting for external factors e.g. e-mail reply from another person
    - In Progress: Actively being worked on by Nova.
    - Done.
    - Failed: In case anything goes wrong
- Title (short, descriptive, will be shown in the UI overview)
- Description (the inital task)
- Comments (potentially multiple follow-up comments/notes while we work on it)
- Summary (summarizing the initial description and all the comments)
- related #persons, #projects, #chats and #artifacts (e-mails, sharepoint links to powerpoints, etc)


## Person
- Unique ID
- Name
- E-Mail
- Role (e.g. Sales lead for the public sector)
- Description (What we know about them and our history with them)
- Current focus (What we are currently working on together, this needs to contain dates)
- related #projects

## Projects
- Unique ID
- Name
- Client (can also be internal)
- Booking Code (on which account the efforts on this project will be billed)
- Summary (What is this project about)
- related #people and their role in the project, #tasks, #chats and #artifacts

## Chat
- Unique ID
- messages in the chat (use langchain/langgraph!)
- related #person (multiple), #project (should be one, but may be multiple) and #task (should be one, but may be multiple)

## Artifact
- Unique ID
- Type (E-Mail, Link, PDF, ...)
- Link
- Summary (We will only store the summary for now. The AI can pull more info via the MarkItDown MCP if required.)



# Workflow Examples:

In general, Nova runs in a loop. It picks up the next open task, works on it, closes it or delegates it to the user.
Nova only works on ONE tasks. This is to make sure we don't get racing conditions in the memory.

## New EMail
- New Mail arrives in users inbox
- Celery check_new_mail job finds the new mail
- New task is created in kanban (Read new mail)
    For the task we want to prepare/extract:
    - involved #people (email addresses → easy identification)
    - related #project (content analysis + OpenMemory context + potential project ID from Nova)
    - attached or linked #artifacts -> This will be done with MarkItDown MCP + API endpoints
- When Nova picks up the task in her main loop:
    - Prepare context: pull info from OpenMemory (#people, #projects), kanban board (current task, #chats and #artifacts that are related to the task), and project DB
    - Run the AI/Langgraph with the context and the system prompt
    - Nova decides what to do next, e.g. ask the user a question
    - The task is moved to the new lane (e.g. "Waiting") and updated (new comment)
    - The memory/context of #people and #projects is updated in OpenMemory and potentially the project DB

## User Feedback
- User answers a chat request 
- The task gets a new comment that summarizes the users answer.
- Related task is moved back to "User Input Received"
- Nova picks it up in next loop iteration


# Error Handling and Resilience
Tasks will go to the "Failed" lane if things go wrong.

# Security and Authentication
The app will run locally. We use a .env file for configuration. Nova will always be single-user.
