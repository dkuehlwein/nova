"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiRequest } from "@/lib/api";
import { getStatusIcon, getStatusColor } from "@/components/status";

export function APIKeysTab() {
  const [googleApiStatus, setGoogleApiStatus] = useState<{
    has_google_api_key: boolean;
    google_api_key_valid: boolean;
    gemini_models_available: number;
    status: string;
  } | null>(null);
  const [phoenixStatus, setPhoenixStatus] = useState<{
    phoenix_enabled: boolean;
    phoenix_host: string;
    phoenix_healthy: boolean;
    status: string;
    error?: string;
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

  useEffect(() => {
    // Only fetch API status if we don't have cached status
    // These will use cached results by default
    fetchGoogleApiStatus();
    fetchPhoenixStatus();
    fetchHuggingfaceApiStatus();
    fetchLitellmApiStatus();
    fetchOpenrouterApiStatus();
  }, []);

  const fetchGoogleApiStatus = async (forceRefresh: boolean = false) => {
    try {
      const url = forceRefresh
        ? '/api/api-keys/google-status?force_refresh=true'
        : '/api/api-keys/google-status';

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

  const fetchPhoenixStatus = async () => {
    try {
      const data = await apiRequest('/api/api-keys/phoenix-status') as {
        phoenix_enabled: boolean;
        phoenix_host: string;
        phoenix_healthy: boolean;
        status: string;
        error?: string;
      };
      setPhoenixStatus(data);
    } catch (error) {
      console.error('Failed to load Phoenix status:', error);
    }
  };

  const fetchHuggingfaceApiStatus = async (forceRefresh: boolean = false) => {
    try {
      const url = forceRefresh
        ? '/api/api-keys/huggingface-status?force_refresh=true'
        : '/api/api-keys/huggingface-status';

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
        ? '/api/api-keys/litellm-status?force_refresh=true'
        : '/api/api-keys/litellm-status';

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
        ? '/api/api-keys/openrouter-status?force_refresh=true'
        : '/api/api-keys/openrouter-status';

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
      const response = await apiRequest('/api/api-keys/validate', {
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
      await apiRequest('/api/api-keys/save', {
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

  if (!googleApiStatus && !phoenixStatus && !huggingfaceApiStatus && !litellmApiStatus && !openrouterApiStatus) {
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
    <div className="space-y-6">
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

            {/* Phoenix Observability Section */}
            <div className="border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Phoenix Observability <span className="text-xs text-muted-foreground font-normal">(Self-Hosted)</span></p>
                  <p className="text-sm text-muted-foreground">LLM tracing and debugging via Arize Phoenix</p>
                </div>
                <div className="flex items-center space-x-2">
                  {phoenixStatus?.status === 'ready' && (() => {
                    const StatusIcon = getStatusIcon('operational');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('operational')}`} />;
                  })()}
                  {phoenixStatus?.status === 'unavailable' && (() => {
                    const StatusIcon = getStatusIcon('critical');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('critical')}`} />;
                  })()}
                  {phoenixStatus?.status === 'disabled' && (() => {
                    const StatusIcon = getStatusIcon('degraded');
                    return <StatusIcon className={`h-4 w-4 ${getStatusColor('degraded')}`} />;
                  })()}
                  <Badge variant={phoenixStatus?.phoenix_healthy ? "default" :
                    (phoenixStatus?.phoenix_enabled ? "destructive" : "secondary")
                  }>
                    {phoenixStatus?.status === 'ready' ? 'Connected' :
                     phoenixStatus?.status === 'unavailable' ? 'Unavailable' :
                     'Disabled'}
                  </Badge>
                </div>
              </div>

              {phoenixStatus?.phoenix_enabled && (
                <div className="flex items-center space-x-2 mt-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fetchPhoenixStatus()}
                  >
                    Refresh Status
                  </Button>
                  {phoenixStatus?.phoenix_healthy && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => window.open(phoenixStatus.phoenix_host, '_blank')}
                    >
                      Open Phoenix UI
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
