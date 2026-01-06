import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
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


// Per ADR-015, MCP servers are managed by LiteLLM
// This interface matches the read-only API response
interface MCPServerStatus {
  name: string
  description: string
  healthy: boolean
  tools_count: number
  tool_names: string[]
}

interface MCPServersData {
  servers: MCPServerStatus[]
  total_servers: number
  total_tools: number
  source: string
}


// MCP Servers Queries (read-only per ADR-015)
export function useMCPServers() {
  return useQuery({
    queryKey: ['mcp-servers'],
    queryFn: async (): Promise<MCPServersData> => {
      return await apiRequest('/api/mcp/')
    },
    staleTime: 30000, // 30 seconds - servers don't change that often
    refetchInterval: 60000, // Poll every minute instead of 30 seconds
    refetchOnWindowFocus: false, // Don't refetch when switching tabs
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

// Skills Queries
interface SkillInfo {
  name: string
  version: string
  description: string
  author: string
  tags: string[]
}

interface SkillsData {
  skills: SkillInfo[]
  count: number
  timestamp: string
}

export function useSkills() {
  return useQuery({
    queryKey: ['skills'],
    queryFn: async (): Promise<SkillsData> => {
      return await apiRequest('/api/skills/')
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - skills don't change often
    refetchOnWindowFocus: false,
    retry: 2
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
      return await apiRequest('/api/task-dashboard')
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
      return await apiRequest('/api/task-dashboard')
    },
    staleTime: 0, // Real-time updates via WebSocket
    refetchInterval: 30000, // Backup polling
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

// User Settings Queries
interface UserSettings {
  id?: string
  created_at?: string
  updated_at?: string
  onboarding_complete: boolean
  full_name?: string
  email?: string
  timezone: string
  notes?: string
  notification_preferences: Record<string, unknown>
  task_defaults: Record<string, unknown>
  agent_polling_interval: number
  agent_error_retry_interval: number
  memory_search_limit: number
  memory_token_limit: number
  mcp_server_preferences: Record<string, unknown>
  // New LiteLLM-first model fields
  chat_llm_model: string
  chat_llm_temperature: number
  chat_llm_max_tokens: number
  memory_llm_model: string
  memory_small_llm_model: string
  memory_llm_temperature: number
  memory_llm_max_tokens: number
  embedding_model: string
}

export function useUserSettings() {
  return useQuery({
    queryKey: ['user-settings'],
    queryFn: async (): Promise<UserSettings> => {
      return await apiRequest('/api/user-settings/')
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - user settings don't change often
    refetchOnWindowFocus: false, // Don't refetch when switching tabs
    retry: 2
  })
}

export function useAvailableModels() {
  return useQuery({
    queryKey: ['available-models'],
    queryFn: async () => {
      // Use the main models endpoint that provides categorized models
      const response = await apiRequest('/llm/models') as {
        models: {
          chat_models: {model_name: string}[],
          embedding_models: {model_name: string}[],
          all_models: {model_name: string}[]
        },
        total: number
      }
      return {
        models: response.models,
        total_models: response.total
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - models don't change often
    refetchOnWindowFocus: false
  })
}

export function useUpdateUserSettings() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (updates: Partial<UserSettings>): Promise<UserSettings> => {
      return await apiRequest('/api/user-settings/', {
        method: 'PATCH',
        body: JSON.stringify(updates),
        headers: {
          'Content-Type': 'application/json'
        }
      })
    },
    onSuccess: (data) => {
      // Update the cache with the new settings
      queryClient.setQueryData(['user-settings'], data)
    },
    onError: (error) => {
      console.error('Failed to update user settings:', error)
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
      return await apiRequest('/system-prompt')
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - prompt doesn't change often
    refetchOnWindowFocus: false, // Don't refetch when switching tabs
    retry: 2
  })
}

export function useUpdateSystemPrompt() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (content: string): Promise<SystemPromptData> => {
      return await apiRequest('/system-prompt', {
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

export function useSystemPromptBackups(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['system-prompt-backups'],
    queryFn: async (): Promise<{ backups: PromptBackup[] }> => {
      return await apiRequest('/system-prompt/backups')
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - backups don't change often
    refetchOnWindowFocus: false, // Don't refetch when switching tabs
    retry: 2,
    enabled: options?.enabled !== false, // Default to enabled unless explicitly disabled
  })
}

export function useRestorePromptBackup() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (backupFilename: string): Promise<SystemPromptData> => {
      return await apiRequest(`/system-prompt/restore/${backupFilename}`, {
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

export function useDeletePromptBackup() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (backupFilename: string): Promise<{ message: string }> => {
      return await apiRequest(`/system-prompt/backups/${backupFilename}`, {
        method: 'DELETE'
      })
    },
    onSuccess: () => {
      // Refresh backups list after deletion
      queryClient.invalidateQueries({ queryKey: ['system-prompt-backups'] })
    },
    onError: (error) => {
      console.error('Failed to delete prompt backup:', error)
    }
  })
}

// Kanban and Task Queries
export interface Task {
  id: string
  title: string
  description: string
  summary?: string
  status: string
  created_at: string
  updated_at: string
  due_date?: string
  completed_at?: string
  tags: string[]
  needs_decision: boolean
  decision_type?: string
  persons: string[]
  projects: string[]
  comments_count: number
}

export interface TasksByStatus {
  [status: string]: Task[]
}

export function useKanbanTasks() {
  return useQuery({
    queryKey: ['kanban-tasks'],
    queryFn: async (): Promise<TasksByStatus> => {
      const response = await apiRequest('/api/task-dashboard?include_tasks=true') as {
        tasks_by_status: TasksByStatus
      }
      return response.tasks_by_status
    },
    staleTime: 0, // Real-time updates via WebSocket
    refetchInterval: 30000, // Backup polling every 30 seconds
    retry: 2,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
  })
}

export function useCurrentTask() {
  const { data: tasksByStatus } = useKanbanTasks()
  
  return useMemo(() => {
    const inProgressTasks = tasksByStatus?.in_progress || []
    return inProgressTasks.length > 0 ? inProgressTasks[0] : null
  }, [tasksByStatus])
}

export function useCreateTask() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (taskData: {
      title: string
      description: string
      status?: string
      due_date?: string
      tags?: string[]
      person_ids?: string[]
      project_ids?: string[]
    }) => {
      return await apiRequest('/api/tasks', {
        method: 'POST',
        body: JSON.stringify(taskData),
        headers: {
          'Content-Type': 'application/json'
        }
      })
    },
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['kanban-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['task-counts'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (error) => {
      console.error('Failed to create task:', error)
    }
  })
}

export function useUpdateTask() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ taskId, updates }: { taskId: string; updates: Partial<Task> }) => {
      return await apiRequest(`/api/tasks/${taskId}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
        headers: {
          'Content-Type': 'application/json'
        }
      })
    },
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['kanban-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['task-counts'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (error) => {
      console.error('Failed to update task:', error)
    }
  })
}

export function useDeleteTask() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (taskId: string) => {
      return await apiRequest(`/api/tasks/${taskId}`, {
        method: 'DELETE'
      })
    },
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['kanban-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['task-counts'] })
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (error) => {
      console.error('Failed to delete task:', error)
    }
  })
}

export function useTaskById(taskId: string) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: async (): Promise<Task> => {
      return await apiRequest(`/api/tasks/${taskId}`)
    },
    enabled: !!taskId,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2
  })
}

// Helper functions for kanban display
export function formatStatusName(status: string): string {
  return status.replace(/_/g, ' ').toUpperCase()
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'new': return 'bg-blue-500'
    case 'user_input_received': return 'bg-green-500'
    case 'needs_review': return 'bg-red-500'
    case 'waiting': return 'bg-orange-500'
    case 'in_progress': return 'bg-purple-500'
    case 'done': return 'bg-gray-500'
    case 'failed': return 'bg-red-700'
    default: return 'bg-gray-500'
  }
} 