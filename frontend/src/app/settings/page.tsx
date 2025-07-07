"use client";

import Navbar from "@/components/Navbar";
import { CheckCircle, AlertCircle, Clock, Brain, Mail, KanbanSquare, Server, Cpu, Database, FileText, ListChecks, ShieldCheck, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { useMCPServers, useToggleMCPServer, useSystemHealth, useRestartService } from "@/hooks/useNovaQueries";
import { useState, Suspense } from "react";
import React from "react";
import SystemPromptEditor from "@/components/SystemPromptEditor";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiRequest } from "@/lib/api";

// Loading component for tabs
function TabContentLoader({ children }: { children: string }) {
  return (
    <div className="flex items-center justify-center h-32">
      <div className="text-muted-foreground">Loading {children}...</div>
    </div>
  );
}

// MCP Servers tab content - loaded only when tab is active
function MCPServersTab() {
  const { data: mcpData, isLoading: mcpLoading, error: mcpError } = useMCPServers();
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

  // Show error if failed to load
  if (mcpError) {
    return (
      <div className="space-y-4">
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
          <p className="text-sm text-destructive">Failed to load MCP servers</p>
        </div>
      </div>
    );
  }

  // Show loading placeholders if still loading
  if (mcpLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="border border-border rounded-lg p-4 animate-pulse">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-3">
                <div className="h-5 w-5 bg-muted rounded" />
                <div>
                  <div className="h-4 w-20 bg-muted rounded mb-1" />
                  <div className="h-3 w-32 bg-muted rounded" />
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <div className="h-4 w-4 bg-muted rounded-full" />
                <div className="h-6 w-10 bg-muted rounded-full" />
              </div>
            </div>
            <div className="h-4 w-full bg-muted rounded mb-2" />
            <div className="flex items-center justify-between text-sm">
              <div className="h-3 w-24 bg-muted rounded" />
              <div className="h-3 w-32 bg-muted rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
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
                        variant={status === "disabled" ? "outline" : "destructive"}
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
        {(!mcpData?.servers || mcpData.servers.length === 0) && (
          <div className="text-center py-8 text-muted-foreground">
            <Server className="h-8 w-8 mx-auto mb-2" />
            <p className="text-sm">No MCP servers configured</p>
          </div>
        )}
      </div>
    </div>
  );
}

