import { Activity, Brain, KanbanSquare, Settings, Users } from "lucide-react";

export default function Nova() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="flex h-16 items-center px-6">
          <div className="flex items-center space-x-2">
            <Brain className="h-8 w-8 text-primary" />
            <h1 className="text-2xl font-bold text-foreground">Nova</h1>
          </div>
          <div className="ml-auto flex items-center space-x-4">
            <div className="flex items-center space-x-2 text-sm text-muted-foreground">
              <Activity className="h-4 w-4" />
              <span>Agent Status: Operational</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6">
        <div className="mx-auto max-w-7xl">
          {/* Welcome Section */}
          <div className="mb-8">
            <h2 className="text-3xl font-bold text-foreground mb-2">
              Welcome to Nova AI Assistant
            </h2>
            <p className="text-muted-foreground text-lg">
              Your AI-powered assistant for IT consultancy management
            </p>
          </div>

          {/* Quick Overview Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-2">
                <KanbanSquare className="h-5 w-5 text-primary" />
                <h3 className="font-semibold text-foreground">Open Tasks</h3>
              </div>
              <p className="text-2xl font-bold text-foreground">12</p>
              <p className="text-sm text-muted-foreground">Ready for processing</p>
            </div>

            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-2">
                <Users className="h-5 w-5 text-primary" />
                <h3 className="font-semibold text-foreground">Blocked Tasks</h3>
              </div>
              <p className="text-2xl font-bold text-foreground">3</p>
              <p className="text-sm text-muted-foreground">Awaiting user input</p>
            </div>

            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-2">
                <Brain className="h-5 w-5 text-primary" />
                <h3 className="font-semibold text-foreground">Current Task</h3>
              </div>
              <p className="text-sm font-medium text-foreground">Process email from John Smith</p>
              <p className="text-sm text-muted-foreground">In progress</p>
            </div>

            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-2">
                <Activity className="h-5 w-5 text-primary" />
                <h3 className="font-semibold text-foreground">MCP Services</h3>
              </div>
              <p className="text-2xl font-bold text-green-500">37</p>
              <p className="text-sm text-muted-foreground">Tools available</p>
            </div>
          </div>

          {/* Main Content Areas */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Chat Section */}
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-4">
                <Brain className="h-5 w-5 text-primary" />
                <h3 className="text-lg font-semibold text-foreground">Chat with Nova</h3>
              </div>
              <div className="h-64 bg-muted rounded-lg flex items-center justify-center">
                <p className="text-muted-foreground">Chat interface coming soon...</p>
              </div>
            </div>

            {/* Kanban Section */}
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-4">
                <KanbanSquare className="h-5 w-5 text-primary" />
                <h3 className="text-lg font-semibold text-foreground">Task Board</h3>
              </div>
              <div className="h-64 bg-muted rounded-lg flex items-center justify-center">
                <p className="text-muted-foreground">Kanban board coming soon...</p>
              </div>
            </div>
          </div>

          {/* Settings Section */}
          <div className="mt-6">
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-4">
                <Settings className="h-5 w-5 text-primary" />
                <h3 className="text-lg font-semibold text-foreground">System Configuration</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-muted rounded-lg">
                  <h4 className="font-medium text-foreground mb-2">MCP Servers</h4>
                  <p className="text-sm text-muted-foreground">Gmail MCP: ✅ Online</p>
                  <p className="text-sm text-muted-foreground">Kanban MCP: ✅ Online</p>
                </div>
                <div className="p-4 bg-muted rounded-lg">
                  <h4 className="font-medium text-foreground mb-2">AI Model</h4>
                  <p className="text-sm text-muted-foreground">Gemini 2.5 Pro</p>
                </div>
                <div className="p-4 bg-muted rounded-lg">
                  <h4 className="font-medium text-foreground mb-2">Agent Status</h4>
                  <p className="text-sm text-green-500">Operational</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
