import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '../lib/api'

// Type definitions for API responses
interface ConfigValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

interface WebSocketMetrics {
  total_connections: number
  active_connections: number
  messages_sent: number
  messages_received: number
  last_activity: string
}

interface AdminOperationResult {
  success: boolean
  output: string
  error?: string
  exit_code: number
}

interface SystemHealthSummary {
  overall_status: 'operational' | 'degraded' | 'critical'
  chat_agent_status: string
  core_agent_status: string
  mcp_servers_healthy: number
  mcp_servers_total: number
  database_status: string
}

interface MCPServerStatus {
  name: string
  url: string
  health_url: string
  description: string
  enabled: boolean
  healthy: boolean
  tools_count?: number
  error?: string
  last_check?: string
}

interface MCPServersData {
  servers: MCPServerStatus[]
  total_servers: number
  healthy_servers: number
  enabled_servers: number
}

interface SystemHealthData {
  status: string
  service: string
  version: string
  database: string
  chat_checkpointer?: string
  error?: string
  chat_agent?: string
  chat_agent_last_check?: string
  database_last_check?: string
  core_agent?: string
  core_agent_last_check?: string
}

// MCP Servers Queries
export function useMCPServers() {
  return useQuery({
    queryKey: ['mcp-servers'],
    queryFn: async (): Promise<MCPServersData> => {
      return await apiRequest('/api/mcp/')
    },
    staleTime: 0, // Always refetch for real-time data
    refetchInterval: 30000, // Backup polling every 30 seconds
    retry: (failureCount, error) => {
      // Don't retry on 4xx errors (client errors)
      if (error instanceof Error && 'status' in error) {
        const status = (error as { status: number }).status
        if (status >= 400 && status < 500) return false
      }
      return failureCount < 3
    }
  })
}

export function useToggleMCPServer() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ serverName, enabled }: { serverName: string; enabled: boolean }) => {
      return await apiRequest(`/api/mcp/${serverName}/toggle`, {
        method: 'PUT',
        body: JSON.stringify({ enabled }),
        headers: {
          'Content-Type': 'application/json'
        }
      })
    },
    onMutate: async ({ serverName, enabled }) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['mcp-servers'] })

      // Snapshot the previous value
      const previousServers = queryClient.getQueryData(['mcp-servers'])

      // Optimistically update to the new value
      queryClient.setQueryData(['mcp-servers'], (old: unknown) => {
        const typedOld = old as MCPServersData | undefined
        if (!typedOld?.servers) return old
        
        return {
          ...typedOld,
          servers: typedOld.servers.map(server => 
            server.name === serverName 
              ? { ...server, enabled }
              : server
          )
        }
      })

      // Return a context object with the snapshotted value
      return { previousServers }
    },
    onError: (_err, _variables, context) => {
      // If the mutation fails, roll back to the previous value
      if (context?.previousServers) {
        queryClient.setQueryData(['mcp-servers'], context.previousServers)
      }
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
    }
  })
}

// WebSocket Connection Queries
export function useWebSocketConnections() {
  return useQuery({
    queryKey: ['websocket-connections'],
    queryFn: async () => {
      return await apiRequest('/ws/connections')
    },
    refetchInterval: 10000, // Refresh every 10 seconds
  })
}

export function useWebSocketMetrics() {
  return useQuery({
    queryKey: ['websocket-metrics'],
    queryFn: async (): Promise<WebSocketMetrics> => {
      return await apiRequest('/ws/metrics')
    },
    staleTime: 10000, // 10 seconds - metrics change frequently
    refetchInterval: 15000, // Refetch every 15 seconds
    retry: 1 // Don't retry too much for metrics
  })
}

// Configuration Queries
export function useConfigValidation() {
  return useQuery({
    queryKey: ['config-validation'],
    queryFn: async (): Promise<ConfigValidationResult> => {
      return await apiRequest('/api/config/validate')
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - validation doesn't change often
    retry: 2
  })
}

export function useConfigBackups() {
  return useQuery({
    queryKey: ['config-backups'],
    queryFn: async () => {
      return await apiRequest('/api/config/backups')
    },
    staleTime: 60000, // Backups don't change frequently
  })
}

export function useValidateConfig() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (configData: unknown) => {
      return await apiRequest('/api/config/validate', {
        method: 'POST',
        body: JSON.stringify(configData),
        headers: {
          'Content-Type': 'application/json'
        }
      })
    },
    onSuccess: () => {
      // Invalidate validation cache after manual validation
      queryClient.invalidateQueries({ queryKey: ['config-validation'] })
    }
  })
}

