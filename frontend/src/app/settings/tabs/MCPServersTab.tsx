"use client";

import { Mail, KanbanSquare, Brain, Server } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useMCPServers } from "@/hooks/useNovaQueries";
import { ServiceStatusIndicator } from "@/components/status";

export function MCPServersTab() {
  const { data: mcpData, isLoading: mcpLoading, error: mcpError } = useMCPServers();

  const getServerIcon = (serverName: string) => {
    const name = serverName.toLowerCase();
    if (name.includes("gmail") || name.includes("outlook") || name.includes("mail") || name.includes("google_workspace")) {
      return Mail;
    }
    if (name.includes("kanban")) {
      return KanbanSquare;
    }
    if (name.includes("memory")) {
      return Brain;
    }
    return Server;
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
              </div>
            </div>
            <div className="h-4 w-full bg-muted rounded mb-2" />
            <div className="flex items-center justify-between text-sm">
              <div className="h-3 w-24 bg-muted rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Info banner about LiteLLM management */}
      <div className="p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
        <p className="text-sm text-blue-800 dark:text-blue-200">
          <strong>Note:</strong> MCP servers are managed by LiteLLM. To add or modify servers,
          edit <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">configs/litellm_config.yaml</code> and restart LiteLLM.
        </p>
      </div>

      <div className="space-y-4">
        {mcpData?.servers?.map((server) => {
          const ServerIcon = getServerIcon(server.name);
          const status = server.healthy ? "healthy" : "unhealthy";

          return (
            <div key={server.name} className="border border-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <ServerIcon className="h-5 w-5 text-primary" />
                  <div>
                    <h3 className="font-medium text-foreground">{server.name}</h3>
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
                </div>
              </div>
              <p className="text-sm text-muted-foreground mb-2">{server.description || "No description available"}</p>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  {server.tools_count || 0} tools available
                </span>
                <span className="text-muted-foreground">
                  {server.healthy ? "Connected" : "Connection failed"}
                </span>
              </div>
              {/* Show tool names if available */}
              {server.tool_names && server.tool_names.length > 0 && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-xs text-muted-foreground mb-2">Available tools:</p>
                  <div className="flex flex-wrap gap-1">
                    {server.tool_names.map((toolName) => (
                      <Badge key={toolName} variant="secondary" className="text-xs">
                        {toolName}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {(!mcpData?.servers || mcpData.servers.length === 0) && (
          <div className="text-center py-8 text-muted-foreground">
            <Server className="h-8 w-8 mx-auto mb-2" />
            <p className="text-sm">No MCP servers configured in LiteLLM</p>
            <p className="text-xs mt-1">Add servers to configs/litellm_config.yaml</p>
          </div>
        )}
      </div>
    </div>
  );
}
