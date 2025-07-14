/**
 * StatusIndicator Component
 * 
 * Universal status display component with consistent styling across all status displays.
 * Replaces all duplicated status icon and color logic throughout the application.
 * Follows ADR 010 unified system health monitoring architecture.
 */

import React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { 
  getStatusTheme, 
  formatRelativeTime, 
  formatResponseTime,
  type ServiceStatus 
} from "@/lib/status-utils";

interface StatusIndicatorProps {
  status: string;
  service?: string;
  serviceType?: "core" | "infrastructure" | "external";
  responseTime?: number;
  features?: string[];
  lastCheck?: string;
  errorMessage?: string;
  essential?: boolean;
  showDetails?: boolean;
  size?: "sm" | "md" | "lg";
  layout?: "horizontal" | "vertical";
  className?: string;
}

export function StatusIndicator({ 
  status, 
  service, 
  serviceType,
  responseTime, 
  features, 
  lastCheck,
  errorMessage,
  essential = false,
  showDetails = true,
  size = "md",
  layout = "horizontal",
  className
}: StatusIndicatorProps) {
  const theme = getStatusTheme(status);
  const StatusIcon = theme.icon;
  
  // Size configurations
  const sizeConfig = {
    sm: {
      icon: "h-4 w-4",
      container: "p-3",
      title: "text-sm font-medium",
      subtitle: "text-xs",
      spacing: "space-x-2"
    },
    md: {
      icon: "h-5 w-5",
      container: "p-4",
      title: "text-base font-medium",
      subtitle: "text-sm",
      spacing: "space-x-3"
    },
    lg: {
      icon: "h-6 w-6",
      container: "p-6",
      title: "text-lg font-semibold",
      subtitle: "text-base",
      spacing: "space-x-4"
    }
  };
  
  const config = sizeConfig[size];
  
  const isVertical = layout === "vertical";
  
  return (
    <div className={cn(
      "rounded-lg border transition-colors",
      theme.bgColor,
      theme.borderColor,
      config.container,
      className
    )}>
      <div className={cn(
        "flex items-center",
        isVertical ? "flex-col space-y-3" : `justify-between ${config.spacing}`
      )}>
        {/* Status Icon and Service Info */}
        <div className={cn(
          "flex items-center",
          isVertical ? "flex-col space-y-2" : config.spacing
        )}>
          <StatusIcon 
            className={cn(
              config.icon, 
              theme.color,
              theme.spin && "animate-spin"
            )} 
          />
          
          {service && (
            <div className={isVertical ? "text-center" : ""}>
              <h3 className={config.title}>{service}</h3>
              
              {showDetails && (
                <div className={cn(
                  "flex flex-wrap gap-1 mt-1",
                  isVertical ? "justify-center" : ""
                )}>
                  {/* Service Type Badge */}
                  {serviceType && (
                    <Badge variant="outline" className="text-xs">
                      {serviceType}
                    </Badge>
                  )}
                  
                  {/* Essential Badge */}
                  {essential && (
                    <Badge variant="destructive" className="text-xs">
                      Essential
                    </Badge>
                  )}
                  
                  {/* Last Check Time */}
                  {lastCheck && (
                    <p className={cn("text-muted-foreground", config.subtitle)}>
                      Last check: {formatRelativeTime(lastCheck)}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        
        {/* Status Details and Badges */}
        {showDetails && (
          <div className={cn(
            "flex items-center gap-2",
            isVertical ? "flex-wrap justify-center" : ""
          )}>
            {/* Response Time */}
            {responseTime && (
              <Badge variant="outline" className="text-xs">
                {formatResponseTime(responseTime)}
              </Badge>
            )}
            
            {/* Features Available */}
            {features && features.length > 0 && (
              <Badge variant="secondary" className="text-xs">
                {features.length} feature{features.length !== 1 ? 's' : ''}
              </Badge>
            )}
            
            {/* Status Badge */}
            <Badge variant={theme.badgeVariant} className="text-xs">
              {theme.description}
            </Badge>
          </div>
        )}
      </div>
      
      {/* Error Message */}
      {showDetails && errorMessage && (
        <div className="mt-3 pt-3 border-t border-border">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium">Error:</span> {errorMessage}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Compact StatusIndicator for inline use (navbar, etc.)
 */
export function StatusIndicatorCompact({ 
  status, 
  service,
  showText = true,
  className 
}: {
  status: string;
  service?: string;
  showText?: boolean;
  className?: string;
}) {
  const theme = getStatusTheme(status);
  const StatusIcon = theme.icon;
  
  return (
    <div className={cn("flex items-center space-x-2", className)}>
      <StatusIcon 
        className={cn(
          "h-4 w-4", 
          theme.color,
          theme.spin && "animate-spin"
        )} 
      />
      {showText && (
        <span className="text-sm font-medium">
          {service ? `${service}: ${theme.description}` : theme.description}
        </span>
      )}
    </div>
  );
}

/**
 * StatusIndicator for service lists - optimized for ServiceStatus objects
 */
export function ServiceStatusIndicator({ 
  service,
  showDetails = true,
  size = "md",
  className 
}: {
  service: ServiceStatus;
  showDetails?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  return (
    <StatusIndicator
      status={service.status}
      service={service.name}
      serviceType={service.type}
      responseTime={service.response_time_ms}
      features={service.features_available}
      lastCheck={service.last_check}
      errorMessage={service.error_message}
      essential={service.essential}
      showDetails={showDetails}
      size={size}
      className={className}
    />
  );
}