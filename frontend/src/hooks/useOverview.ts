import { useState, useEffect } from 'react';

interface TaskCounts {
  NEW: number;
  USER_INPUT_RECEIVED: number;
  NEEDS_REVIEW: number;
  WAITING: number;
  IN_PROGRESS: number;
  DONE: number;
  FAILED: number;
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
  assignee: string;
  priority: string;
}

interface OverviewData {
  task_counts: TaskCounts;
  total_tasks: number;
  pending_decisions: number;
  recent_activity: ActivityItem[];
  system_status: string;
}

export function useOverview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentTask, setCurrentTask] = useState<CurrentTask | null>(null);

  const fetchOverview = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8001/api/overview');
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      setData(result);
      
      // For now, mock the current task since we only have one in progress at a time
      // TODO: Update backend to return current in-progress task details
      if (result.task_counts.IN_PROGRESS > 0) {
        setCurrentTask({
          id: 'current',
          title: 'Implement user dashboard', // This will come from API later
          assignee: 'Nova AI',
          priority: 'high'
        });
      } else {
        setCurrentTask(null);
      }
      
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
  };

  useEffect(() => {
    fetchOverview();
    
    // Refresh every 30 seconds for real-time updates
    const interval = setInterval(fetchOverview, 30000);
    
    return () => clearInterval(interval);
  }, []);

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