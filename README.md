# Nova AI Assistant

Modular, AI-first assistant for managers.

## Overview

This repository contains the source code for the Nova AI Assistant, a system designed to leverage independently deployable MCP (Model Context Protocol) servers for diverse functionalities, all orchestrated by a core agent. User interaction for tasks is managed via a `tasks.md` application, and chat/document collaboration will explore Open Canvas.

## Project Structure

- `frontend/`: Frontend Application (e.g., React/Vue integrating Open Canvas)
- `backend/`: Nova Backend Core (FastAPI, Celery, `uv`)
- `mcp_servers/`: Independent MCP Server Applications (Python, `uv`, Dockerized)
- `docs/`: Project Documentation (ADRs, guides)
- `infrastructure/`: Deployment configs (Docker Compose, K8s manifests)
- `tests/`: Top-level E2E tests for the whole system
- `scripts/`: Utility scripts
- `memory-bank/`: Project memory and context files.

## Getting Started

(Instructions to be added for setup, `uv` environment initialization, running services, etc.)

## Key Technologies

- Python
- `uv`
- FastAPI
- Celery
- Docker
- `fastmcp`
- Gemini 2.5 Pro
- LangChain / LlamaIndex
- `tasks.md`
- `mem0`
- Open Canvas (Exploratory)