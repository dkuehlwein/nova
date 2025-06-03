import { useState, useEffect } from 'react';
import { apiRequest, API_ENDPOINTS } from '@/lib/api';

export interface Task {
  id: string;
  title: string;
  description: string;
  summary?: string;
  status: string;
  created_at: string;
  updated_at: string;
  due_date?: string;
  completed_at?: string;
  tags: string[];
  needs_decision: boolean;
  decision_type?: string;
  persons: string[];
  projects: string[];
  comments_count: number;
}

interface TasksByStatus {
  [status: string]: Task[];
}

export function useKanban() {
  const [tasksByStatus, setTasksByStatus] = useState<TasksByStatus>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchKanbanData = async () => {
    try {
      setLoading(true);
      const result = await apiRequest<TasksByStatus>(API_ENDPOINTS.tasksByStatus);
      setTasksByStatus(result);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch kanban data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
      
      // Fallback to empty data structure
      setTasksByStatus({
        new: [],
        user_input_received: [],
        needs_review: [],
        waiting: [],
        in_progress: [],
        done: [],
        failed: []
      });
    } finally {
      setLoading(false);
    }
  };

  const updateTaskStatus = async (taskId: string, newStatus: string) => {
    try {
      await apiRequest(API_ENDPOINTS.taskById(taskId), {
        method: 'PUT',
        body: JSON.stringify({ status: newStatus }),
      });

      // Refresh data after update
      await fetchKanbanData();
    } catch (err) {
      console.error('Failed to update task status:', err);
      throw err;
    }
  };

  const createTask = async (taskData: {
    title: string;
    description: string;
    status?: string;
    due_date?: string;
    tags?: string[];
    person_ids?: string[];
    project_ids?: string[];
  }) => {
    try {
      const result = await apiRequest(API_ENDPOINTS.tasks, {
        method: 'POST',
        body: JSON.stringify(taskData),
      });

      // Refresh data after creation
      await fetchKanbanData();
      return result;
    } catch (err) {
      console.error('Failed to create task:', err);
      throw err;
    }
  };

  const deleteTask = async (taskId: string) => {
    try {
      await apiRequest(API_ENDPOINTS.taskById(taskId), {
        method: 'DELETE',
      });

      // Refresh data after deletion
      await fetchKanbanData();
    } catch (err) {
      console.error('Failed to delete task:', err);
      throw err;
    }
  };

  const getTaskById = async (taskId: string): Promise<Task> => {
    try {
      return await apiRequest<Task>(API_ENDPOINTS.taskById(taskId));
    } catch (err) {
      console.error('Failed to fetch task:', err);
      throw err;
    }
  };

  useEffect(() => {
    fetchKanbanData();
  }, []);

  // Helper to get current task (first in_progress task)
  const getCurrentTask = (): Task | null => {
    const inProgressTasks = tasksByStatus.in_progress || [];
    return inProgressTasks.length > 0 ? inProgressTasks[0] : null;
  };

  // Helper to format status names for display
  const formatStatusName = (status: string): string => {
    return status.replace(/_/g, ' ').toUpperCase();
  };

  // Helper to get status color
  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'new': return 'bg-blue-500';
      case 'user_input_received': return 'bg-green-500';
      case 'needs_review': return 'bg-red-500';
      case 'waiting': return 'bg-orange-500';
      case 'in_progress': return 'bg-purple-500';
      case 'done': return 'bg-gray-500';
      case 'failed': return 'bg-red-700';
      default: return 'bg-gray-500';
    }
  };

  return {
    tasksByStatus,
    loading,
    error,
    getCurrentTask,
    formatStatusName,
    getStatusColor,
    updateTaskStatus,
    createTask,
    deleteTask,
    getTaskById,
    refresh: fetchKanbanData,
  };
} 