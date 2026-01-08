"use client";

import { AlertCircle, Brain, Cog } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSystemStatusPage, useRefreshAllServices } from "@/hooks/useUnifiedSystemStatus";
import { StatusGrid, StatusOverview } from "@/components/status";

export function SystemStatusTab() {
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
      </div>
    </div>
  );
}
