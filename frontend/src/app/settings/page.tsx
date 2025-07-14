"use client";

import Navbar from "@/components/Navbar";
import { AlertCircle, Brain, Mail, KanbanSquare, Server, FileText, ListChecks, ShieldCheck, User, Key, Cog } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { useMCPServers, useToggleMCPServer, useRestartService, useUserSettings, useUpdateUserSettings, useAvailableModels } from "@/hooks/useNovaQueries";
import { useSystemStatusPage, useRefreshAllServices } from "@/hooks/useUnifiedSystemStatus";
import { useState, Suspense } from "react";
import React from "react";
import SystemPromptEditor from "@/components/SystemPromptEditor";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiRequest } from "@/lib/api";
import { StatusGrid, StatusOverview, ServiceStatusIndicator, getStatusIcon, getStatusColor } from "@/components/status";

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
          const status = !server.enabled ? "disabled" : (server.healthy ? "healthy" : "unhealthy");
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
                  <ServiceStatusIndicator
                    service={{
                      name: "",
                      type: "external",
                      status: status,
                      features_available: [`${server.tools_count || 0} tools`],
                      essential: false
                    }}
                    showDetails={false}
                    size="sm"
                  />
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
                  {server.enabled ? (server.healthy ? `Last check: Just now` : "Health check failed") : "Disabled"}
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

