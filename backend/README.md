# Nova Backend Core

This directory contains the backend services for the Nova AI Assistant, including:
- API Gateway (FastAPI)
- Task Orchestrator (Celery)
- Core Agent Executor

## Setup

1.  Navigate to this directory: `cd backend`
2.  Create a virtual environment using `uv`: `uv venv`
3.  Activate the virtual environment: `source .venv/bin/activate` (on Linux/macOS) or `.venv\Scripts\activate` (on Windows)
4.  Install dependencies: `uv pip install -r requirements.txt` (or `uv pip sync pyproject.toml` if all dependencies are listed there)

(More details to be added) 