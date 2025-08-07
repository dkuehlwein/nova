/**
 * Unified Status Utilities and Theme System
 * 
 * Provides consistent status theming, icons, and utilities across all components.
 * Eliminates code duplication from settings page and other status displays.
 * Follows ADR 010 unified system health monitoring architecture.
 */

import { CheckCircle, AlertTriangle, XCircle, AlertCircle, Loader2 } from "lucide-react";

export const STATUS_THEMES = {
  operational: {
    icon: CheckCircle,
    color: "text-green-500 dark:text-green-400",
    bgColor: "bg-green-50 dark:bg-green-950/50",
    borderColor: "border-green-200 dark:border-green-800",
    description: "Operational",
    badgeVariant: "default" as const,
    spin: false
  },
  healthy: {
    icon: CheckCircle,
    color: "text-green-500 dark:text-green-400",
    bgColor: "bg-green-50 dark:bg-green-950/50",
    borderColor: "border-green-200 dark:border-green-800",
    description: "Healthy",
    badgeVariant: "default" as const,
    spin: false
  },
  degraded: {
    icon: AlertTriangle,
    color: "text-yellow-500 dark:text-yellow-400", 
    bgColor: "bg-yellow-50 dark:bg-yellow-950/50",
    borderColor: "border-yellow-200 dark:border-yellow-800",
    description: "Degraded Performance",
    badgeVariant: "secondary" as const,
    spin: false
  },
  critical: {
    icon: XCircle,
    color: "text-red-500 dark:text-red-400",
    bgColor: "bg-red-50 dark:bg-red-950/50", 
    borderColor: "border-red-200 dark:border-red-800",
    description: "Critical Issues",
    badgeVariant: "destructive" as const,
    spin: false
  },
  unhealthy: {
    icon: XCircle,
    color: "text-red-500 dark:text-red-400",
    bgColor: "bg-red-50 dark:bg-red-950/50",
    borderColor: "border-red-200 dark:border-red-800", 
    description: "Service Down",
    badgeVariant: "destructive" as const,
    spin: false
  },
  offline: {
    icon: XCircle,
    color: "text-red-500 dark:text-red-400",
    bgColor: "bg-red-50 dark:bg-red-950/50",
    borderColor: "border-red-200 dark:border-red-800",
    description: "Offline",
    badgeVariant: "destructive" as const,
    spin: false
  },
  unknown: {
    icon: AlertCircle,
    color: "text-gray-500 dark:text-gray-400",
    bgColor: "bg-gray-50 dark:bg-gray-950/50",
    borderColor: "border-gray-200 dark:border-gray-800", 
    description: "Status Unknown",
    badgeVariant: "outline" as const,
    spin: false
  },
  loading: {
    icon: Loader2,
    color: "text-gray-500 dark:text-gray-400",
    bgColor: "bg-gray-50 dark:bg-gray-950/50",
    borderColor: "border-gray-200 dark:border-gray-800",
    description: "Checking...",
    badgeVariant: "outline" as const,
    spin: true
  },
  disabled: {
    icon: AlertCircle,
    color: "text-gray-400 dark:text-gray-500",
    bgColor: "bg-gray-50 dark:bg-gray-950/30",
    borderColor: "border-gray-100 dark:border-gray-800",
    description: "Disabled",
    badgeVariant: "outline" as const,
    spin: false
  }
} as const;

export type StatusType = keyof typeof STATUS_THEMES;

/**
 * Get unified status theme for any status string
 */
