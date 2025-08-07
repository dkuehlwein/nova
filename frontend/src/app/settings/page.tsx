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
import { useState, Suspense, useEffect } from "react";
import React from "react";
import { useRouter, useSearchParams } from "next/navigation";
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

// API Keys tab content
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
  const [huggingfaceApiStatus, setHuggingfaceApiStatus] = useState<{
    has_huggingface_api_key: boolean;
    huggingface_api_key_valid: boolean;
    username: string;
    status: string;
    cached?: boolean;
    last_check?: string;
  } | null>(null);
  const [litellmApiStatus, setLitellmApiStatus] = useState<{
    has_litellm_master_key: boolean;
    litellm_master_key_valid: boolean;
    base_url: string;
    status: string;
    cached?: boolean;
    last_check?: string;
  } | null>(null);
  const [openrouterApiStatus, setOpenrouterApiStatus] = useState<{
    has_openrouter_api_key: boolean;
    openrouter_api_key_valid: boolean;
    models_available: number;
    status: string;
    cached?: boolean;
    last_check?: string;
  } | null>(null);
  const [showApiKeyForm, setShowApiKeyForm] = useState(false);
  const [newApiKey, setNewApiKey] = useState('');
  const [validatingApiKey, setValidatingApiKey] = useState(false);
  const [savingApiKey, setSavingApiKey] = useState(false);

  React.useEffect(() => {
    // Only fetch API status if we don't have cached status
    // These will use cached results by default
    fetchGoogleApiStatus();
    fetchLangsmithApiStatus();
    fetchHuggingfaceApiStatus();
    fetchLitellmApiStatus();
    fetchOpenrouterApiStatus();
  }, []);

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

  const fetchHuggingfaceApiStatus = async (forceRefresh: boolean = false) => {
    try {
      const url = forceRefresh 
        ? '/api/user-settings/huggingface-api-status?force_refresh=true'
        : '/api/user-settings/huggingface-api-status';
      
      const data = await apiRequest(url) as {
        has_huggingface_api_key: boolean;
        huggingface_api_key_valid: boolean;
        username: string;
        status: string;
        cached?: boolean;
        last_check?: string;
      };
      setHuggingfaceApiStatus(data);
    } catch (error) {
      console.error('Failed to load HuggingFace API status:', error);
    }
  };

  const fetchLitellmApiStatus = async (forceRefresh: boolean = false) => {
    try {
      const url = forceRefresh 
        ? '/api/user-settings/litellm-api-status?force_refresh=true'
        : '/api/user-settings/litellm-api-status';
      
      const data = await apiRequest(url) as {
        has_litellm_master_key: boolean;
        litellm_master_key_valid: boolean;
        base_url: string;
        status: string;
        cached?: boolean;
        last_check?: string;
      };
      setLitellmApiStatus(data);
    } catch (error) {
      console.error('Failed to load LiteLLM API status:', error);
    }
  };

  const fetchOpenrouterApiStatus = async (forceRefresh: boolean = false) => {
    try {
      const url = forceRefresh 
        ? '/api/user-settings/openrouter-api-status?force_refresh=true'
        : '/api/user-settings/openrouter-api-status';
      
      const data = await apiRequest(url) as {
        has_openrouter_api_key: boolean;
        openrouter_api_key_valid: boolean;
        models_available: number;
        status: string;
        cached?: boolean;
        last_check?: string;
      };
      setOpenrouterApiStatus(data);
    } catch (error) {
      console.error('Failed to load OpenRouter API status:', error);
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

      // Refresh status (force refresh to validate new key)
      await fetchGoogleApiStatus(true);
      
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

  if (!googleApiStatus && !langsmithApiStatus && !huggingfaceApiStatus && !litellmApiStatus && !openrouterApiStatus) {
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
          <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-4">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <strong>Required:</strong> LiteLLM Master Key is needed for Nova to function.
              <br />
              <strong>Optional:</strong> Add external API keys to enable additional AI models and integrations.
            </p>
          </div>
          
          <div className="space-y-4 border border-muted rounded-lg p-4">
            {/* LiteLLM Master Key Section - Required, shown first */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium flex items-center gap-2">
                    LiteLLM Master Key 
                    <span className="bg-rose-100 dark:bg-rose-900 text-rose-800 dark:text-rose-200 text-xs px-2 py-1 rounded-full font-semibold">Required</span>
                  </p>
                  <p className="text-sm text-muted-foreground">Authentication key for your LiteLLM proxy service</p>
                </div>
                <div className="flex items-center space-x-2">
                  {litellmApiStatus?.status === 'ready' && (() => {
                    const StatusIcon = getStatusIcon('operational');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('operational')}`} />;
                  })()}
                  {litellmApiStatus?.status === 'configured_invalid' && (() => {
                    const StatusIcon = getStatusIcon('critical');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('critical')}`} />;
                  })()}
                  <Badge variant={litellmApiStatus?.has_litellm_master_key ? 
                    (litellmApiStatus?.litellm_master_key_valid ? "default" : "destructive") : 
                    "secondary"
                  }>
                    {litellmApiStatus?.status === 'ready' ? litellmApiStatus.base_url :
                     litellmApiStatus?.status === 'configured_invalid' ? 'Invalid' :
                     'Not configured'}
                  </Badge>
                </div>
              </div>
              
              {litellmApiStatus?.has_litellm_master_key && (
                <div className="flex items-center space-x-2 mt-3">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => fetchLitellmApiStatus(true)}
                  >
                    Refresh Status
                  </Button>
                </div>
              )}
            </div>
            
            {/* Google API Key Section */}
            <div className="border-t border-border pt-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Google API Key <span className="text-xs text-muted-foreground font-normal">(Optional)</span></p>
                  <p className="text-sm text-muted-foreground">Enables Gemini AI models and Google Workspace integration</p>
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
                    {googleApiStatus?.status === 'ready' ? `${googleApiStatus.gemini_models_available} models` :
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
            
            {/* HuggingFace API Key Section */}
            <div className="border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">HuggingFace API Key <span className="text-xs text-muted-foreground font-normal">(Optional)</span></p>
                  <p className="text-sm text-muted-foreground">Enables access to HuggingFace models and embeddings</p>
                </div>
                <div className="flex items-center space-x-2">
                  {huggingfaceApiStatus?.status === 'ready' && (() => {
                    const StatusIcon = getStatusIcon('operational');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('operational')}`} />;
                  })()}
                  {huggingfaceApiStatus?.status === 'configured_invalid' && (() => {
                    const StatusIcon = getStatusIcon('critical');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('critical')}`} />;
                  })()}
                  {huggingfaceApiStatus?.status !== 'ready' && (
                    <Badge variant={huggingfaceApiStatus?.has_huggingface_api_key ? 
                      (huggingfaceApiStatus?.huggingface_api_key_valid ? "default" : "destructive") : 
                      "secondary"
                    }>
                      {huggingfaceApiStatus?.status === 'configured_invalid' ? 'Invalid' : 'Not configured'}
                    </Badge>
                  )}
                </div>
              </div>
              
              {huggingfaceApiStatus?.has_huggingface_api_key && (
                <div className="flex items-center space-x-2 mt-3">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => fetchHuggingfaceApiStatus(true)}
                  >
                    Refresh Status
                  </Button>
                </div>
              )}
            </div>
            
            {/* OpenRouter API Key Section */}
            <div className="border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">OpenRouter API Key <span className="text-xs text-muted-foreground font-normal">(Optional)</span></p>
                  <p className="text-sm text-muted-foreground">Enables access to premium models like Horizon Beta</p>
                </div>
                <div className="flex items-center space-x-2">
                  {openrouterApiStatus?.status === 'ready' && (() => {
                    const StatusIcon = getStatusIcon('operational');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('operational')}`} />;
                  })()}
                  {openrouterApiStatus?.status === 'configured_invalid' && (() => {
                    const StatusIcon = getStatusIcon('critical');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('critical')}`} />;
                  })()}
                  <Badge variant={openrouterApiStatus?.has_openrouter_api_key ? 
                    (openrouterApiStatus?.openrouter_api_key_valid ? "default" : "destructive") : 
                    "secondary"
                  }>
                    {openrouterApiStatus?.status === 'ready' ? `${openrouterApiStatus.models_available} models` :
                     openrouterApiStatus?.status === 'configured_invalid' ? 'Invalid' :
                     'Not configured'}
                  </Badge>
                </div>
              </div>
              
              {openrouterApiStatus?.has_openrouter_api_key && (
                <div className="flex items-center space-x-2 mt-3">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => fetchOpenrouterApiStatus(true)}
                  >
                    Refresh Status
                  </Button>
                </div>
              )}
            </div>
            
            {/* LangSmith API Key Section */}
            <div className="border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">LangSmith API Key <span className="text-xs text-muted-foreground font-normal">(Optional)</span></p>
                  <p className="text-sm text-muted-foreground">Enables AI debugging, tracing, and monitoring</p>
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
                  {langsmithApiStatus?.status !== 'ready' && (
                    <Badge variant={langsmithApiStatus?.has_langsmith_api_key ? 
                      (langsmithApiStatus?.langsmith_api_key_valid ? "default" : "destructive") : 
                      "secondary"
                    }>
                      {langsmithApiStatus?.status === 'configured_invalid' ? 'Invalid' : 'Not configured'}
                    </Badge>
                  )}
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
      </div>
    </div>
  );
}

