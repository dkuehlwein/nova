# Nova - AI-Powered Kanban Task Manager

Nova is an intelligent kanban-style task management system that integrates with LangChain AI agents to provide autonomous task processing and human-in-the-loop capabilities.

## 🚀 Quick Start

1. **Install Dependencies & Start Services**
   ```bash
   cd nova
   # Start backend dependencies
   docker-compose up -d postgres redis
   
   # Install frontend dependencies
   cd frontend && npm install && cd ..
   
   # Install backend dependencies  
   cd backend && uv sync && cd ..
   ```

2. **Configure Environment**
   Create a `.env` file in the root directory:
   ```env
   # Required: Google AI API Key
   GOOGLE_API_KEY=your_google_api_key_here
   
   # Optional: LangSmith tracing
   LANGCHAIN_API_KEY=your_langsmith_api_key
   LANGCHAIN_PROJECT=nova-development
   
   # Development Logging (set to false for readable console output)
   LOG_JSON=false
   LOG_LEVEL=INFO
   
   # Other optional settings
   ```

3. **Start Nova Services**
   ```bash
   # Terminal 1: Start backend (chat agent + API)
   cd backend && uv run python start_website.py
   
   # Terminal 2: Start core agent (autonomous task processor)
   cd backend && uv run python start_core_agent.py
   
   # Terminal 3: Start frontend
   cd frontend && npm run dev
   ```

4. **Access Nova**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Core Agent: http://localhost:8001

## 📋 Development Configuration

### Logging Configuration
Nova supports both human-readable console output and structured JSON logging:

- **Development**: Set `LOG_JSON=false` for readable console output
- **Production**: Set `LOG_JSON=true` for structured JSON logs
- **Log Level**: Set `LOG_LEVEL` to DEBUG, INFO, WARNING, ERROR, or CRITICAL

### Database Configuration
- **Development**: Uses in-memory checkpointer by default
- **Production**: PostgreSQL checkpointer is required

## 🛠️ Architecture

Nova consists of three main components:

1. **Frontend** (Next.js): Web interface for task management and chat
2. **Chat Agent Service** (FastAPI): Handles web requests and interactive chat
3. **Core Agent Service** (FastAPI): Autonomous task processing loop

## 📖 Documentation

- [High-Level Architecture](docs/high-level-outline.md)
- [Human-in-the-Loop Design](docs/human-in-the-loop-architecture.md)
- [Settings Implementation](docs/settings_realization_work_packages.md)
- [Docker Setup Guide](docs/docker-setup.md)

## 🧪 Testing

```bash
# Backend tests
cd backend && uv run pytest ../tests

# Frontend tests (when available)
cd frontend && npm test
```

## 🤝 Contributing

Nova follows clean architecture principles with clear separation of concerns. See the architecture documentation for detailed information about the codebase structure and patterns.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.