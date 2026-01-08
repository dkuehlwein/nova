"use client";

import { useState, useEffect } from "react";
import { Cog } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiRequest } from "@/lib/api";

export function AutomationTab() {
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Load user settings on component mount
  useEffect(() => {
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
    <div className="space-y-6">
      <div className="space-y-6">

        {/* Agent Processing Section */}
        <div className="space-y-4">
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
