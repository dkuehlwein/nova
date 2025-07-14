/**
 * Unified System Status Hook
 * 
 * Provides consistent system status data fetching across all components.
 * Replaces all individual status fetching hooks with a unified approach.
 * Follows ADR 010 unified system health monitoring architecture.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";
import { 
  type UnifiedSystemStatus, 
  STATUS_LOADING_STATES 
} from "@/lib/status-utils";

const QUERY_KEYS = {
  systemHealth: (options?: { includeHistory?: boolean }) => 
    ['system-health', options?.includeHistory || false],
  serviceStatus: (serviceName: string) => ['service-status', serviceName],
} as const;

/**
 * Main hook for unified system status with caching
 */
export function useUnifiedSystemStatus(options?: {
  refreshInterval?: number;
  includeHistory?: boolean;
  forceRefresh?: boolean;
  enabled?: boolean;
}) {
  const { 
    refreshInterval = 30000, // 30 seconds
    includeHistory = false, 
    forceRefresh = false,
    enabled = true
  } = options || {};
  
  return useQuery({
    queryKey: QUERY_KEYS.systemHealth({ includeHistory }),
    queryFn: async (): Promise<UnifiedSystemStatus> => {
      const params = new URLSearchParams();
      if (includeHistory) params.set('include_history', 'true');
      if (forceRefresh) params.set('force_refresh', 'true');
      
      const response = await apiRequest(`/api/system/system-health?${params}`);
      return response as UnifiedSystemStatus;
    },
    refetchInterval: refreshInterval,
    staleTime: 30000, // Consider data stale after 30 seconds
    enabled,
    placeholderData: STATUS_LOADING_STATES.systemStatus
  });
}

/**
 * Hook for navbar system status (optimized for frequent updates)
 */
export function useNavbarSystemStatus() {
  return useUnifiedSystemStatus({ 
    refreshInterval: 60000, // Less frequent for navbar (1 minute)
    includeHistory: false,
    forceRefresh: false
  });
}

/**
 * Hook for system status page (with history and more frequent updates)
 */
export function useSystemStatusPage() {
  return useUnifiedSystemStatus({ 
    refreshInterval: 30000, // More frequent for status page
    includeHistory: true,
    forceRefresh: false
  });
}

/**
 * Hook for individual service status
 */
export function useServiceStatus(serviceName: string, options?: {
  refreshInterval?: number;
  forceRefresh?: boolean;
  enabled?: boolean;
}) {
  const { 
    refreshInterval = 60000,
    forceRefresh = false,
    enabled = true
  } = options || {};
  
  return useQuery({
    queryKey: QUERY_KEYS.serviceStatus(serviceName),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (forceRefresh) params.set('force_refresh', 'true');
      
      const response = await apiRequest(`/api/system/system-health/${serviceName}?${params}`);
      return response;
    },
    refetchInterval: refreshInterval,
    staleTime: 30000,
    enabled: enabled && !!serviceName,
    placeholderData: STATUS_LOADING_STATES.serviceStatus
  });
}


/**
 * Mutation for refreshing all services
 */
export function useRefreshAllServices() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async () => {
      const response = await apiRequest('/api/system/system-health/refresh', {
        method: 'POST'
      });
      return response;
    },
    onSuccess: () => {
      // Invalidate all status-related queries to trigger refetch
      queryClient.invalidateQueries({ 
        queryKey: ['system-health'] 
      });
      queryClient.invalidateQueries({ 
        queryKey: ['service-status'] 
      });
      queryClient.invalidateQueries({ 
        queryKey: ['system-health-summary'] 
      });
    }
  });
}

/**
 * Mutation for refreshing specific service
 */
export function useRefreshService(serviceName: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async () => {
      const response = await apiRequest(`/api/system/unified-status/${serviceName}?force_refresh=true`);
      return response;
    },
    onSuccess: () => {
      // Invalidate specific service query and overall status
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.serviceStatus(serviceName) 
      });
      queryClient.invalidateQueries({ 
        queryKey: ['system-health'] 
      });
    }
  });
}

/**
 * Hook to get filtered services by type
 */
export function useServicesByType(serviceType: "core" | "infrastructure" | "external") {
  const { data: systemStatus } = useUnifiedSystemStatus();
  
  const services = React.useMemo(() => {
    if (!systemStatus) return [];
    
    switch (serviceType) {
      case "core":
        return systemStatus.core_services;
      case "infrastructure":
        return systemStatus.infrastructure_services;
      case "external":
        return systemStatus.external_services;
      default:
        return [];
    }
  }, [systemStatus, serviceType]);
  
  return services;
}

/**
 * Hook to get health statistics
 */
export function useHealthStatistics() {
  const { data: systemStatus } = useUnifiedSystemStatus();
  
  return React.useMemo(() => {
    if (!systemStatus) {
      return {
        totalServices: 0,
        healthyServices: 0,
        degradedServices: 0,
        criticalServices: 0,
        healthPercentage: 0,
        topIssues: []
      };
    }
    
    return {
      totalServices: systemStatus.summary.total_services,
      healthyServices: systemStatus.summary.healthy_services,
      degradedServices: systemStatus.summary.degraded_services,
      criticalServices: systemStatus.summary.critical_services,
      healthPercentage: systemStatus.overall_health_percentage,
      topIssues: systemStatus.summary.top_issues
    };
  }, [systemStatus]);
}

/**
 * Hook for real-time status updates (WebSocket integration)
 * TODO: Implement WebSocket integration for real-time status updates
 */
export function useRealTimeStatusUpdates() {
  const queryClient = useQueryClient();
  
  // TODO: Implement WebSocket connection for real-time status updates
  // This would listen for status change events and update the cache accordingly
  
  React.useEffect(() => {
    // Placeholder for WebSocket integration
    // Could listen for events like "service_status_changed", "health_check_completed", etc.
  }, [queryClient]);
}

// Re-export React for useMemo
import React from "react";