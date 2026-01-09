import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '../lib/api'

// Type definitions for hook API responses
export interface HookStats {
  total_runs: number
  successful_runs: number
  failed_runs: number
  items_processed: number
  tasks_created: number
  tasks_updated: number
}

export interface Hook {
  name: string
  hook_type: string
  display_name: string
  enabled: boolean
  polling_interval: number
  status: 'idle' | 'running' | 'error' | 'disabled'
  last_run: string | null
  next_run: string | null
  stats: HookStats
  last_error: string | null
  hook_settings: Record<string, unknown>
}

export interface HooksListResponse {
  hooks: Hook[]
}

export interface HookConfigUpdate {
  enabled?: boolean
  polling_interval?: number
}

export interface TriggerResponse {
  task_id: string
  hook_name: string
  status: string
  queued_at: string
}

// Query keys
export const hookQueryKeys = {
  all: ['hooks'] as const,
  detail: (name: string) => ['hooks', name] as const,
}

// List all hooks with status and stats
export function useHooks(options?: { refreshInterval?: number }) {
  return useQuery({
    queryKey: hookQueryKeys.all,
    queryFn: async (): Promise<HooksListResponse> => {
      return await apiRequest('/api/hooks/')
    },
    staleTime: 5000, // 5 seconds - hooks status can change frequently
    refetchInterval: options?.refreshInterval ?? 10000, // 10 seconds default polling
    refetchIntervalInBackground: false, // Don't poll when tab is not visible
    refetchOnWindowFocus: true,
    retry: 2,
  })
}

// Get single hook details
export function useHook(hookName: string) {
  return useQuery({
    queryKey: hookQueryKeys.detail(hookName),
    queryFn: async (): Promise<Hook> => {
      return await apiRequest(`/api/hooks/${hookName}`)
    },
    enabled: !!hookName,
    staleTime: 5000,
    retry: 2,
  })
}

// Update hook configuration
export function useUpdateHookConfig() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ hookName, config }: { hookName: string; config: HookConfigUpdate }): Promise<Hook> => {
      return await apiRequest(`/api/hooks/${hookName}`, {
        method: 'PATCH',
        body: JSON.stringify(config),
        headers: { 'Content-Type': 'application/json' },
      })
    },
    onSuccess: (data, variables) => {
      // Update the hooks list cache
      queryClient.invalidateQueries({ queryKey: hookQueryKeys.all })
      // Update the individual hook cache
      queryClient.setQueryData(hookQueryKeys.detail(variables.hookName), data)
    },
    onError: (error) => {
      console.error('Failed to update hook config:', error)
    },
  })
}

// Manually trigger a hook
export function useTriggerHook() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (hookName: string): Promise<TriggerResponse> => {
      return await apiRequest(`/api/hooks/${hookName}/trigger`, {
        method: 'POST',
      })
    },
    onSuccess: () => {
      // Invalidate hooks list to show updated status
      queryClient.invalidateQueries({ queryKey: hookQueryKeys.all })
    },
    onError: (error) => {
      console.error('Failed to trigger hook:', error)
    },
  })
}

// Helper to format hook type for display (fallback when display_name not available)
export function formatHookType(hookType: string): string {
  // Convert snake_case to Title Case as fallback
  return hookType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

// Helper to format time ago
export function formatTimeAgo(isoString: string | null): string {
  if (!isoString) return 'Never'

  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSeconds < 60) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

// Helper to format time until
export function formatTimeUntil(isoString: string | null): string {
  if (!isoString) return 'Unknown'

  const date = new Date(isoString)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()

  if (diffMs < 0) return 'Now'

  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)

  if (diffSeconds < 60) return `in ${diffSeconds}s`
  if (diffMinutes < 60) return `in ${diffMinutes}m`
  return `in ${diffHours}h`
}

// Helper to format polling interval
export function formatInterval(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

// Helper to calculate success rate
export function calculateSuccessRate(stats: HookStats): number {
  if (stats.total_runs === 0) return 100
  return Math.round((stats.successful_runs / stats.total_runs) * 100)
}
