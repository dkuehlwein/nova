# Nova AI Assistant: System Patterns

## System Architecture Diagram

```mermaid
graph TD
    subgraph User Interface (Frontend)
        UI_Kanban[Kanban View (Displays tasks.md content)]
        UI_Chat_Collaborate[Chat & Collaboration (Leveraging Open Canvas - TBD Integration)]
        UI_Kanban -- REST API --> B_API
        UI_Chat_Collaborate -- REST API / WebSockets --> B_API
    end

    subgraph Nova_Backend_Core [Nova Backend Core (Python, FastAPI, Celery, `uv`)]
        B_API[API Gateway (FastAPI)]
        B_Orchestrator[Task Orchestrator (Celery + Redis Container)]
        B_Agent[Core Agent Executor (Gemini LLM, LangChain/LlamaIndex + fastmcp Client)]

        B_API -- Handles HTTP/WS, Enqueues to --> B_Orchestrator
        B_Orchestrator -- Triggers for async tasks (e.g., email polling) --> B_Agent
        B_Agent -- Responds to direct user interactions (via API) & async triggers --> B_API
        B_Agent -- Uses LLM --> Ext_LLM
        B_Agent -- Makes MCP Calls --> MCP_Network
    end

    subgraph MCP_Network [MCP Network (Inter-service communication)]
        %% Simulating network calls to individual MCP servers
        B_Agent --> MCP_TasksMD_Server
        B_Agent --> MCP_Mem0_Server
        B_Agent --> MCP_Email_Server
        B_Agent --> MCP_Messaging_Server
        B_Agent --> MCP_OpenCanvas_Server_Placeholder["MCP_OpenCanvas_Backend_Server (Exploratory)"]
    end

    subgraph MCP_Servers_Independent [Independent MCP Servers (Python, `uv`, Dockerized)]
        MCP_TasksMD_Server["Tasks.md MCP Server<br>(Uses tasks-md library)"]
        MCP_Mem0_Server["Mem0 MCP Server<br>(Wraps Mem0 service/library)"]
        MCP_Email_Server["Email MCP Server<br>(IMAP/SMTP/API integration)"]
        MCP_Messaging_Server["User Messaging MCP Server<br>(Triggers B_API WebSockets)"]
        %% MCP_OpenCanvas_Server_Placeholder -- future, if OpenCanvas backend is wrapped --
    end

    subgraph Data_Stores_External_Services [Data Stores & External Services]
        Data_TasksMD_File["tasks.md file<br>(Managed via Tasks.md library)"]
        Data_Mem0_Storage["Mem0 Service Storage"]
        Data_Redis_Celery["Redis Container<br>(Celery Broker/Results)"]
        Data_Logs["Log Storage<br>(e.g., ELK, Loki, CloudWatch)"]
        Ext_LLM["LLM API (Gemini 2.5 Pro)"]
        Ext_Email_Service["Email Service (IMAP/API)"]
        Ext_OpenCanvas_Service["Open Canvas Service/Assets<br>(Frontend and potentially backend)"]

        MCP_TasksMD_Server -- Interacts with --> Data_TasksMD_File
        MCP_Mem0_Server -- Interacts with --> Data_Mem0_Storage
        B_Orchestrator -- Uses --> Data_Redis_Celery
        %% Logging Service not shown explicitly connected but used by all backend/MCP components
        MCP_Email_Server -- Interacts with --> Ext_Email_Service
        UI_Chat_Collaborate -- Consumes --> Ext_OpenCanvas_Service
    end

    style Nova_Backend_Core fill:#ddeeff,stroke:#333,stroke-width:2px
    style MCP_Servers_Independent fill:#ddffdd,stroke:#333,stroke-width:2px
    style User_Interface fill:#ffffdd,stroke:#333,stroke-width:2px
```

## Key Technical Decisions
- **Primary Language:** Python for backend and MCP server development.
- **API Framework:** FastAPI for REST and WebSocket APIs.
- **Asynchronous Task Processing:** Celery with Redis as a broker/backend.
- **Package Management:** `uv` for Python virtual environments and dependencies.
- **Inter-Service Communication:** `fastmcp` library for communication between the Core Agent and MCP servers.
- **Containerization:** Docker for all backend services and MCP servers.
- **Local Orchestration:** Docker Compose for managing multi-container local development environments.

## Design Patterns
- **Monorepo:** All project code (frontend, backend, MCP servers, docs, etc.) will reside in a single repository.
- **Model-Context-Protocol (MCP):** A pattern for creating modular, tool-like services that can be orchestrated by a core agent. Each MCP server is an independent, deployable unit.
- **Service-Oriented Architecture (SOA) principles:** Applied through the use of independent MCP servers.
- **Agent-Based System:** A central agent orchestrates tasks and tools.

## Component Relationships
- The **Frontend** interacts with the **Nova Backend Core** via REST APIs and WebSockets.
- The **Nova Backend Core** (specifically the API Gateway) receives requests and can enqueue tasks to the **Task Orchestrator (Celery)**.
- The **Task Orchestrator** triggers the **Core Agent Executor** for asynchronous operations.
- The **Core Agent Executor** interacts directly with an **LLM (Gemini 2.5 Pro)** and makes calls to various **MCP Servers** via the **MCP Network** (using `fastmcp`).
- Each **MCP Server** is an independent application, potentially interacting with external data stores or services (e.g., `tasks.md` file, Mem0 service, email services).

## Critical Implementation Paths
1.  **Backend Core Setup:** Establishing the FastAPI application, Celery integration, and basic Core Agent structure.
2.  **MCP Server Framework:** Defining a template/standard for creating new MCP servers using `fastmcp`.
3.  **First MCP Server Implementation:** Developing the `Tasks.md MCP Server` as an initial proof-of-concept for the MCP architecture.
4.  **Agent-MCP Integration:** Ensuring the Core Agent can successfully communicate with and utilize MCP servers.
5.  **Frontend Integration:** Connecting the frontend UI (Kanban, Chat) to the backend API endpoints. 