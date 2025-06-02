"use client";

import Navbar from "@/components/Navbar";
import { Settings, CheckCircle, AlertCircle, Clock, Brain, Mail, KanbanSquare, Server, Cpu, Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

export default function SettingsPage() {
  // Mock settings data
  const mcpServers = [
    {
      name: "Gmail MCP",
      port: 8002,
      status: "operational",
      tools: 27,
      description: "Email management and automation",
      icon: Mail,
      lastPing: "Just now"
    },
    {
      name: "Kanban MCP", 
      port: 8001,
      status: "operational",
      tools: 10,
      description: "Task management and kanban board",
      icon: KanbanSquare,
      lastPing: "Just now"
    },
    {
      name: "Memory MCP",
      port: 8003,
      status: "offline",
      tools: 0,
      description: "Contextual memory and relationships",
      icon: Brain,
      lastPing: "Never"
    }
  ];

  const systemConfig = {
    aiModel: "Gemini 2.5 Pro",
    autoProcessing: true,
    notifications: true,
    emailAutoReply: false,
    taskAutoAssign: true,
    decisionTimeout: 24 // hours
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "operational":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "degraded":
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case "offline":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "operational": return "text-green-500";
      case "degraded": return "text-yellow-500"; 
      case "offline": return "text-red-500";
      default: return "text-gray-500";
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <div className="p-6">
        <div className="mx-auto max-w-6xl">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center space-x-2 mb-2">
              <Settings className="h-6 w-6 text-primary" />
              <h1 className="text-2xl font-bold text-foreground">Settings</h1>
            </div>
            <p className="text-muted-foreground">
              Configure Nova AI Assistant and monitor system status
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* MCP Servers Status */}
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">MCP Servers</h2>
              <div className="space-y-4">
                {mcpServers.map((server) => (
                  <div key={server.name} className="border border-border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <server.icon className="h-5 w-5 text-primary" />
                        <div>
                          <h3 className="font-medium text-foreground">{server.name}</h3>
                          <p className="text-sm text-muted-foreground">Port {server.port}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        {getStatusIcon(server.status)}
                        <Badge 
                          variant={server.status === "operational" ? "outline" : "destructive"}
                          className={getStatusColor(server.status)}
                        >
                          {server.status}
                        </Badge>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">{server.description}</p>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        {server.tools} tools available
                      </span>
                      <span className="text-muted-foreground">
                        Last ping: {server.lastPing}
                      </span>
                    </div>
                    {server.status === "offline" && (
                      <Button size="sm" variant="outline" className="mt-2 w-full">
                        Restart Server
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* System Configuration */}
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">Configuration</h2>
              <div className="space-y-6">
                {/* AI Model */}
                <div>
                  <h3 className="text-sm font-medium text-foreground mb-2">AI Model</h3>
                  <div className="flex items-center justify-between p-3 border border-border rounded-lg">
                    <div className="flex items-center space-x-2">
                      <Brain className="h-4 w-4 text-primary" />
                      <span className="text-sm text-foreground">{systemConfig.aiModel}</span>
                    </div>
                    <Badge variant="secondary">Active</Badge>
                  </div>
                </div>

                {/* Automation Settings */}
                <div>
                  <h3 className="text-sm font-medium text-foreground mb-3">Automation</h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-foreground">Auto Processing</p>
                        <p className="text-xs text-muted-foreground">Automatically process incoming emails and tasks</p>
                      </div>
                      <Switch checked={systemConfig.autoProcessing} />
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-foreground">Email Auto-Reply</p>
                        <p className="text-xs text-muted-foreground">Send automatic responses to simple emails</p>
                      </div>
                      <Switch checked={systemConfig.emailAutoReply} />
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-foreground">Task Auto-Assign</p>
                        <p className="text-xs text-muted-foreground">Automatically assign tasks to team members</p>
                      </div>
                      <Switch checked={systemConfig.taskAutoAssign} />
                    </div>
                  </div>
                </div>

                {/* Notification Settings */}
                <div>
                  <h3 className="text-sm font-medium text-foreground mb-3">Notifications</h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-foreground">Decision Alerts</p>
                        <p className="text-xs text-muted-foreground">Notify when AI needs your input</p>
                      </div>
                      <Switch checked={systemConfig.notifications} />
                    </div>
                    
                    <div className="p-3 border border-border rounded-lg">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-foreground">Decision Timeout</p>
                        <Badge variant="outline">{systemConfig.decisionTimeout}h</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        Auto-escalate decisions after this many hours
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* System Status Overview */}
          <div className="mt-8 bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4">System Status</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 border border-border rounded-lg">
                <div className="flex items-center space-x-2 mb-2">
                  <Cpu className="h-4 w-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">Agent</span>
                </div>
                <div className="flex items-center space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-sm text-green-500">Operational</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">37 tools active</p>
              </div>

              <div className="p-4 border border-border rounded-lg">
                <div className="flex items-center space-x-2 mb-2">
                  <Database className="h-4 w-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">Database</span>
                </div>
                <div className="flex items-center space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-sm text-green-500">Healthy</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">2ms response</p>
              </div>

              <div className="p-4 border border-border rounded-lg">
                <div className="flex items-center space-x-2 mb-2">
                  <Server className="h-4 w-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">Memory</span>
                </div>
                <div className="flex items-center space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-sm text-green-500">Normal</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">2.1GB / 8GB</p>
              </div>

              <div className="p-4 border border-border rounded-lg">
                <div className="flex items-center space-x-2 mb-2">
                  <Brain className="h-4 w-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">Uptime</span>
                </div>
                <div className="flex items-center space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-sm text-green-500">99.9%</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">7 days, 2 hours</p>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="mt-8 flex space-x-4">
            <Button variant="outline">
              Export Logs
            </Button>
            <Button variant="outline">
              Restart All Services
            </Button>
            <Button variant="destructive">
              Emergency Stop
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
} 