// System Status tab content - loaded only when tab is active
function SystemStatusTab() {
  const { data: systemHealth, isLoading: systemHealthLoading } = useSystemHealth();
  const { data: mcpData, isLoading: mcpLoading } = useMCPServers();

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

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="p-4 border border-border rounded-lg">
        <div className="flex items-center space-x-2 mb-2">
          <Cpu className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Chat Agent</span>
        </div>
        <div className="flex items-center space-x-2">
          {systemHealthLoading ? (
            <div className="h-4 w-4 animate-pulse bg-muted rounded-full" />
          ) : (
            getStatusIcon(systemHealth?.chat_agent || "operational")
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {systemHealthLoading ? "Loading..." : `Last check: ${systemHealth?.chat_agent_last_check || "Just now"}`}
        </p>
      </div>

      <div className="p-4 border border-border rounded-lg">
        <div className="flex items-center space-x-2 mb-2">
          <Database className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Database</span>
        </div>
        <div className="flex items-center space-x-2">
          {systemHealthLoading ? (
            <div className="h-4 w-4 animate-pulse bg-muted rounded-full" />
          ) : (
            getStatusIcon(systemHealth?.database || "operational")
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {systemHealthLoading ? "Loading..." : `Last check: ${systemHealth?.database_last_check || "Just now"}`}
        </p>
      </div>

      <div className="p-4 border border-border rounded-lg">
        <div className="flex items-center space-x-2 mb-2">
          <Server className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">MCP Servers</span>
        </div>
        <div className="flex items-center space-x-2">
          {mcpLoading ? (
            <div className="h-4 w-4 animate-pulse bg-muted rounded-full" />
          ) : (
            getStatusIcon(mcpData?.healthy_servers === mcpData?.enabled_servers ? "operational" : (mcpData?.enabled_servers || 0) > 0 ? "degraded" : "offline")
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {mcpLoading ? "Loading..." : (mcpData ? `${mcpData.healthy_servers}/${mcpData.enabled_servers} healthy` : "Loading...")}
        </p>
      </div>

      <div className="p-4 border border-border rounded-lg">
        <div className="flex items-center space-x-2 mb-2">
          <Brain className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Core Agent</span>
        </div>
        <div className="flex items-center space-x-2">
          {systemHealthLoading ? (
            <div className="h-4 w-4 animate-pulse bg-muted rounded-full" />
          ) : (
            getStatusIcon(systemHealth?.core_agent || "offline")
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {systemHealthLoading ? "Loading..." : `Last check: ${systemHealth?.core_agent_last_check || "Not running"}`}
        </p>
      </div>
    </div>
  );
}

// User Settings tab content  
function UserSettingsTab() {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const COMMON_TIMEZONES = [
    'UTC',
    'America/New_York',
    'America/Los_Angeles',
    'Europe/London',
    'Europe/Paris',
    'Asia/Tokyo',
    'Asia/Shanghai',
    'Australia/Sydney',
  ];

  // Load user settings on component mount
  React.useEffect(() => {
    fetchUserSettings();
  }, []);

  const fetchUserSettings = async () => {
    try {
      const data = await apiRequest('/api/user-settings/');
      setSettings(data);
    } catch (error) {
      console.error('Failed to load user settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;
    
    setSaving(true);
    try {
      await apiRequest('/api/user-settings/', {
        method: 'PATCH',
        body: JSON.stringify({
          full_name: settings.full_name,
          email: settings.email,
          timezone: settings.timezone,
          notes: settings.notes,
          email_polling_enabled: settings.email_polling_enabled,
          email_polling_interval: settings.email_polling_interval,
          agent_polling_interval: settings.agent_polling_interval
        }),
      });
      console.log('User settings updated successfully');
    } catch (error) {
      console.error('Failed to update user settings:', error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="space-y-2">
            <div className="h-4 w-20 bg-muted rounded animate-pulse" />
            <div className="h-10 w-full bg-muted rounded animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <User className="h-8 w-8 mx-auto mb-2" />
        <p className="text-sm">Failed to load user settings</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="space-y-6">
        {/* User Profile Section */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground">Profile Information</h3>
          
          <div className="space-y-2">
            <Label htmlFor="full_name">Full Name</Label>
            <Input
              id="full_name"
              value={settings.full_name || ''}
              onChange={(e) => setSettings({...settings, full_name: e.target.value})}
              placeholder="Enter your full name"
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              type="email"
              value={settings.email || ''}
              onChange={(e) => setSettings({...settings, email: e.target.value})}
              placeholder="Enter your email address"
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="timezone">Timezone</Label>
            <select
              id="timezone"
              value={settings.timezone || 'UTC'}
              onChange={(e) => setSettings({...settings, timezone: e.target.value})}
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="notes">Additional Notes</Label>
            <Textarea
              id="notes"
              value={settings.notes || ''}
              onChange={(e) => setSettings({...settings, notes: e.target.value})}
              placeholder="Add any additional context you'd like Nova to know about you..."
              rows={6}
            />
            <p className="text-xs text-muted-foreground">
              This information helps Nova provide more personalized responses.
            </p>
          </div>
        </div>

        {/* Email Integration Section */}
        <div className="space-y-4 border-t border-border pt-6">
          <h3 className="text-lg font-medium text-foreground">Email Integration</h3>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Email Polling</Label>
              <p className="text-sm text-muted-foreground">
                Automatically check for new emails to create tasks
              </p>
            </div>
            <Switch
              checked={settings.email_polling_enabled || false}
              onCheckedChange={(checked) => setSettings({...settings, email_polling_enabled: checked})}
            />
          </div>
          
          {settings.email_polling_enabled && (
            <div className="space-y-2">
              <Label htmlFor="email_polling_interval">Polling Interval (seconds)</Label>
              <Input
                id="email_polling_interval"
                type="number"
                min="60"
                max="3600"
                value={settings.email_polling_interval || 300}
                onChange={(e) => setSettings({...settings, email_polling_interval: parseInt(e.target.value)})}
              />
              <p className="text-xs text-muted-foreground">
                How often to check for new emails (minimum 60 seconds)
              </p>
            </div>
          )}
        </div>

        {/* Agent Settings Section */}
        <div className="space-y-4 border-t border-border pt-6">
          <h3 className="text-lg font-medium text-foreground">Agent Settings</h3>
          
          <div className="space-y-2">
            <Label htmlFor="agent_polling_interval">Agent Polling Interval (seconds)</Label>
            <Input
              id="agent_polling_interval"
              type="number"
              min="10"
              max="300"
              value={settings.agent_polling_interval || 30}
              onChange={(e) => setSettings({...settings, agent_polling_interval: parseInt(e.target.value)})}
            />
            <p className="text-xs text-muted-foreground">
              How often the core agent checks for new tasks (minimum 10 seconds)
            </p>
          </div>
        </div>
        
        <Button onClick={handleSave} disabled={saving} className="w-full">
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <div className="flex h-[calc(100vh-4rem)]">
        {/* Left Sidebar with Tabs */}
        <div className="w-64 border-r border-border bg-muted/30">
          <div className="p-4 border-b border-border">
            <h1 className="font-semibold text-foreground">Settings</h1>
            <p className="text-sm text-muted-foreground">Configure Nova</p>
          </div>
          
          <Tabs defaultValue="system-prompt" orientation="vertical" className="w-full">
            <TabsList className="w-full h-auto flex-col bg-transparent space-y-1 p-2">
              <TabsTrigger 
                value="system-prompt" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <FileText className="h-4 w-4 mr-2" /> 
                System Prompt
              </TabsTrigger>
              <TabsTrigger 
                value="mcp-servers" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <ListChecks className="h-4 w-4 mr-2" /> 
                MCP Servers
              </TabsTrigger>
              <TabsTrigger 
                value="system-status" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <ShieldCheck className="h-4 w-4 mr-2" /> 
                System Status
              </TabsTrigger>
              <TabsTrigger 
                value="user-profile" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <User className="h-4 w-4 mr-2" /> 
                User Settings
              </TabsTrigger>
            </TabsList>

            {/* Main Content Area */}
            <div className="fixed inset-y-0 left-64 right-0 top-16">
              <div className="h-full overflow-y-auto p-6">
                <TabsContent value="system-prompt" className="mt-0">
                  <Suspense fallback={<TabContentLoader>System Prompt</TabContentLoader>}>
                    <SystemPromptEditor />
                  </Suspense>
                </TabsContent>

                <TabsContent value="mcp-servers" className="mt-0">
                  <div className="bg-card border border-border rounded-lg p-6">
                    <h2 className="text-lg font-semibold text-foreground mb-4">MCP Servers Management</h2>
                    <MCPServersTab />
                  </div>
                </TabsContent>

                <TabsContent value="system-status" className="mt-0">
                  <div className="bg-card border border-border rounded-lg p-6">
                    <h2 className="text-lg font-semibold text-foreground mb-4">System Status Overview</h2>
                    <SystemStatusTab />
                  </div>
                </TabsContent>

                <TabsContent value="user-profile" className="mt-0">
                  <div className="bg-card border border-border rounded-lg p-6">
                    <h2 className="text-lg font-semibold text-foreground mb-4">User Settings</h2>
                    <Suspense fallback={<TabContentLoader>User Settings</TabContentLoader>}>
                      <UserSettingsTab />
                    </Suspense>
                  </div>
                </TabsContent>
              </div>
            </div>
          </Tabs>
        </div>
      </div>
    </div>
  );
}