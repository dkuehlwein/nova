# Nova

Nova is an AI assistant for an director in an IT consultancy. 
This is the high-level requirements document for Nova.

# Techstack
## Agent Techstack:
- python 3.13 with uv for venvs and pytest for tests
- langchain/langgraph 
- memory: TO BE DISCUSSED. 
    - Preference for OpenMemory https://mem0.ai/openmemory-mcp but not sure how well it works with langgraph
    - Benefit: Works with Ollama https://github.com/mem0ai/mem0/discussions/2811
    - TO RESEARCH/TEST: How does this work with out Data Structures? Do we need e.g #person seperate, or can we just use OpenMemory?
- fastMCP for mcp servers
- celery for recurrings tasks (loading new mails)


# MCP Servers
- GMail incl Calendar
- Kanban board
- Markitdown for conversions (https://github.com/microsoft/markitdown). This also needs normal API endpoints like the Kanban board

## UI Techstack:
To be defined. Nova should look modern, business and clean with a dark theme and only use well established frameworks.
But we need React for best integration with langchain: https://langchain-ai.github.io/langgraph/cloud/how-tos/use_stream_react/#loading-states

# UI
The UI needs to offer:

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
TO DISCUSS: 
- Do we integrate the frontend from the Kanban MCP server (preferred for keeping things modular) or create a new one (might be better because we need deep integration?)
- We probably need to rewrite the kanban board from scratch - the task.md approach is too simple for the requirements


# Data Structures

## Task
- Unique ID
- Status 
    - ToDo - not yet started. 
    - Doing - currently being worked on. This should only be ONE task -> this will be displayed in the chat overview
    - Blocked - waiting for user feedback/approval
    - Done - finished
  TO DISCUSS: Do we need more lanes? Maybe we want to seperate New tasks (e.g. new e-mail arrived, check it out) vs tasks with new info (e.g. user added a comment to the task, or answered a chat request)
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
- Summary
- TO DISCUSS: Do we need to actual content? I think a summary is enough, the AI could then pull more info if required


# Workflow Examples:

In general, Nova runs in a loop. It picks up the next open task, works on it, closes it or delegates it to the user.
Nova only works on ONE tasks. This is to make sure we don't get racing conditions in the memory.

## New EMail
- New Mail arrives in users inbox
- Celery check_new_mail task finds the the new mail
- New task is created (Read new mail)
    For the task we want to prepare/extract:
    - involved #people
    - related #project, and 
    - attached or linked #artifacts -> This will be done with MarkItDown
- When Nova picks up the task we:
    - Prepare context: pull in info on all related #people, #projects, #chats, #artifacts, current tasks
    - Run the AI/Langgraph with the context and the system prompt
    - Nova decides what to do next, e.g. ask the user a question
    - The task is moved the the new lane (e.g. blocked) and updated (new comment)
    - The memory / database is updated. I.e. related #people, and #projects


## User Feedback
- User answers a chat request 
- The task gets a new comment that summarizes the users answer.
- Related task is moved back to "Todo" (or other name, see discussion above)
