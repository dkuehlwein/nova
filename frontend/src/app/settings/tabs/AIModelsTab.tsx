"use client";

import { useState, useEffect, useCallback } from "react";
import { Brain } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUserSettings, useUpdateUserSettings, useAvailableModels } from "@/hooks/useNovaQueries";
import { apiRequest } from "@/lib/api";

export function AIModelsTab() {
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

  useEffect(() => {
    if (userSettings && !editingSettings) {
      setEditingSettings(userSettings as unknown as Record<string, unknown>);
    }
  }, [userSettings, editingSettings]);

  const checkLitellmStatus = useCallback(async (baseUrlOverride?: string) => {
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

  useEffect(() => {
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
    <div className="space-y-6">
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
                  value={String(editingSettings?.chat_llm_model || '')}
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
                        {userSettings?.chat_llm_model && (
                          <SelectItem key={`current-chat-${userSettings.chat_llm_model}`} value={String(userSettings.chat_llm_model)}>
                            {String(userSettings.chat_llm_model)} (Current)
                          </SelectItem>
                        )}

                        {/* Available models */}
                        {availableModels?.models ? (
                          <>
                            {/* Chat Models */}
                            {availableModels.models.chat_models?.filter((model: {model_name: string}) =>
                              model.model_name !== userSettings?.chat_llm_model
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
                  value={String(editingSettings?.memory_llm_model || '')}
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
                  value={String(editingSettings?.memory_small_llm_model || '')}
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
                    value={String(editingSettings?.chat_llm_max_tokens || editingSettings?.llm_max_tokens || 4096)}
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
