// Re-export everything from useNovaQueries for backward compatibility
export {
  useKanbanTasks,
  useCurrentTask,
  useCreateTask,
  useUpdateTask,
  useDeleteTask,
  formatStatusName,
  getStatusColor,
  type Task,
  type TasksByStatus
} from './useNovaQueries'

// Legacy hook for backward compatibility
// This maintains the same API as the old useKanban hook
export function useKanban() {
  const kanbanQuery = useKanbanTasks()
  const createTaskMutation = useCreateTask()
  const updateTaskMutation = useUpdateTask()
  const deleteTaskMutation = useDeleteTask()
  const currentTask = useCurrentTask()

  return {
    // Data
    tasksByStatus: kanbanQuery.data || {},
    loading: kanbanQuery.isLoading,
    error: kanbanQuery.error?.message || null,
    
    // Current task
    getCurrentTask: () => currentTask,
    
    // Helper functions
    formatStatusName,
    getStatusColor,
    
    // Actions
    createTask: createTaskMutation.mutate,
    updateTaskStatus: async (taskId: string, newStatus: string) => {
      return updateTaskMutation.mutateAsync({ taskId, updates: { status: newStatus } })
    },
    deleteTask: deleteTaskMutation.mutate,
    getTaskById: async (taskId: string) => {
      // For individual task fetching, we'll use the API directly
      // since React Query's useTaskById is a hook and can't be called conditionally
      const { apiRequest } = await import('@/lib/api')
      return apiRequest(`/api/tasks/${taskId}`)
    },
    
    // Refresh function
    refresh: () => {
      kanbanQuery.refetch()
    }
  }
}

// Re-export types and functions for direct import
import {
  useKanbanTasks,
  useCurrentTask,
  useCreateTask,
  useUpdateTask,
  useDeleteTask,
  formatStatusName,
  getStatusColor
} from './useNovaQueries'