// System Status tab content - Unified implementation using new components
function SystemStatusTab() {
  const { data: systemStatus, error: systemError } = useSystemStatusPage();
  const refreshMutation = useRefreshAllServices();

  const handleRefreshAll = () => {
    refreshMutation.mutate();
  };

  if (systemError) {
    return (
      <div className="text-center py-8 text-red-500">
        <AlertCircle className="h-8 w-8 mx-auto mb-2" />
        <p>Failed to load system status</p>
        <Button 
          variant="outline" 
          size="sm" 
          className="mt-2"
          onClick={handleRefreshAll}
          disabled={refreshMutation.isPending}
        >
          {refreshMutation.isPending ? "Refreshing..." : "Retry"}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Overall Health Overview */}
      <StatusOverview
        overallStatus={systemStatus?.overall_status || "loading"}
        overallHealthPercentage={systemStatus?.overall_health_percentage || 0}
        lastUpdated={systemStatus?.last_updated || new Date().toISOString()}
        cached={systemStatus?.cached || false}
        summary={systemStatus?.summary}
        onRefresh={handleRefreshAll}
      />
      
      {/* Core Services */}
      <StatusGrid
        title="Core Services"
        services={systemStatus?.core_services || []}
        columns={2}
        emptyMessage="No core services configured"
      />
      
      {/* Infrastructure Services */}
      <StatusGrid
        title="Infrastructure Services"
        services={systemStatus?.infrastructure_services || []}
        columns={3}
        emptyMessage="No infrastructure services configured"
      />
      
      {/* External Services */}
      <StatusGrid
        title="External Services"
        services={systemStatus?.external_services || []}
        columns={2}
        emptyMessage="No external services configured"
      />

      {/* Quick Actions */}
      <div className="p-4 border border-border rounded-lg bg-muted/50">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Cog className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium text-foreground">Quick Actions</span>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* LiteLLM Admin UI */}
          <div className="flex items-center justify-between p-3 border border-border rounded-lg">
            <div className="flex items-center space-x-2">
              <Brain className="h-4 w-4 text-primary" />
              <div>
                <span className="text-sm font-medium text-foreground">LiteLLM Admin UI</span>
                <p className="text-xs text-muted-foreground">Monitor LLM usage and costs</p>
              </div>
            </div>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => window.open('http://localhost:4000', '_blank')}
            >
              Open UI
            </Button>
          </div>

          {/* Refresh All Services */}
          <div className="flex items-center justify-between p-3 border border-border rounded-lg">
            <div className="flex items-center space-x-2">
              <Server className="h-4 w-4 text-primary" />
              <div>
                <span className="text-sm font-medium text-foreground">Refresh All Services</span>
                <p className="text-xs text-muted-foreground">Force health check update</p>
              </div>
            </div>
            <Button 
              variant="outline" 
              size="sm"
              onClick={handleRefreshAll}
              disabled={refreshMutation.isPending}
            >
              {refreshMutation.isPending ? "Refreshing..." : "Refresh"}
            </Button>
          </div>
        </div>
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
            <Select 
              value={String(settings.timezone || 'UTC')} 
              onValueChange={(value) => setSettings({...settings, timezone: value})}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COMMON_TIMEZONES.map((tz) => (
                  <SelectItem key={tz} value={tz}>
                    {tz}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
  const [googleApiStatus, setGoogleApiStatus] = useState<{
    has_google_api_key: boolean;
    google_api_key_valid: boolean;
    gemini_models_available: number;
    status: string;
  } | null>(null);
  const [langsmithApiStatus, setLangsmithApiStatus] = useState<{
    has_langsmith_api_key: boolean;
    langsmith_api_key_valid: boolean;
    features_available: number;
    status: string;
    cached?: boolean;
    last_check?: string;
  } | null>(null);
  const [showApiKeyForm, setShowApiKeyForm] = useState(false);
  const [newApiKey, setNewApiKey] = useState('');
  const [validatingApiKey, setValidatingApiKey] = useState(false);
  const [savingApiKey, setSavingApiKey] = useState(false);
  const { data: userSettings, isLoading: loading } = useUserSettings();
  const { data: availableModels, isLoading: modelsLoading, refetch: refetchModels } = useAvailableModels();
  const updateUserSettings = useUpdateUserSettings();
  const [editingSettings, setEditingSettings] = useState<Record<string, unknown> | null>(null);

  React.useEffect(() => {
    // Only fetch API status if we don't have cached status
    // These will use cached results by default
    fetchGoogleApiStatus();
    fetchLangsmithApiStatus();
  }, []);

  React.useEffect(() => {
    if (userSettings && !editingSettings) {
      setEditingSettings(userSettings as unknown as Record<string, unknown>);
    }
  }, [userSettings, editingSettings]);


  const fetchGoogleApiStatus = async (forceRefresh: boolean = false) => {
    try {
      const url = forceRefresh 
        ? '/api/user-settings/google-api-status?force_refresh=true'
        : '/api/user-settings/google-api-status';
      
      const data = await apiRequest(url) as {
        has_google_api_key: boolean;
        google_api_key_valid: boolean;
        gemini_models_available: number;
        status: string;
        cached?: boolean;
        last_check?: string;
      };
      setGoogleApiStatus(data);
    } catch (error) {
      console.error('Failed to load Google API status:', error);
    }
  };

  const fetchLangsmithApiStatus = async (forceRefresh: boolean = false) => {
    try {
      const url = forceRefresh 
        ? '/api/user-settings/langsmith-api-status?force_refresh=true'
        : '/api/user-settings/langsmith-api-status';
      
      const data = await apiRequest(url) as {
        has_langsmith_api_key: boolean;
        langsmith_api_key_valid: boolean;
        features_available: number;
        status: string;
        cached?: boolean;
        last_check?: string;
      };
      setLangsmithApiStatus(data);
    } catch (error) {
      console.error('Failed to load LangSmith API status:', error);
    }
  };

  const handleSave = async () => {
    if (!editingSettings) return;
    
    try {
      await updateUserSettings.mutateAsync({
        llm_model: editingSettings.llm_model as string,
        llm_temperature: editingSettings.llm_temperature as number,
        llm_max_tokens: editingSettings.llm_max_tokens as number,
      });
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  const validateGoogleApiKey = async (apiKey: string) => {
    setValidatingApiKey(true);
    try {
      const response = await apiRequest('/api/user-settings/validate-api-key', {
        method: 'POST',
        body: JSON.stringify({
          key_type: 'google_api_key',
          api_key: apiKey
        })
      }) as { valid: boolean };
      return response.valid;
    } catch (error) {
      console.error('Failed to validate Google API key:', error);
      return false;
    } finally {
      setValidatingApiKey(false);
    }
  };

  const saveGoogleApiKey = async () => {
    if (!newApiKey.trim()) return;
    
    setSavingApiKey(true);
    try {
      // First validate the key
      const isValid = await validateGoogleApiKey(newApiKey);
      if (!isValid) {
        alert('Invalid Google API key. Please check your key and try again.');
        return;
      }

      // Save the validated key
      await apiRequest('/api/user-settings/save-api-keys', {
        method: 'POST',
        body: JSON.stringify({
          api_keys: {
            google_api_key: newApiKey
          }
        })
      });

      // Refresh status and models (force refresh to validate new key)
      await fetchGoogleApiStatus(true);
      await refetchModels();
      
      // Reset form
      setNewApiKey('');
      setShowApiKeyForm(false);
      
      alert('Google API key saved successfully! Gemini models are now available.');
    } catch (error) {
      console.error('Failed to save Google API key:', error);
      alert('Failed to save Google API key. Please try again.');
    } finally {
      setSavingApiKey(false);
    }
  };

  const handleInputChange = (field: string, value: string | number) => {
    setEditingSettings(prev => {
      if (!prev) return null;
      return { ...prev, [field]: value };
    });
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
          <h3 className="text-lg font-medium text-foreground">External Services</h3>
          <p className="text-sm text-muted-foreground">
            Configure optional external services. All API keys are stored securely and never shared.
          </p>
          
          <div className="space-y-4 border border-muted rounded-lg p-4">
            {/* Google API Key Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Google API Key <span className="text-xs text-muted-foreground">(Optional)</span></p>
                  <p className="text-sm text-muted-foreground">For Google Workspace integration and Gemini cloud AI models</p>
                </div>
                <div className="flex items-center space-x-2">
                  {googleApiStatus?.status === 'ready' && (() => {
                    const StatusIcon = getStatusIcon('operational');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('operational')}`} />;
                  })()}
                  {googleApiStatus?.status === 'configured_invalid' && (() => {
                    const StatusIcon = getStatusIcon('critical');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('critical')}`} />;
                  })()}
                  <Badge variant={googleApiStatus?.has_google_api_key ? 
                    (googleApiStatus?.google_api_key_valid ? "default" : "destructive") : 
                    "secondary"
                  }>
                    {googleApiStatus?.status === 'ready' ? `Valid (${googleApiStatus.gemini_models_available} models)` :
                     googleApiStatus?.status === 'configured_invalid' ? 'Invalid' :
                     'Not configured'}
                  </Badge>
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setShowApiKeyForm(!showApiKeyForm)}
                >
                  {googleApiStatus?.has_google_api_key ? 'Update API Key' : 'Add API Key'}
                </Button>
                {googleApiStatus?.has_google_api_key && (
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => fetchGoogleApiStatus(true)}
                  >
                    Refresh Status
                  </Button>
                )}
              </div>
              
              {showApiKeyForm && (
                <div className="space-y-3 p-3 bg-muted/50 rounded border">
                  <div className="space-y-2">
                    <Label htmlFor="google-api-key">Google API Key</Label>
                    <Input
                      id="google-api-key"
                      type="password"
                      value={newApiKey}
                      onChange={(e) => setNewApiKey(e.target.value)}
                      placeholder="Enter your Google API key"
                    />
                    <p className="text-xs text-muted-foreground">
                      Get your API key from{' '}
                      <a href="https://console.cloud.google.com/" target="_blank" rel="noopener noreferrer" 
                         className="text-primary hover:underline">
                        Google Cloud Console
                      </a>
                    </p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button 
                      size="sm"
                      onClick={saveGoogleApiKey}
                      disabled={!newApiKey.trim() || validatingApiKey || savingApiKey}
                    >
                      {savingApiKey ? 'Saving...' : validatingApiKey ? 'Validating...' : 'Save'}
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => {
                        setShowApiKeyForm(false);
                        setNewApiKey('');
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
            
            {/* LangSmith API Key Section */}
            <div className="border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">LangSmith API Key <span className="text-xs text-muted-foreground">(Optional)</span></p>
                  <p className="text-sm text-muted-foreground">For AI debugging and monitoring</p>
                </div>
                <div className="flex items-center space-x-2">
                  {langsmithApiStatus?.status === 'ready' && (() => {
                    const StatusIcon = getStatusIcon('operational');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('operational')}`} />;
                  })()}
                  {langsmithApiStatus?.status === 'configured_invalid' && (() => {
                    const StatusIcon = getStatusIcon('critical');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('critical')}`} />;
                  })()}
                  <Badge variant={langsmithApiStatus?.has_langsmith_api_key ? 
                    (langsmithApiStatus?.langsmith_api_key_valid ? "default" : "destructive") : 
                    "secondary"
                  }>
                    {langsmithApiStatus?.status === 'ready' ? `Valid (${langsmithApiStatus.features_available} features)` :
                     langsmithApiStatus?.status === 'configured_invalid' ? 'Invalid' :
                     'Not configured'}
                  </Badge>
                </div>
              </div>
              
              {langsmithApiStatus?.has_langsmith_api_key && (
                <div className="flex items-center space-x-2 mt-3">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => fetchLangsmithApiStatus(true)}
                  >
                    Refresh Status
                  </Button>
                </div>
              )}
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
              <Label>Model</Label>
              {editingSettings ? (
                <Select 
                  value={String(editingSettings?.llm_model || '')} 
                  onValueChange={(value) => handleInputChange('llm_model', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsLoading ? (
                      <SelectItem value="loading" disabled>Loading models...</SelectItem>
                    ) : (
                      <>
                        {/* Current user setting (always show this first) */}
                        {editingSettings?.llm_model && (
                          <SelectItem key={`current-${editingSettings.llm_model}`} value={String(editingSettings.llm_model)}>
                            {String(editingSettings.llm_model)} (Current)
                          </SelectItem>
                        )}
                        
                        {/* Available models */}
                        {availableModels?.models ? (
                          <>
                            {/* Local Models */}
                            {availableModels.models.local?.filter((model: {model_name: string}) => 
                              model.model_name !== editingSettings?.llm_model
                            ).map((model: {model_name: string}) => (
                              <SelectItem key={model.model_name} value={model.model_name}>
                                {model.model_name}
                              </SelectItem>
                            ))}
                            {/* Cloud Models */}
                            {availableModels.models.cloud?.filter((model: {model_name: string}) => 
                              model.model_name !== editingSettings?.llm_model
                            ).map((model: {model_name: string}) => (
                              <SelectItem key={model.model_name} value={model.model_name}>
                                {model.model_name}
                              </SelectItem>
                            ))}
                          </>
                        ) : null}
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
              <Button onClick={handleSave} disabled={updateUserSettings.isPending}>
                {updateUserSettings.isPending ? 'Saving...' : 'Save Changes'}
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