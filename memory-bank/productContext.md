# Nova AI Assistant: Product Context

## Why This Project Exists
To develop a sophisticated, AI-driven assistant specifically designed to aid managers in their daily tasks and decision-making processes. The project emphasizes a modular architecture to ensure flexibility and scalability.

## Problems It Solves
This assistant aims to address common managerial challenges such as:
- Efficient task tracking and management.
- Streamlined communication and collaboration.
- Access to AI-powered insights and automation for routine tasks.
- Reducing cognitive load by centralizing information and tools.

## How It Should Work
- A **Core Agent** (powered by Gemini LLM, using LangChain/LlamaIndex) will be the central brain, orchestrating various functionalities.
- **MCP (Model Context Protocol) Servers** will provide specialized tools and services (e.g., `tasks.md` management, `mem0` for memory, email integration, messaging).
- The **Core Backend** (FastAPI, Celery) will handle API requests, manage asynchronous tasks, and host the Core Agent.
- A **User Interface** will provide a Kanban view for `tasks.md` and a chat/collaboration space (potentially using Open Canvas).
- Communication between the Core Agent and MCP servers will use the `fastmcp` library.

## User Experience Goals
- **Intuitive and Efficient:** Users should find the assistant easy to use and effective in helping them manage their work.
- **Seamless Integration:** The various components (task management, chat, AI assistance) should feel like a cohesive experience.
- **Personalized and Context-Aware:** Leveraging `mem0`, the assistant should remember past interactions and provide contextually relevant support.
- **Reliable and Performant:** The system should be stable and responsive. 