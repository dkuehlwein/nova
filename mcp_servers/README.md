# MCP Servers

This directory contains independent MCP (Model Context Protocol) Server Applications.
Each server is a self-contained Python application, managed with `uv` and designed to be Dockerized.

## Servers

- `tasks_md_mcp_server/`: Manages interactions with a `tasks.md` file.
- `mem0_mcp_server/`: Wraps the `mem0` service for agent memory.
- `email_mcp_server/`: Handles email functionalities (IMAP/SMTP/API integration).
- `messaging_mcp_server/`: Manages user messaging, potentially triggering WebSocket communications via the backend.

(More servers can be added as needed.)

## General Setup for an MCP Server

1.  Navigate to the specific server directory (e.g., `cd mcp_servers/tasks_md_mcp_server`).
2.  Create a virtual environment using `uv`: `uv venv`
3.  Activate the virtual environment: `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows).
4.  Install dependencies: `uv pip install -r requirements.txt` (or `uv pip sync pyproject.toml`). 