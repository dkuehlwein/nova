import { useState, useEffect, useCallback } from 'react';
import { apiRequest, API_ENDPOINTS } from '@/lib/api';

interface TaskCounts {
  NEW: number;
  USER_INPUT_RECEIVED: number;
  NEEDS_REVIEW: number;
  WAITING: number;
  IN_PROGRESS: number;
  DONE: number;
  FAILED: number;
}

// API response format (lowercase with underscores)
interface ApiTaskCounts {
  new: number;
  user_input_received: number;
  needs_review: number;
  waiting: number;
  in_progress: number;
  done: number;
  failed: number;
}

interface ActivityItem {
  type: string;
  title: string;
  description: string;
  time: string;
  timestamp: string;
  related_task_id?: string;
  related_chat_id?: string;
}

interface CurrentTask {
  id: string;
  title: string;
  priority: string;
}

interface OverviewData {
  task_counts: TaskCounts;
  total_tasks: number;
  pending_decisions: number;
  recent_activity: ActivityItem[];
  system_status: string;
}

interface ApiOverviewResponse {
  task_counts: ApiTaskCounts;
  total_tasks: number;
  pending_decisions: number;
  recent_activity: ActivityItem[];
  system_status: string;
}

interface TasksByStatusResponse {
  in_progress: Array<{
    id: string;
    title: string;
    persons?: string[];
  }>;
  [key: string]: Array<{
    id: string;
    title: string;
    persons?: string[];
  }>;
}

// Function to transform API response to frontend format
const transformTaskCounts = (apiCounts: ApiTaskCounts): TaskCounts => ({
  NEW: apiCounts.new || 0,
  USER_INPUT_RECEIVED: apiCounts.user_input_received || 0,
  NEEDS_REVIEW: apiCounts.needs_review || 0,
  WAITING: apiCounts.waiting || 0,
  IN_PROGRESS: apiCounts.in_progress || 0,
  DONE: apiCounts.done || 0,
  FAILED: apiCounts.failed || 0,
});

export function useOverview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentTask, setCurrentTask] = useState<CurrentTask | null>(null);

  const fetchCurrentTask = async () => {
    try {
      const tasksByStatus = await apiRequest<TasksByStatusResponse>(API_ENDPOINTS.tasksByStatus);
      const inProgressTasks = tasksByStatus.in_progress || [];
      
      if (inProgressTasks.length > 0) {
        const task = inProgressTasks[0];
        setCurrentTask({
          id: task.id,
          title: task.title,
          priority: 'high' // Could be derived from task data if needed
        });
      } else {
        setCurrentTask(null);
      }
    } catch (err) {
      console.error('Failed to fetch current task:', err);
      setCurrentTask(null);
    }
  };

  const fetchOverview = useCallback(async () => {
    try {
      setLoading(true);
      const apiResult: ApiOverviewResponse = await apiRequest<ApiOverviewResponse>(API_ENDPOINTS.overview);
      
      // Transform API response to frontend format
      const transformedData: OverviewData = {
        ...apiResult,
        task_counts: transformTaskCounts(apiResult.task_counts),
      };
      
      setData(transformedData);
      
      // Fetch current task details from kanban API
      await fetchCurrentTask();
      
      setError(null);
    } catch (err) {
      console.error('Failed to fetch overview data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
      
      // Fallback to mock data for development
      setData({
        task_counts: {
          NEW: 5,
          USER_INPUT_RECEIVED: 2,
          NEEDS_REVIEW: 3,
          WAITING: 4,
          IN_PROGRESS: 1,
          DONE: 24,
          FAILED: 0
        },
        total_tasks: 39,
        pending_decisions: 5,
        recent_activity: [],
        system_status: 'operational'
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
    
    // Refresh every 30 seconds for real-time updates
    const interval = setInterval(fetchOverview, 30000);
    
    return () => clearInterval(interval);
  }, [fetchOverview]);

  // Calculate derived values
  const activeTasks = data ? 
    data.task_counts.NEW + 
    data.task_counts.USER_INPUT_RECEIVED + 
    data.task_counts.NEEDS_REVIEW + 
    data.task_counts.WAITING + 
    data.task_counts.IN_PROGRESS : 0;

  return {
    data,
    loading,
    error,
    currentTask,
    activeTasks,
    refresh: fetchOverview
  };
} 