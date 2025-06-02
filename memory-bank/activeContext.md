# Nova AI Assistant: Active Context

## 🎯 **CURRENT FOCUS: PHASE 1 FRONTEND SETUP** ⭐

### **Frontend Stack Finalized** ✅
- **Core**: Next.js 15.1 + React 19 + TypeScript 5.x
- **UI**: Tailwind CSS + shadcn/ui (business/clean + dark theme) + Lucide React
- **State**: React built-in state + API state management (TBD: SWR/TanStack when needed)
- **Real-time**: Simple polling for overview dashboard
- **API**: Direct fetch() to MCP server `/api/` endpoints (no proxy needed)

### **Architecture Decisions Finalized** ✅
**API Integration Pattern:**
- **Direct Connection**: `localhost:8001/api/cards`, `localhost:8002/api/messages`
- **No Proxy Needed**: Frontend connects directly to MCP server `/api/` endpoints
- **MCP Protocol**: Agent uses `/mcp/` endpoints, frontend uses `/api/` endpoints

**UI Integration Strategy:**
- **✅ Chat Component**: Fully integrated Nova component with direct LangGraph communication  
- **✅ Kanban Component**: Fully integrated Nova component using kanban MCP API endpoints
- **Benefits**: Consistent architecture, seamless UX, shared state, unified theming, single codebase

### **🚀 IMMEDIATE NEXT STEPS**

#### **1. Frontend Project Setup** 🎯
**Priority**: Highest - Establish foundation
- **Create**: `nova/frontend/` with Next.js 15.1 + TypeScript + Tailwind + shadcn/ui
- **Setup**: Project structure with Overview, Chat, KanbanBoard, Settings components
- **Goal**: Hello world unified interface with modern tech stack

#### **2. Design System Implementation** 🎨
**After Setup**: Establish visual foundation
- **Implement**: Dark theme business/clean design with shadcn/ui
- **Create**: Component library and design tokens
- **Goal**: Professional, modern interface ready for component development

#### **3. Direct MCP Integration** 🔌
**After Design**: Connect to existing MCP servers
- **Connect**: Direct fetch() to `localhost:8001/api/` and `localhost:8002/api/`
- **Test**: Integration with existing kanban MCP (10 tools operational)
- **Goal**: Unified frontend communicating with MCP services directly

#### **4. Fully Integrated Components** 🤖
**After MCP Integration**: Complete component integration
- **Implement**: Fully integrated Chat and KanbanBoard components
- **Goal**: Complete Nova orchestration with seamless user experience

## 📋 **CONFIRMED ARCHITECTURAL DECISIONS**

### **Frontend Structure** 🖥️
```
nova/frontend/
├── app/                    # Next.js 15.1 App Router
│   ├── page.tsx           # Overview dashboard (task counts, agent status)
│   ├── chat/page.tsx      # Fully integrated agent communication
│   ├── kanban/page.tsx    # Fully integrated task management
│   ├── settings/page.tsx  # System configuration
│   └── api/               # Optional internal API routes
├── components/
│   ├── ui/                # shadcn/ui components
│   ├── Overview.tsx       # Quick overview dashboard
│   ├── Chat.tsx          # Fully integrated agent interface
│   ├── KanbanBoard.tsx   # Fully integrated task management
│   ├── TaskCard.tsx      # Reusable task components
│   ├── Settings.tsx      # Configuration panel
│   └── shared/           # Shared UI components
├── hooks/
│   ├── useTasks.ts       # Kanban API integration
│   ├── useAgentStatus.ts # Agent status and communication
│   └── useNovaConfig.ts  # Configuration management
├── lib/
│   └── api.ts            # Direct MCP server API client
└── styles/
    └── globals.css       # Tailwind + dark theme
```

### **API Integration Pattern** 🔗
```typescript
// Direct MCP server communication (no proxy)
// lib/api.ts
export async function getTasks() {
  const response = await fetch('http://localhost:8001/api/cards');
  return response.json();
}

export async function getEmails() {
  const response = await fetch('http://localhost:8002/api/messages');
  return response.json();
}

export async function getTaskCounts() {
  const response = await fetch('http://localhost:8001/api/stats');
  return response.json();
}

// MCP Server Structure (existing):
// localhost:8001/mcp/  → LangGraph/agent communication  
// localhost:8001/api/  → Frontend REST API
// localhost:8001/health → Health check
```

### **Technology Decisions** ⚙️
- **Framework**: Next.js 15.1 (latest stable, Dec 2024) with App Router
- **React**: React 19 (stable) - required for LangGraph integration
- **Styling**: Tailwind CSS + shadcn/ui (business theme + dark mode)
- **HTTP**: Direct fetch() to MCP server `/api/` endpoints
- **State Management**: Deferred until needed (React built-in sufficient for now)
- **UI Integration**: ✅ Fully integrated components (Chat + Kanban)

## 🎉 **STABLE FOUNDATION** ✅

### **Production Ready Infrastructure**
- **37 Tools**: Gmail MCP (27) + Kanban MCP (10) fully operational
- **MCP Endpoints**: Each server exposes `/mcp/` (protocol) + `/api/` (REST) + `/health`
- **Agent Platform**: LangGraph + Gemini 2.5 Pro with continuous operation
- **Docker Environment**: Complete orchestration with health monitoring
- **Testing**: Comprehensive pytest suite

### **Clear Next Steps Path**
1. **Setup** → Frontend project with hello-world page
2. **Design** → Implement design system and component library
3. **Connect** → Direct MCP server integration via `/api/` endpoints
4. **Integrate** → Fully integrated Chat and KanbanBoard components

**Status**: ✅ **FRONTEND ARCHITECTURE UNIFIED, READY FOR IMPLEMENTATION**