export function getStatusTheme(status: string): typeof STATUS_THEMES[StatusType] {
  const normalizedStatus = status.toLowerCase().trim();
  
  // Direct mapping for exact matches
  if (normalizedStatus in STATUS_THEMES) {
    return STATUS_THEMES[normalizedStatus as StatusType];
  }
  
  // Fuzzy matching for common variations
  if (normalizedStatus === "healthy" || normalizedStatus === "operational" || normalizedStatus === "ok") {
    return STATUS_THEMES.operational;
  }
  if (normalizedStatus === "degraded" || normalizedStatus === "warning") {
    return STATUS_THEMES.degraded;
  }
  if (normalizedStatus === "unhealthy" || normalizedStatus === "critical" || 
      normalizedStatus === "offline" || normalizedStatus === "error" || 
      normalizedStatus === "failed" || normalizedStatus === "down") {
    return STATUS_THEMES.critical;
  }
  if (normalizedStatus === "loading" || normalizedStatus === "checking") {
    return STATUS_THEMES.loading;
  }
  if (normalizedStatus === "disabled") {
    return STATUS_THEMES.disabled;
  }
  
  return STATUS_THEMES.unknown;
}

/**
 * Get status text description
 */
export function getStatusText(status: string): string {
  return getStatusTheme(status).description;
}

/**
 * Get status icon component
 */
export function getStatusIcon(status: string) {
  return getStatusTheme(status).icon;
}

/**
 * Get status color class
 */
export function getStatusColor(status: string): string {
  return getStatusTheme(status).color;
}

/**
 * Get status background color class
 */
export function getStatusBgColor(status: string): string {
  return getStatusTheme(status).bgColor;
}

/**
 * Get status border color class
 */
export function getStatusBorderColor(status: string): string {
  return getStatusTheme(status).borderColor;
}

/**
 * Get badge variant for status
 */
export function getStatusBadgeVariant(status: string) {
  return getStatusTheme(status).badgeVariant;
}

/**
 * Check if status icon should spin (for loading states)
 */
export function shouldStatusIconSpin(status: string): boolean {
  return getStatusTheme(status).spin || false;
}

/**
 * Format relative time for status checks
 */
export function formatRelativeTime(timestamp: string | Date): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 5) {
    return "Just now";
  } else if (diffSecs < 60) {
    return `${diffSecs} seconds ago`;
  } else if (diffMins < 60) {
    return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  } else {
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  }
}

/**
 * Format response time for display
 */
export function formatResponseTime(responseTimeMs?: number): string {
  if (!responseTimeMs) return "";
  
  if (responseTimeMs < 1000) {
    return `${responseTimeMs}ms`;
  } else {
    return `${(responseTimeMs / 1000).toFixed(1)}s`;
  }
}

/**
 * Calculate overall health percentage
 */
export function calculateHealthPercentage(
  totalServices: number,
  healthyServices: number
): number {
  if (totalServices === 0) return 0;
  return Math.round((healthyServices / totalServices) * 100);
}

/**
 * Service status type definitions
 */
export interface ServiceStatus {
  name: string;
  type: "core" | "infrastructure" | "external";
  status: string;
  response_time_ms?: number;
  last_check?: string;
  error_message?: string;
  metadata?: Record<string, unknown>;
  essential?: boolean;
  features_available?: string[];
}

export interface MCPServerStatus extends ServiceStatus {
  enabled: boolean;
  tools_count?: number;
  description: string;
  url: string;
}

export interface UnifiedSystemStatus {
  overall_status: "operational" | "degraded" | "critical" | "loading";
  overall_health_percentage: number;
  last_updated: string;
  cached: boolean;
  
  // Service Categories
  core_services: ServiceStatus[];
  infrastructure_services: ServiceStatus[];
  
  // Quick Summary for Navbar
  summary: {
    total_services: number;
    healthy_services: number;
    degraded_services: number;
    critical_services: number;
    top_issues: string[];
  };
  
  // Optional history data
  history?: unknown[];
}

/**
 * Status loading states for consistent UI
 */
export const STATUS_LOADING_STATES = {
  systemStatus: {
    overall_status: "loading" as const,
    overall_health_percentage: 0,
    last_updated: new Date().toISOString(),
    cached: false,
    core_services: [],
    infrastructure_services: [],
    summary: {
      total_services: 0,
      healthy_services: 0,
      degraded_services: 0,
      critical_services: 0,
      top_issues: []
    }
  },
  
  serviceStatus: {
    name: "Loading...",
    type: "core" as const,
    status: "loading",
    last_check: new Date().toISOString()
  }
};