// AI Models & Infrastructure tab content
function AIModelsTab() {
  const { data: userSettings, isLoading: loading } = useUserSettings();
  const { data: availableModels, isLoading: modelsLoading } = useAvailableModels();
  const updateUserSettings = useUpdateUserSettings();
  const [editingSettings, setEditingSettings] = useState<Record<string, unknown> | null>(null);
  const [litellmStatus, setLitellmStatus] = useState<{
    status: string;
    models_count: number;
    base_url: string;
  } | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);

  React.useEffect(() => {
    if (userSettings && !editingSettings) {
      setEditingSettings(userSettings as unknown as Record<string, unknown>);
    }
  }, [userSettings, editingSettings]);

  const checkLitellmStatus = React.useCallback(async (baseUrlOverride?: string) => {
    const baseUrl = baseUrlOverride || (editingSettings?.litellm_base_url as string) || 'http://localhost:4000';
    
    try {
      // Get model count via Nova backend (which handles authentication)
      const models = await apiRequest('/llm/models') as {
        models: {
          chat_models: {model_name: string}[],
          embedding_models: {model_name: string}[],
          all_models: {model_name: string}[]
        },
        total: number
      };
      setLitellmStatus({
        status: 'connected',
        models_count: models.total || 0,
        base_url: baseUrl || 'http://localhost:4000'
      });
    } catch (error) {
      console.error('Failed to connect to LiteLLM via Nova backend:', error);
      setLitellmStatus({
        status: 'disconnected',
        models_count: 0,
        base_url: baseUrl || 'http://localhost:4000'
      });
    }
  }, [editingSettings]);

  React.useEffect(() => {
    // Only check status after settings are loaded
    if (editingSettings) {
      checkLitellmStatus();
    }
  }, [editingSettings, checkLitellmStatus]);

  const handleSave = async () => {
    if (!editingSettings) return;
    
    try {
      await updateUserSettings.mutateAsync({
        litellm_base_url: editingSettings.litellm_base_url as string,
        chat_llm_model: editingSettings.chat_llm_model as string,
        chat_llm_temperature: editingSettings.chat_llm_temperature as number,
        chat_llm_max_tokens: editingSettings.chat_llm_max_tokens as number,
        memory_llm_model: editingSettings.memory_llm_model as string,
        memory_small_llm_model: editingSettings.memory_small_llm_model as string,
        memory_llm_temperature: editingSettings.memory_llm_temperature as number,
        memory_llm_max_tokens: editingSettings.memory_llm_max_tokens as number,
        embedding_model: editingSettings.embedding_model as string,
      } as Record<string, unknown>);
      // Refresh LiteLLM status after saving
      await checkLitellmStatus();
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  const handleInputChange = (field: string, value: string | number) => {
    setEditingSettings(prev => {
      if (!prev) return null;
      return { ...prev, [field]: value };
    });
    
    // If LiteLLM base URL changed, update the status display immediately
    if (field === 'litellm_base_url' && typeof value === 'string') {
      checkLitellmStatus(value);
    }
  };

  const testLitellmConnection = async () => {
    if (!editingSettings?.litellm_base_url) return;
    
    setTestingConnection(true);
    try {
      const baseUrl = (editingSettings.litellm_base_url as string) || 'http://localhost:4000';
      
      // Test via Nova backend (which handles authentication)
      const models = await apiRequest('/llm/models') as {
        models: {
          chat_models: {model_name: string}[],
          embedding_models: {model_name: string}[],
          all_models: {model_name: string}[]
        },
        total: number
      };
      setLitellmStatus({
        status: 'connected',
        models_count: models.total || 0,
        base_url: baseUrl
      });
      alert(`Connection successful! LiteLLM is running at ${baseUrl} with ${models.total || 0} models available.`);
    } catch (error) {
      console.error('Connection test failed:', error);
      const baseUrl = (editingSettings.litellm_base_url as string) || 'http://localhost:4000';
      alert(`Connection failed: Unable to reach LiteLLM at ${baseUrl}\n\nError: ${error instanceof Error ? error.message : 'Network error'}\n\nMake sure LiteLLM is running and the master key is configured in your environment.`);
      setLitellmStatus({
        status: 'disconnected',
        models_count: 0,
        base_url: baseUrl || 'http://localhost:4000'
      });
    } finally {
      setTestingConnection(false);
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

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="space-y-6">
        {/* LiteLLM Connection Section */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground">LiteLLM Connection</h3>
          <p className="text-sm text-muted-foreground">
            Configure your LiteLLM service connection. This is the central gateway for all AI model interactions.
            Authentication is handled via environment configuration for security.
          </p>
          
          <div className="space-y-4 border border-muted rounded-lg p-4">
            {/* Connection Status */}
            <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
              <div className="flex items-center space-x-2">
                <Brain className="h-4 w-4 text-primary" />
                <div>
                  <span className="text-sm font-medium text-foreground">LiteLLM Status</span>
                  <p className="text-xs text-muted-foreground">{litellmStatus?.base_url || 'Loading...'}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {!litellmStatus ? (
                  <>
                    <div className="h-2 w-2 bg-gray-400 rounded-full animate-pulse"></div>
                    <Badge variant="secondary">Checking...</Badge>
                  </>
                ) : litellmStatus.status === 'connected' ? (
                  <>
                    <div className="h-2 w-2 bg-green-500 rounded-full"></div>
                    <Badge variant="default">{litellmStatus.models_count} models</Badge>
                  </>
                ) : (
                  <>
                    <div className="h-2 w-2 bg-red-500 rounded-full"></div>
                    <Badge variant="destructive">Disconnected</Badge>
                  </>
                )}
              </div>
            </div>
            
            {/* Base URL Configuration */}
            <div className="space-y-2">
              <Label htmlFor="litellm_base_url">LiteLLM Base URL</Label>
              <Input
                id="litellm_base_url"
                value={String(editingSettings?.litellm_base_url || 'http://localhost:4000')}
                onChange={(e) => handleInputChange('litellm_base_url', e.target.value)}
                placeholder="http://localhost:4000"
              />
              <p className="text-xs text-muted-foreground">
                URL of your LiteLLM proxy service. Change this if running LiteLLM on a different host or port.
              </p>
            </div>
            
            {/* Test Connection */}
            <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
              <div>
                <span className="text-sm font-medium text-foreground">Connection Test</span>
                <p className="text-xs text-muted-foreground">Test your LiteLLM connection</p>
              </div>
              <Button 
                variant="outline" 
                onClick={testLitellmConnection}
                disabled={testingConnection || !editingSettings?.litellm_base_url}
              >
                {testingConnection ? 'Testing...' : 'Test Connection'}
              </Button>
            </div>
            
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-xs text-amber-800">
                <strong>Note:</strong> LiteLLM master key is configured via environment variables (Tier 2) for security. 
                Only the base URL can be changed here.
              </p>
            </div>
          </div>
        </div>

        {/* Model Configuration Section */}
        <div className="space-y-4 border-t border-border pt-6">
          <h3 className="text-lg font-medium text-foreground">AI Model Selection</h3>
          <p className="text-sm text-muted-foreground">
            Choose which AI models Nova uses for different tasks. All models are routed through LiteLLM.
          </p>
          
          <div className="space-y-4 border border-muted rounded-lg p-4">
            
            {/* Chat Model Selection */}
            <div className="space-y-2">
              <Label>Chat Model</Label>
              {editingSettings ? (
                <Select 
                  value={String(editingSettings?.chat_llm_model || editingSettings?.llm_model || '')} 
                  onValueChange={(value) => handleInputChange('chat_llm_model', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsLoading ? (
                      <SelectItem value="loading" disabled>Loading models...</SelectItem>
                    ) : (
                      <>
                        {/* Current saved setting (only show "Current" for actually saved value) */}
                        {(userSettings?.chat_llm_model || userSettings?.llm_model) && (
                          <SelectItem key={`current-chat-${userSettings.chat_llm_model || userSettings.llm_model}`} value={String(userSettings.chat_llm_model || userSettings.llm_model)}>
                            {String(userSettings.chat_llm_model || userSettings.llm_model)} (Current)
                          </SelectItem>
                        )}
                        
                        {/* Available models */}
                        {availableModels?.models ? (
                          <>
                            {/* Chat Models */}
                            {availableModels.models.chat_models?.filter((model: {model_name: string}) => 
                              model.model_name !== (userSettings?.chat_llm_model || userSettings?.llm_model)
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
                Primary model for conversations and task generation
              </p>
            </div>
            
            {/* Memory Model Selection */}
            <div className="space-y-2">
              <Label>Memory Model</Label>
              {editingSettings ? (
                <Select 
                  value={String(editingSettings?.memory_llm_model || editingSettings?.llm_model || '')} 
                  onValueChange={(value) => handleInputChange('memory_llm_model', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsLoading ? (
                      <SelectItem value="loading" disabled>Loading models...</SelectItem>
                    ) : (
                      <>
                        {/* Current saved setting (only show "Current" for actually saved value) */}
                        {userSettings?.memory_llm_model && (
                          <SelectItem key={`current-memory-${userSettings.memory_llm_model}`} value={String(userSettings.memory_llm_model)}>
                            {String(userSettings.memory_llm_model)} (Current)
                          </SelectItem>
                        )}
                        
                        {/* Available models */}
                        {availableModels?.models ? (
                          <>
                            {/* Chat Models (can be used for memory) */}
                            {availableModels.models.chat_models?.filter((model: {model_name: string}) => 
                              model.model_name !== userSettings?.memory_llm_model
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
                Model for memory processing and context analysis
              </p>
            </div>
            
            {/* Memory Small Model Selection */}
            <div className="space-y-2">
              <Label>Memory Small Model</Label>
              {editingSettings ? (
                <Select 
                  value={String(editingSettings?.memory_small_llm_model || editingSettings?.memory_llm_model || '')} 
                  onValueChange={(value) => handleInputChange('memory_small_llm_model', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsLoading ? (
                      <SelectItem value="loading" disabled>Loading models...</SelectItem>
                    ) : (
                      <>
                        {/* Current saved setting (only show "Current" for actually saved value) */}
                        {userSettings?.memory_small_llm_model && (
                          <SelectItem key={`current-memory-small-${userSettings.memory_small_llm_model}`} value={String(userSettings.memory_small_llm_model)}>
                            {String(userSettings.memory_small_llm_model)} (Current)
                          </SelectItem>
                        )}
                        
                        {/* Available models */}
                        {availableModels?.models ? (
                          <>
                            {/* Chat Models (can be used for memory) */}
                            {availableModels.models.chat_models?.filter((model: {model_name: string}) => 
                              model.model_name !== userSettings?.memory_small_llm_model
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
                Lightweight model for quick memory operations and classification
              </p>
            </div>
            
            {/* Embedding Model Selection */}
            <div className="space-y-2">
              <Label>Embedding Model</Label>
              {editingSettings ? (
                <Select 
                  value={String(editingSettings?.embedding_model || '')} 
                  onValueChange={(value) => handleInputChange('embedding_model', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsLoading ? (
                      <SelectItem value="loading" disabled>Loading models...</SelectItem>
                    ) : (
                      <>
                        {/* Current saved setting (only show "Current" for actually saved value) */}
                        {userSettings?.embedding_model && (
                          <SelectItem key={`current-embedding-${userSettings.embedding_model}`} value={String(userSettings.embedding_model)}>
                            {String(userSettings.embedding_model)} (Current)
                          </SelectItem>
                        )}
                        
                        {/* Available models */}
                        {availableModels?.models ? (
                          <>
                            {/* Embedding Models */}
                            {availableModels.models.embedding_models?.filter((model: {model_name: string}) => 
                              model.model_name !== userSettings?.embedding_model
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
                Model for document search and semantic matching
              </p>
            </div>
            
            {/* Chat Model Parameters */}
            <div className="space-y-4 border-t border-border pt-4">
              <h4 className="font-medium text-sm text-foreground">Chat Model Parameters</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Temperature</Label>
                  <Input
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={String(editingSettings?.chat_llm_temperature || editingSettings?.llm_temperature || 0.7)}
                    onChange={(e) => handleInputChange('chat_llm_temperature', parseFloat(e.target.value))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Response creativity (0.0 = precise, 1.0 = creative)
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Max Tokens</Label>
                  <Input
                    type="number"
                    min="100"
                    max="32000"
                    value={String(editingSettings?.chat_llm_max_tokens || editingSettings?.llm_max_tokens || 2048)}
                    onChange={(e) => handleInputChange('chat_llm_max_tokens', parseInt(e.target.value))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Maximum response length
                  </p>
                </div>
              </div>
            </div>
            
            {/* Memory Model Parameters */}
            <div className="space-y-4 border-t border-border pt-4">
              <h4 className="font-medium text-sm text-foreground">Memory Model Parameters</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Temperature</Label>
                  <Input
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={String(editingSettings?.memory_llm_temperature || 0.1)}
                    onChange={(e) => handleInputChange('memory_llm_temperature', parseFloat(e.target.value))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Lower values for factual accuracy
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Max Tokens</Label>
                  <Input
                    type="number"
                    min="100"
                    max="32000"
                    value={String(editingSettings?.memory_llm_max_tokens || 2048)}
                    onChange={(e) => handleInputChange('memory_llm_max_tokens', parseInt(e.target.value))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Memory processing token limit
                  </p>
                </div>
              </div>
            </div>
            
            <div className="flex justify-end pt-4">
              <Button onClick={handleSave} disabled={updateUserSettings.isPending}>
                {updateUserSettings.isPending ? 'Saving...' : 'Save Configuration'}
              </Button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

// Automation & Processing tab content
function AutomationTab() {
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
      console.log('Automation settings updated successfully');
    } catch (error) {
      console.error('Failed to update automation settings:', error);
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
        <p className="text-sm">Failed to load automation settings</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="space-y-6">
        {/* Email Processing Section */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground">Email Processing</h3>
          <p className="text-sm text-muted-foreground">
            Configure how Nova monitors and processes your email for automatic task creation.
          </p>
          
          <div className="space-y-4 border border-muted rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Enable Email Monitoring</Label>
                <p className="text-sm text-muted-foreground">
                  Automatically scan emails and create relevant tasks
                </p>
              </div>
              <Switch
                checked={Boolean(settings.email_polling_enabled)}
                onCheckedChange={(checked) => setSettings({...settings, email_polling_enabled: checked})}
              />
            </div>
            
            {Boolean(settings.email_polling_enabled) && (
              <div className="space-y-2 pt-4 border-t border-border">
                <Label htmlFor="email_polling_interval">Monitoring Interval (seconds)</Label>
                <Input
                  id="email_polling_interval"
                  type="number"
                  min="60"
                  max="3600"
                  value={Number(settings.email_polling_interval) || 300}
                  onChange={(e) => setSettings({...settings, email_polling_interval: parseInt(e.target.value)})}
                />
                <p className="text-xs text-muted-foreground">
                  How frequently to check for new emails (minimum: 60 seconds, recommended: 300 seconds)
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Agent Processing Section */}
        <div className="space-y-4 border-t border-border pt-6">
          <h3 className="text-lg font-medium text-foreground">Core Agent Processing</h3>
          <p className="text-sm text-muted-foreground">
            Configure Nova&apos;s autonomous task processing behavior and performance.
          </p>
          
          <div className="space-y-4 border border-muted rounded-lg p-4">
            <div className="space-y-2">
              <Label htmlFor="agent_polling_interval">Agent Processing Interval (seconds)</Label>
              <Input
                id="agent_polling_interval"
                type="number"
                min="10"
                max="300"
                value={Number(settings.agent_polling_interval) || 30}
                onChange={(e) => setSettings({...settings, agent_polling_interval: parseInt(e.target.value)})}
              />
              <p className="text-xs text-muted-foreground">
                How often the core agent processes tasks (minimum: 10 seconds, recommended: 30 seconds)
              </p>
            </div>
          </div>
        </div>

        {/* Memory System Section */}
        <div className="space-y-4 border-t border-border pt-6">
          <h3 className="text-lg font-medium text-foreground">Memory System</h3>
          <p className="text-sm text-muted-foreground">
            Configure how Nova stores, searches, and processes contextual memory.
          </p>
          
          <div className="space-y-4 border border-muted rounded-lg p-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="memory_search_limit">Search Result Limit</Label>
                <Input
                  id="memory_search_limit"
                  type="number"
                  min="1"
                  max="100"
                  value={Number(settings.memory_search_limit) || 10}
                  onChange={(e) => setSettings({...settings, memory_search_limit: parseInt(e.target.value)})}
                />
                <p className="text-xs text-muted-foreground">
                  Maximum memory results returned per search
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="memory_token_limit">Processing Token Limit</Label>
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
                  Token limit for memory analysis (higher = more comprehensive)
                </p>
              </div>
            </div>
          </div>
        </div>
        
        <div className="flex justify-end pt-4">
          <Button onClick={handleSave} disabled={saving} className="w-full">
            {saving ? 'Saving Changes...' : 'Save Automation Settings'}
          </Button>
        </div>
      </div>
    </div>
  );
}

function SettingsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [currentTab, setCurrentTab] = useState("ai-models");

  // Initialize current tab from URL or default
  useEffect(() => {
    const tabFromUrl = searchParams.get("tab");
    if (tabFromUrl) {
      setCurrentTab(tabFromUrl);
    }
  }, [searchParams]);

  // Handle tab change and update URL
  const handleTabChange = (newTab: string) => {
    setCurrentTab(newTab);
    const newUrl = `/settings?tab=${newTab}`;
    router.push(newUrl, { scroll: false });
  };

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
          
          <Tabs value={currentTab} onValueChange={handleTabChange} orientation="vertical" className="w-full">
            <TabsList className="w-full h-auto flex-col bg-transparent space-y-1 p-2">
              <TabsTrigger 
                value="user-profile" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <User className="h-4 w-4 mr-2" /> 
                Personal
              </TabsTrigger>
              <TabsTrigger 
                value="ai-models" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <Brain className="h-4 w-4 mr-2" /> 
                AI Models
              </TabsTrigger>
              <TabsTrigger 
                value="api-keys" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <Key className="h-4 w-4 mr-2" /> 
                API Keys
              </TabsTrigger>
              <TabsTrigger 
                value="automation" 
                className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
              >
                <Cog className="h-4 w-4 mr-2" /> 
                Automation
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

                <TabsContent value="ai-models" className="mt-0">
                  <div className="bg-card border border-border rounded-lg p-6">
                    <h2 className="text-lg font-semibold text-foreground mb-4">AI Models & Infrastructure</h2>
                    <Suspense fallback={<TabContentLoader>AI Models</TabContentLoader>}>
                      <AIModelsTab />
                    </Suspense>
                  </div>
                </TabsContent>

                <TabsContent value="api-keys" className="mt-0">
                  <div className="bg-card border border-border rounded-lg p-6">
                    <h2 className="text-lg font-semibold text-foreground mb-4">External API Keys</h2>
                    <Suspense fallback={<TabContentLoader>API Keys</TabContentLoader>}>
                      <APIKeysTab />
                    </Suspense>
                  </div>
                </TabsContent>

                <TabsContent value="automation" className="mt-0">
                  <div className="bg-card border border-border rounded-lg p-6">
                    <h2 className="text-lg font-semibold text-foreground mb-4">Automation & Processing</h2>
                    <Suspense fallback={<TabContentLoader>Automation</TabContentLoader>}>
                      <AutomationTab />
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

export default function SettingsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
          <div className="text-muted-foreground">Loading settings...</div>
        </div>
      </div>
    }>
      <SettingsPageContent />
    </Suspense>
  );
}