// Task Queries (ready for future use)
export function useTaskCounts() {
  return useQuery({
    queryKey: ['task-counts'],
    queryFn: async (): Promise<{ task_counts: Record<string, number>, total_tasks: number }> => {
      return await apiRequest('/api/overview')
    },
    staleTime: 0, // Real-time updates via WebSocket
    refetchInterval: 30000, // Backup polling
  })
}

interface OverviewData {
  task_counts: Record<string, number>
  total_tasks: number
  pending_decisions: number
  recent_activity: Array<{
    type: string
    title: string
    description: string
    time: string
    timestamp: string
    related_task_id?: string
    related_chat_id?: string
  }>
  system_status: string
}

export function useOverview() {
  return useQuery({
    queryKey: ['overview'],
    queryFn: async (): Promise<OverviewData> => {
      return await apiRequest('/api/overview')
    },
    staleTime: 0, // Real-time updates via WebSocket
    refetchInterval: 30000, // Backup polling
  })
}

// System Health Queries
export function useSystemHealth() {
  return useQuery({
    queryKey: ['system-health'],
    queryFn: async (): Promise<SystemHealthData> => {
      return await apiRequest('/api/admin/health')
    },
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // Refetch every minute
    retry: 2
  })
}

export function useSystemHealthSummary() {
  return useQuery({
    queryKey: ['system-health-summary'],
    queryFn: async (): Promise<SystemHealthSummary> => {
      return await apiRequest('/api/system/system-health-summary')
    },
    staleTime: 0, // Always refetch for real-time navbar updates
    refetchInterval: 30000, // Backup polling every 30 seconds
    retry: 2
  })
}

// Admin Operations
export function useRestartService() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (serviceName: string): Promise<AdminOperationResult> => {
      return await apiRequest(`/api/admin/restart/${serviceName}`, {
        method: 'POST'
      })
    },
    onSuccess: () => {
      // Invalidate health-related queries after restart
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
      queryClient.invalidateQueries({ queryKey: ['websocket-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['system-health'] })
    }
  })
}

export function useAllowedServices() {
  return useQuery({
    queryKey: ['allowed-services'],
    queryFn: async (): Promise<string[]> => {
      return await apiRequest('/api/admin/allowed-services')
    },
    staleTime: 10 * 60 * 1000, // 10 minutes - allowed services rarely change
    retry: 1
  })
}

// Helper hook to invalidate all Nova queries (useful for full refresh)
export function useInvalidateAllQueries() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async () => {
      queryClient.invalidateQueries()
      return { success: true }
    }
  })
}

// System Prompt Queries
interface SystemPromptData {
  content: string
  file_path: string
  last_modified: string
  size_bytes: number
}

interface PromptBackup {
  filename: string
  path: string
  created: string
  size_bytes: number
}

export function useSystemPrompt() {
  return useQuery({
    queryKey: ['system-prompt'],
    queryFn: async (): Promise<SystemPromptData> => {
      return await apiRequest('/chat/system-prompt')
    },
    staleTime: 30000, // 30 seconds - prompt doesn't change often
    retry: 2
  })
}

export function useUpdateSystemPrompt() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (content: string): Promise<SystemPromptData> => {
      return await apiRequest('/chat/system-prompt', {
        method: 'PUT',
        body: JSON.stringify({ content }),
        headers: {
          'Content-Type': 'application/json'
        }
      })
    },
    onSuccess: (data) => {
      // Update the cache with the new prompt data
      queryClient.setQueryData(['system-prompt'], data)
      // Invalidate related queries that might be affected
      queryClient.invalidateQueries({ queryKey: ['system-prompt-backups'] })
    },
    onError: (error) => {
      console.error('Failed to update system prompt:', error)
    }
  })
}

export function useSystemPromptBackups() {
  return useQuery({
    queryKey: ['system-prompt-backups'],
    queryFn: async (): Promise<{ backups: PromptBackup[] }> => {
      return await apiRequest('/chat/system-prompt/backups')
    },
    staleTime: 60000, // 1 minute - backups don't change often
    retry: 2
  })
}

export function useRestorePromptBackup() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (backupFilename: string): Promise<SystemPromptData> => {
      return await apiRequest(`/chat/system-prompt/restore/${backupFilename}`, {
        method: 'POST'
      })
    },
    onSuccess: (data) => {
      // Update the prompt cache with restored content
      queryClient.setQueryData(['system-prompt'], data)
      // Refresh backups list
      queryClient.invalidateQueries({ queryKey: ['system-prompt-backups'] })
    },
    onError: (error) => {
      console.error('Failed to restore prompt backup:', error)
    }
  })
} 