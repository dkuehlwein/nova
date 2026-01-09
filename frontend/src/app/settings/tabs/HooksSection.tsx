"use client";

import { useState } from "react";
import { Play, Settings2, AlertCircle, Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useHooks,
  useTriggerHook,
  useUpdateHookConfig,
  formatHookType,
  formatTimeAgo,
  formatTimeUntil,
  formatInterval,
  calculateSuccessRate,
  type Hook,
} from "@/hooks/useHookStatus";

function StatusIndicator({ status }: { status: Hook['status'] }) {
  switch (status) {
    case 'idle':
      return (
        <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
          <span className="h-2 w-2 rounded-full bg-green-500" />
          Idle
        </span>
      );
    case 'running':
      return (
        <span className="flex items-center gap-1.5 text-blue-600 dark:text-blue-400">
          <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
          Running
        </span>
      );
    case 'error':
      return (
        <span className="flex items-center gap-1.5 text-red-600 dark:text-red-400">
          <span className="h-2 w-2 rounded-full bg-red-500" />
          Error
        </span>
      );
    case 'disabled':
      return (
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <span className="h-2 w-2 rounded-full bg-muted-foreground" />
          Disabled
        </span>
      );
  }
}

function HookCard({ hook }: { hook: Hook }) {
  const [showSettings, setShowSettings] = useState(false);
  const [editInterval, setEditInterval] = useState(hook.polling_interval.toString());

  const triggerHook = useTriggerHook();
  const updateConfig = useUpdateHookConfig();

  const successRate = calculateSuccessRate(hook.stats);

  const handleTrigger = () => {
    triggerHook.mutate(hook.name);
  };

  const handleToggleEnabled = () => {
    updateConfig.mutate({
      hookName: hook.name,
      config: { enabled: !hook.enabled },
    });
  };

  const handleSaveSettings = () => {
    const interval = parseInt(editInterval, 10);
    if (isNaN(interval) || interval < 10) {
      return;
    }
    updateConfig.mutate({
      hookName: hook.name,
      config: { polling_interval: interval },
    });
    setShowSettings(false);
  };

  return (
    <>
      <div className="border border-muted rounded-lg p-4 space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h4 className="font-medium text-foreground">{hook.display_name || formatHookType(hook.hook_type)}</h4>
            <StatusIndicator status={hook.status} />
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor={`enabled-${hook.name}`} className="text-sm text-muted-foreground">
              Enabled
            </Label>
            <Switch
              id={`enabled-${hook.name}`}
              checked={hook.enabled}
              onCheckedChange={handleToggleEnabled}
              disabled={updateConfig.isPending}
            />
          </div>
        </div>

        {/* Timing info */}
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Interval:</span>{" "}
            <span className="text-foreground">{formatInterval(hook.polling_interval)}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Last run:</span>{" "}
            <span className="text-foreground">{formatTimeAgo(hook.last_run)}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Next run:</span>{" "}
            <span className="text-foreground">
              {hook.enabled ? formatTimeUntil(hook.next_run) : "—"}
            </span>
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span className="flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
            {hook.stats.items_processed} items
          </span>
          <span>→</span>
          <span>{hook.stats.tasks_created} tasks created</span>
          <span className="ml-auto">
            {successRate}% success ({hook.stats.successful_runs}/{hook.stats.total_runs} runs)
          </span>
        </div>

        {/* Error message if any */}
        {hook.last_error && (
          <div className="flex items-start gap-2 p-2 bg-red-50 dark:bg-red-950/20 rounded text-sm text-red-700 dark:text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span className="line-clamp-2">{hook.last_error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-muted">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSettings(true)}
          >
            <Settings2 className="h-4 w-4 mr-1" />
            Settings
          </Button>
          <Button
            size="sm"
            onClick={handleTrigger}
            disabled={triggerHook.isPending || !hook.enabled}
          >
            {triggerHook.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Play className="h-4 w-4 mr-1" />
            )}
            Run Now
          </Button>
        </div>
      </div>

      {/* Settings Dialog */}
      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{hook.display_name || formatHookType(hook.hook_type)} Settings</DialogTitle>
            <DialogDescription>
              Configure how often this hook runs and other settings.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="polling-interval">Polling Interval (seconds)</Label>
              <Input
                id="polling-interval"
                type="number"
                min="10"
                value={editInterval}
                onChange={(e) => setEditInterval(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                How often to check for new items (minimum: 10 seconds)
              </p>
            </div>
            {/* Show hook-specific settings as read-only info */}
            {Object.keys(hook.hook_settings).length > 0 && (
              <div className="space-y-2">
                <Label>Hook-Specific Settings</Label>
                <div className="p-3 bg-muted rounded-lg text-sm font-mono">
                  {Object.entries(hook.hook_settings).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="text-muted-foreground">{key}:</span>
                      <span>{String(value)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  Edit configs/input_hooks.yaml to change these settings
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSettings(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveSettings} disabled={updateConfig.isPending}>
              {updateConfig.isPending ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : null}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function HooksSection() {
  const { data, isLoading, error, refetch } = useHooks();

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="border border-muted rounded-lg p-4">
            <div className="h-6 w-32 bg-muted rounded animate-pulse mb-3" />
            <div className="h-4 w-full bg-muted rounded animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <XCircle className="h-8 w-8 text-red-500 mb-2" />
        <p className="text-sm text-muted-foreground mb-4">
          Failed to load hooks. Make sure the backend is running with Celery workers.
        </p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!data?.hooks || data.hooks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <Clock className="h-8 w-8 text-muted-foreground mb-2" />
        <p className="text-sm text-muted-foreground">
          No input hooks configured. Add hooks to configs/input_hooks.yaml to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {data.hooks.map((hook) => (
        <HookCard key={hook.name} hook={hook} />
      ))}
    </div>
  );
}
