"use client";

import Navbar from "@/components/Navbar";
import { Settings, CheckCircle, AlertCircle, Clock, Brain, Mail, KanbanSquare, Server, Cpu, Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useMCPServers, useToggleMCPServer, useSystemHealth, useRestartService } from "@/hooks/useNovaQueries";
import { useState } from "react";
import SystemPromptEditor from "@/components/SystemPromptEditor";

export default function SettingsPage() {
  const { data: mcpData, isLoading: mcpLoading, error: mcpError } = useMCPServers();
  const { data: systemHealth } = useSystemHealth();
  const toggleMutation = useToggleMCPServer();
  const restartMutation = useRestartService();
  const [restartingService, setRestartingService] = useState<string | null>(null);

  const handleToggleServer = async (serverName: string, currentEnabled: boolean) => {
    try {
      await toggleMutation.mutateAsync({ 
        serverName, 
        enabled: !currentEnabled 
      });
    } catch (error) {
      console.error('Failed to toggle server:', error);
      // Error is handled by the mutation's onError callback
    }
  };

  const handleRestartServer = async (serverName: string) => {
    try {
      setRestartingService(serverName);
      await restartMutation.mutateAsync(serverName);
    } catch (error) {
      console.error('Failed to restart server:', error);
    } finally {
      setRestartingService(null);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "operational":
      case "healthy":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "degraded":
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case "offline":
      case "unhealthy":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "operational":
      case "healthy": 
        return "text-green-500";
      case "degraded": 
        return "text-yellow-500"; 
      case "offline":
      case "unhealthy": 
        return "text-red-500";
      default: 
        return "text-gray-500";
    }
  };

  const getStatusText = (enabled: boolean, healthy: boolean) => {
    if (!enabled) return "disabled";
    if (healthy) return "operational";
    return "offline";
  };

  const getServerIcon = (serverName: string) => {
    switch (serverName.toLowerCase()) {
      case "gmail":
        return Mail;
      case "kanban":
        return KanbanSquare;
      case "memory":
        return Brain;
      default:
        return Server;
    }
  };

  if (mcpLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <div className="text-muted-foreground">Loading settings...</div>
        </div>
      </div>
    );
  }

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

          {/* System Prompt Editor - Full Width */}
          <div className="mb-8">
            <SystemPromptEditor />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* MCP Servers Status */}
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">MCP Servers</h2>
              
              {mcpError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-600">Failed to load MCP servers</p>
                </div>
              )}
              
              <div className="space-y-4">
                {mcpData?.servers?.map((server) => {
                  const ServerIcon = getServerIcon(server.name);
                  const status = getStatusText(server.enabled, server.healthy);
                  const isToggling = toggleMutation.isPending;
                  const isRestarting = restartingService === server.name;
                  
                  return (
                    <div key={server.name} className="border border-border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-3">
                          <ServerIcon className="h-5 w-5 text-primary" />
                          <div>
                            <h3 className="font-medium text-foreground">{server.name}</h3>
                            <p className="text-sm text-muted-foreground">{server.url}</p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-3">
                          <div className="flex items-center space-x-2">
                            {getStatusIcon(status)}
                            {status !== "operational" && (
                              <Badge 
                                variant="destructive"
                                className={getStatusColor(status)}
                              >
                                {status}
                              </Badge>
                            )}
                          </div>
                          <Switch 
                            checked={server.enabled}
                            onCheckedChange={() => handleToggleServer(server.name, server.enabled)}
                            disabled={isToggling}
                          />
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground mb-2">{server.description}</p>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">
                          {server.tools_count || 0} tools available
                        </span>
                        <span className="text-muted-foreground">
                          {server.enabled ? (server.healthy ? `Last check: ${server.last_check || 'Just now'}` : "Health check failed") : "Disabled"}
                        </span>
                      </div>
                      {!server.healthy && server.enabled && (
                        <Button 
                          size="sm" 
                          variant="outline" 
                          className="mt-2 w-full"
                          onClick={() => handleRestartServer(server.name)}
                          disabled={isRestarting}
                        >
                          {isRestarting ? "Restarting..." : "Restart Server"}
                        </Button>
                      )}
                    </div>
                  );
                })}
                
                {(!mcpData?.servers || mcpData.servers.length === 0) && !mcpError && (
                  <div className="text-center py-8 text-muted-foreground">
                    <Server className="h-8 w-8 mx-auto mb-2" />
                    <p className="text-sm">No MCP servers configured</p>
                  </div>
                )}
              </div>
            </div>

            {/* System Status Overview */}
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">System Status</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 border border-border rounded-lg">
                  <div className="flex items-center space-x-2 mb-2">
                    <Cpu className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium text-foreground">Chat Agent</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(systemHealth?.chat_agent || "operational")}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Last check: {systemHealth?.chat_agent_last_check || "Just now"}
                  </p>
                </div>

                <div className="p-4 border border-border rounded-lg">
                  <div className="flex items-center space-x-2 mb-2">
                    <Database className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium text-foreground">Database</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(systemHealth?.database || "operational")}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Last check: {systemHealth?.database_last_check || "Just now"}
                  </p>
                </div>

                <div className="p-4 border border-border rounded-lg">
                  <div className="flex items-center space-x-2 mb-2">
                    <Server className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium text-foreground">MCP Servers</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(mcpData?.healthy_servers === mcpData?.enabled_servers ? "operational" : "degraded")}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {mcpData ? `${mcpData.healthy_servers}/${mcpData.enabled_servers} healthy` : "Loading..."}
                  </p>
                </div>

                <div className="p-4 border border-border rounded-lg">
                  <div className="flex items-center space-x-2 mb-2">
                    <Brain className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium text-foreground">Core Agent</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(systemHealth?.core_agent || "offline")}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Last check: {systemHealth?.core_agent_last_check || "Not running"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 