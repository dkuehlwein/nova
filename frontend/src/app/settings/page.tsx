"use client";

import Navbar from "@/components/Navbar";
import { CheckCircle, AlertCircle, Clock, Brain, Mail, KanbanSquare, Server, Cpu, Database, FileText, ListChecks, ShieldCheck, User, Key, Cog } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

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
  const [systemStatus, setSystemStatus] = useState<Record<string, unknown> | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);

  React.useEffect(() => {
    fetchSystemStatus();
  }, []);

  const fetchSystemStatus = async () => {
    try {
      const data = await apiRequest('/api/user-settings/system-status') as Record<string, unknown>;
      setSystemStatus(data);
    } catch (error) {
      console.error('Failed to load system status:', error);
    } finally {
      setStatusLoading(false);
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

      <div className="p-4 border border-border rounded-lg">
        <div className="flex items-center space-x-2 mb-2">
          <Cpu className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Ollama (Local AI)</span>
        </div>
        <div className="flex items-center space-x-2">
          {statusLoading ? (
            <div className="h-4 w-4 animate-pulse bg-muted rounded-full" />
          ) : (
            getStatusIcon(systemStatus?.services?.ollama?.status === 'healthy' ? 'operational' : 'offline')
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {statusLoading ? "Loading..." : `Last check: ${systemStatus?.services?.ollama?.status === 'healthy' ? "Just now" : "Failed"}`}
        </p>
      </div>

      <div className="p-4 border border-border rounded-lg">
        <div className="flex items-center space-x-2 mb-2">
          <Server className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">LiteLLM (Gateway)</span>
        </div>
        <div className="flex items-center space-x-2">
          {statusLoading ? (
            <div className="h-4 w-4 animate-pulse bg-muted rounded-full" />
          ) : (
            getStatusIcon(systemStatus?.services?.litellm?.status === 'healthy' ? 'operational' : 'offline')
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {statusLoading ? "Loading..." : `Last check: ${systemStatus?.services?.litellm?.status === 'healthy' ? "Just now" : "Failed"}`}
        </p>
      </div>

      <div className="p-4 border border-border rounded-lg">
        <div className="flex items-center space-x-2 mb-2">
          <Database className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Neo4j (Memory)</span>
        </div>
        <div className="flex items-center space-x-2">
          {statusLoading ? (
            <div className="h-4 w-4 animate-pulse bg-muted rounded-full" />
          ) : (
            getStatusIcon(systemStatus?.services?.neo4j?.status === 'healthy' ? 'operational' : 'offline')
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {statusLoading ? "Loading..." : `Last check: ${systemStatus?.services?.neo4j?.status === 'healthy' ? "Just now" : "Failed"}`}
        </p>
      </div>
    </div>
  );
}

// User Settings tab content  
function UserSettingsTab() {
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
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
      const data = await apiRequest('/api/user-settings/') as Record<string, unknown>;
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
          notes: settings.notes
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
              value={String(settings.full_name || '')}
              onChange={(e) => setSettings({...settings, full_name: e.target.value})}
              placeholder="Enter your full name"
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              type="email"
              value={String(settings.email || '')}
              onChange={(e) => setSettings({...settings, email: e.target.value})}
              placeholder="Enter your email address"
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="timezone">Timezone</Label>
            <select
              id="timezone"
              value={String(settings.timezone || 'UTC')}
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
              value={String(settings.notes || '')}
              onChange={(e) => setSettings({...settings, notes: e.target.value})}
              placeholder="Add any additional context you'd like Nova to know about you..."
              rows={6}
            />
            <p className="text-xs text-muted-foreground">
              This information helps Nova provide more personalized responses.
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

// API Keys and Model Settings tab content
function APIKeysTab() {
  const [systemStatus, setSystemStatus] = useState<Record<string, unknown> | null>(null);
  const [userSettings, setUserSettings] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingSettings, setEditingSettings] = useState<Record<string, unknown> | null>(null);

  React.useEffect(() => {
    fetchSystemStatus();
    fetchUserSettings();
  }, []);

  const fetchSystemStatus = async () => {
    try {
      const data = await apiRequest('/api/user-settings/system-status') as Record<string, unknown>;
      setSystemStatus(data);
    } catch (error) {
      console.error('Failed to load system status:', error);
    }
  };

  const fetchUserSettings = async () => {
    try {
      const data = await apiRequest('/api/user-settings/') as Record<string, unknown>;
      setUserSettings(data);
      setEditingSettings(data);
    } catch (error) {
      console.error('Failed to load user settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!editingSettings) return;
    
    setSaving(true);
    try {
      const response = await apiRequest('/api/user-settings/', {
        method: 'PATCH',
        body: JSON.stringify({
          llm_model: editingSettings.llm_model,
          llm_provider: editingSettings.llm_provider,
          llm_temperature: editingSettings.llm_temperature,
          llm_max_tokens: editingSettings.llm_max_tokens,
        })
      });
      
      setUserSettings(response as Record<string, unknown>);
      setEditingSettings(response as Record<string, unknown>);
    } catch (error) {
      console.error('Failed to save settings:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleInputChange = (field: string, value: string | number) => {
    setEditingSettings(prev => prev ? { ...prev, [field]: value } : null);
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-2">
            <div className="h-4 w-20 bg-muted rounded animate-pulse" />
            <div className="h-10 w-full bg-muted rounded animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="space-y-6">
        {/* API Keys Section */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground">API Keys & Services</h3>
          <p className="text-sm text-muted-foreground">
            Manage your API keys for external services. These are stored securely and never shared.
          </p>
          
          <div className="space-y-4 border border-muted rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Google API Key</p>
                <p className="text-sm text-muted-foreground">For Gmail, Calendar, and cloud AI features</p>
              </div>
              <Badge variant={systemStatus?.api_keys_configured?.google ? "default" : "secondary"}>
                {systemStatus?.api_keys_configured?.google ? "Configured" : "Not configured"}
              </Badge>
            </div>
            
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">LangSmith API Key</p>
                <p className="text-sm text-muted-foreground">For AI debugging and monitoring (optional)</p>
              </div>
              <Badge variant={systemStatus?.api_keys_configured?.langsmith ? "default" : "secondary"}>
                {systemStatus?.api_keys_configured?.langsmith ? "Configured" : "Not configured"}
              </Badge>
            </div>
            
          </div>
        </div>

        {/* Model Configuration Section */}
        <div className="space-y-4 border-t border-border pt-6">
          <h3 className="text-lg font-medium text-foreground">AI Model Configuration</h3>
          <p className="text-sm text-muted-foreground">
            Configure which AI models Nova uses for different tasks. Changes apply immediately.
          </p>
          
          <div className="space-y-4 border border-muted rounded-lg p-4">
            <div className="space-y-2">
              <Label>AI Provider</Label>
              {editingSettings ? (
                <Select 
                  value={String(editingSettings?.llm_provider || 'ollama')} 
                  onValueChange={(value) => handleInputChange('llm_provider', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ollama">Ollama (Local)</SelectItem>
                    <SelectItem value="google">Google (Cloud)</SelectItem>
                  </SelectContent>
                </Select>
              ) : (
                <div className="h-10 w-full bg-muted rounded animate-pulse" />
              )}
              <p className="text-xs text-muted-foreground">
                AI provider: Ollama (local) or Google (cloud)
              </p>
            </div>
            
            <div className="space-y-2">
              <Label>Model</Label>
              {editingSettings ? (
                <Select 
                  value={String(editingSettings?.llm_model || 'gemma3:12b-it-qat')} 
                  onValueChange={(value) => handleInputChange('llm_model', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {editingSettings?.llm_provider === 'ollama' ? (
                      <>
                        <SelectItem value="gemma3:12b-it-qat">Gemma 3 12B (Local)</SelectItem>
                        <SelectItem value="gemma2:9b-instruct-q4_0">Gemma 2 9B (Local)</SelectItem>
                      </>
                    ) : (
                      <>
                        <SelectItem value="gemini-2.5-flash">Gemini 2.5 Flash</SelectItem>
                        <SelectItem value="gemini-1.5-pro">Gemini 1.5 Pro</SelectItem>
                      </>
                    )}
                  </SelectContent>
                </Select>
              ) : (
                <div className="h-10 w-full bg-muted rounded animate-pulse" />
              )}
              <p className="text-xs text-muted-foreground">
                Model used for chat responses and task generation
              </p>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Temperature</Label>
                <Input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={String(editingSettings?.llm_temperature || 0.1)}
                  onChange={(e) => handleInputChange('llm_temperature', parseFloat(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  Response randomness (0.0 - 1.0)
                </p>
              </div>
              <div className="space-y-2">
                <Label>Max Tokens</Label>
                <Input
                  type="number"
                  min="100"
                  max="32000"
                  value={String(editingSettings?.llm_max_tokens || 2048)}
                  onChange={(e) => handleInputChange('llm_max_tokens', parseInt(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  Maximum response length
                </p>
              </div>
            </div>
            
            <div className="flex justify-end">
              <Button onClick={handleSave} disabled={saving}>
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

// Agent and Email Settings tab content
function AgentSettingsTab() {
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Load user settings on component mount
  React.useEffect(() => {
    fetchUserSettings();
  }, []);

  const fetchUserSettings = async () => {
    try {
      const data = await apiRequest('/api/user-settings/') as Record<string, unknown>;
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
          email_polling_enabled: settings.email_polling_enabled,
          email_polling_interval: settings.email_polling_interval,
          agent_polling_interval: settings.agent_polling_interval,
          memory_search_limit: settings.memory_search_limit,
          memory_token_limit: settings.memory_token_limit
        }),
      });
      console.log('Agent settings updated successfully');
    } catch (error) {
      console.error('Failed to update agent settings:', error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
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
        <Cog className="h-8 w-8 mx-auto mb-2" />
        <p className="text-sm">Failed to load agent settings</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="space-y-6">
        {/* Email Integration Section */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground">Email Integration</h3>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Email Polling</Label>
              <p className="text-sm text-muted-foreground">
                Automatically check for new emails to create tasks
              </p>
            </div>
            <Switch
              checked={Boolean(settings.email_polling_enabled)}
              onCheckedChange={(checked) => setSettings({...settings, email_polling_enabled: checked})}
            />
          </div>
          
          {Boolean(settings.email_polling_enabled) && (
            <div className="space-y-2">
              <Label htmlFor="email_polling_interval">Polling Interval (seconds)</Label>
              <Input
                id="email_polling_interval"
                type="number"
                min="60"
                max="3600"
                value={Number(settings.email_polling_interval) || 300}
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
              value={Number(settings.agent_polling_interval) || 30}
              onChange={(e) => setSettings({...settings, agent_polling_interval: parseInt(e.target.value)})}
            />
            <p className="text-xs text-muted-foreground">
              How often the core agent checks for new tasks (minimum 10 seconds)
            </p>
          </div>
        </div>

        {/* Memory Settings Section */}
        <div className="space-y-4 border-t border-border pt-6">
          <h3 className="text-lg font-medium text-foreground">Memory Settings</h3>
          
          <div className="space-y-2">
            <Label htmlFor="memory_search_limit">Memory Search Limit</Label>
            <Input
              id="memory_search_limit"
              type="number"
              min="1"
              max="100"
              value={Number(settings.memory_search_limit) || 10}
              onChange={(e) => setSettings({...settings, memory_search_limit: parseInt(e.target.value)})}
            />
            <p className="text-xs text-muted-foreground">
              Maximum number of memory results to return in searches
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="memory_token_limit">Memory Token Limit</Label>
            <Input
              id="memory_token_limit"
              type="number"
              min="1000"
              max="100000"
              step="1000"
              value={Number(settings.memory_token_limit) || 32000}
              onChange={(e) => setSettings({...settings, memory_token_limit: parseInt(e.target.value)})}
            />
            <p className="text-xs text-muted-foreground">
              Maximum tokens for memory processing (higher values allow more comprehensive analysis)
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
            <p className="text-sm text-muted-foreground">Manage your preferences</p>
          </div>
          
          <Tabs defaultValue="user-profile" orientation="vertical" className="w-full">
            <TabsList className="w-full h-auto flex-col bg-transparent space-y-1 p-2">
              <TabsTrigger 
                value="user-profile" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <User className="h-4 w-4 mr-2" /> 
                Personal Settings
              </TabsTrigger>
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
                value="api-keys" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <Key className="h-4 w-4 mr-2" /> 
                API Keys & Models
              </TabsTrigger>
              <TabsTrigger 
                value="agent-settings" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <Cog className="h-4 w-4 mr-2" /> 
                Agent & Email
              </TabsTrigger>
              <TabsTrigger 
                value="system-status" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <ShieldCheck className="h-4 w-4 mr-2" /> 
                System Status
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
                    <h2 className="text-lg font-semibold text-foreground mb-4">Personal Settings</h2>
                    <Suspense fallback={<TabContentLoader>Personal Settings</TabContentLoader>}>
                      <UserSettingsTab />
                    </Suspense>
                  </div>
                </TabsContent>

                <TabsContent value="api-keys" className="mt-0">
                  <div className="bg-card border border-border rounded-lg p-6">
                    <h2 className="text-lg font-semibold text-foreground mb-4">API Keys & Models</h2>
                    <Suspense fallback={<TabContentLoader>API Keys & Models</TabContentLoader>}>
                      <APIKeysTab />
                    </Suspense>
                  </div>
                </TabsContent>

                <TabsContent value="agent-settings" className="mt-0">
                  <div className="bg-card border border-border rounded-lg p-6">
                    <h2 className="text-lg font-semibold text-foreground mb-4">Agent, Email & Memory Settings</h2>
                    <Suspense fallback={<TabContentLoader>Agent Settings</TabContentLoader>}>
                      <AgentSettingsTab />
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