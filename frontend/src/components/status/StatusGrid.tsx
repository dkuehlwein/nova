/**
 * StatusGrid Component
 * 
 * Reusable grid layout for displaying multiple service statuses.
 * Provides consistent layout and summary information across all status displays.
 * Follows ADR 010 unified system health monitoring architecture.
 */

import React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { ServiceStatusIndicator } from "./StatusIndicator";
import { type ServiceStatus } from "@/lib/status-utils";

interface StatusGridProps {
  title: string;
  services: ServiceStatus[];
  columns?: number;
  showSummary?: boolean;
  emptyMessage?: string;
  className?: string;
  itemSize?: "sm" | "md" | "lg";
}

export function StatusGrid({ 
  title, 
  services, 
  columns = 3, 
  showSummary = true,
  emptyMessage = "No services configured",
  className,
  itemSize = "md"
}: StatusGridProps) {
  const healthyCount = services.filter(s => 
    s.status === "healthy" || s.status === "operational"
  ).length;
  
  const degradedCount = services.filter(s => 
    s.status === "degraded"
  ).length;
  
  const criticalCount = services.filter(s => 
    s.status === "unhealthy" || s.status === "critical" || s.status === "offline"
  ).length;
  
  // Grid column classes based on columns prop
  const gridColsClass = {
    1: "grid-cols-1",
    2: "grid-cols-1 md:grid-cols-2", 
    3: "grid-cols-1 md:grid-cols-2 lg:grid-cols-3",
    4: "grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
  }[columns] || "grid-cols-1 md:grid-cols-2 lg:grid-cols-3";
  
  if (services.length === 0) {
    return (
      <div className={cn("space-y-4", className)}>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <Badge variant="outline">0 services</Badge>
        </div>
        <div className="text-center py-8 text-muted-foreground">
          {emptyMessage}
        </div>
      </div>
    );
  }
  
  return (
    <div className={cn("space-y-4", className)}>
      {/* Header with Summary */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">{title}</h3>
        
        {showSummary && (
          <div className="flex items-center space-x-2">
            {/* Health Summary */}
            <Badge variant="outline">
              {healthyCount} / {services.length} healthy
            </Badge>
            
            {/* Degraded Count */}
            {degradedCount > 0 && (
              <Badge variant="secondary">
                {degradedCount} degraded
              </Badge>
            )}
            
            {/* Critical Count */}
            {criticalCount > 0 && (
              <Badge variant="destructive">
                {criticalCount} critical
              </Badge>
            )}
          </div>
        )}
      </div>
      
      {/* Services Grid */}
      <div className={cn("grid gap-4", gridColsClass)}>
        {services.map(service => (
          <ServiceStatusIndicator
            key={service.name}
            service={service}
            size={itemSize}
            showDetails={true}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Compact StatusGrid for smaller displays or sidebars
 */
export function StatusGridCompact({ 
  title, 
  services,
  className 
}: {
  title: string;
  services: ServiceStatus[];
  className?: string;
}) {
  return (
    <StatusGrid
      title={title}
      services={services}
      columns={1}
      itemSize="sm"
      showSummary={true}
      className={className}
    />
  );
}

/**
 * StatusOverview component for displaying high-level system health
 */
export function StatusOverview({ 
  overallStatus,
  overallHealthPercentage,
  lastUpdated,
  cached = false,
  summary,
  onRefresh,
  className 
}: {
  overallStatus: string;
  overallHealthPercentage: number;
  lastUpdated: string;
  cached?: boolean;
  summary?: {
    total_services: number;
    healthy_services: number;
    degraded_services: number;
    critical_services: number;
    top_issues: string[];
  };
  onRefresh?: () => void;
  className?: string;
}) {
  return (
    <div className={cn(
      "rounded-lg border p-6 bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-950 dark:to-blue-950",
      className
    )}>
      <div className="flex items-center justify-between">
        {/* Status Info */}
        <div className="flex items-center space-x-4">
          <ServiceStatusIndicator
            service={{
              name: "System Status",
              type: "core",
              status: overallStatus,
              last_check: lastUpdated
            }}
            size="lg"
            showDetails={false}
          />
          
          <div>
            <h2 className="text-xl font-semibold">
              System Health: {overallHealthPercentage}%
            </h2>
            <p className="text-muted-foreground">
              Last updated: {new Date(lastUpdated).toLocaleString()}
              {cached && " (cached)"}
            </p>
            
            {/* Summary Stats */}
            {summary && (
              <div className="flex items-center space-x-4 mt-2">
                <Badge variant="outline">
                  {summary.healthy_services}/{summary.total_services} healthy
                </Badge>
                
                {summary.degraded_services > 0 && (
                  <Badge variant="secondary">
                    {summary.degraded_services} degraded
                  </Badge>
                )}
                
                {summary.critical_services > 0 && (
                  <Badge variant="destructive">
                    {summary.critical_services} critical
                  </Badge>
                )}
              </div>
            )}
            
            {/* Top Issues */}
            {summary && summary.top_issues.length > 0 && (
              <div className="mt-2">
                <p className="text-sm text-muted-foreground">
                  Issues: {summary.top_issues.join(", ")}
                </p>
              </div>
            )}
          </div>
        </div>
        
        {/* Refresh Button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
          >
            Refresh All
          </button>
        )}
      </div>
    </div>
  );
}