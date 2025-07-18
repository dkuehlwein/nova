"use client";

import Navbar from "@/components/Navbar";
import { Plus, Calendar, Trash2, FileText, MessageCircle, Activity, Edit2, Check, X, MessageSquare } from "lucide-react";
import { MarkdownMessage } from "@/components/MarkdownMessage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";

import { useKanbanTasks, useCreateTask, useDeleteTask, formatStatusName, getStatusColor, type Task } from "@/hooks/useKanban";
import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

interface Lane {
  id: string;
  title: string;
  color: string;
  tasks: Task[];
}

interface CreateTaskData {
  title: string;
  description: string;
  tags: string[];
}

interface ActivityItem {
  id?: string;
  type?: string;
  title?: string;
  description: string;
  time: string;
  timestamp: string;
  related_task_id?: string;
  itemType: 'activity' | 'comment';
  author?: string;
  content?: string;
}

interface Comment {
  id: string;
  content: string;
  author: string;
  created_at: string;
  task_id: string;
}

interface Activity {
  id: string;
  type: string;
  title: string;
  description: string;
  timestamp: string;
  related_task_id?: string;
  author?: string;
}

function KanbanPage() {
  const { data: tasksByStatus, isLoading: loading, error } = useKanbanTasks()
  const createTaskMutation = useCreateTask()
  const deleteTaskMutation = useDeleteTask()

  const searchParams = useSearchParams();
  const router = useRouter();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isTaskDetailOpen, setIsTaskDetailOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [urlTaskProcessed, setUrlTaskProcessed] = useState(false);
  const [newTask, setNewTask] = useState<CreateTaskData>({
    title: '',
    description: '',
    tags: []
  });
  const [taskComments, setTaskComments] = useState<Comment[]>([]);
  const [taskActivity, setTaskActivity] = useState<Activity[]>([]);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [isEditingDescription, setIsEditingDescription] = useState(false);
  const [editedTitle, setEditedTitle] = useState('');
  const [editedDescription, setEditedDescription] = useState('');

  const handleTaskClick = useCallback(async (task: Task) => {
    try {
      // Fetch latest task details
      const { apiRequest } = await import('@/lib/api')
      const taskDetails = await apiRequest<Task>(`/api/tasks/${task.id}`)
      setSelectedTask(taskDetails);
      
      // Fetch comments and activity
      await Promise.all([
        fetchTaskComments(task.id),
        fetchTaskActivity(task.id)
      ]);
      
      setIsTaskDetailOpen(true);
    } catch (err) {
      console.error('Failed to fetch task details:', err);
      // Fallback to using the task data we already have
      setSelectedTask(task);
      setTaskComments([]);
      setTaskActivity([]);
      setIsTaskDetailOpen(true);
    }
  }, []);

  // Handle URL task parameter to auto-open task dialog
  useEffect(() => {
    const taskId = searchParams.get('task');
    if (taskId && !loading && !urlTaskProcessed) {
      // Properly load the full task data using handleTaskClick
      handleTaskClick({ id: taskId } as Task);
      setUrlTaskProcessed(true);
    }
  }, [searchParams, loading, urlTaskProcessed, handleTaskClick]);

  // Convert API data to lanes format
  const lanes: Lane[] = Object.entries(tasksByStatus || {}).map(([status, tasks]) => ({
    id: status,
    title: formatStatusName(status),
    color: getStatusColor(status),
    tasks: tasks || []
  }));

  const handleCreateTask = async () => {
    if (!newTask.title.trim()) return;
    
    try {
      setIsCreating(true);
      await createTaskMutation.mutateAsync({
        title: newTask.title,
        description: newTask.description,
        status: 'new', // Always create tasks in "new" status
        tags: newTask.tags
      });
      
      // Reset form and close dialog
      setNewTask({
        title: '',
        description: '',
        tags: []
      });
      setIsCreateDialogOpen(false);
      
      // Reset URL processing flag to allow future URL-based task openings
      setUrlTaskProcessed(false);
    } catch (err) {
      console.error('Failed to create task:', err);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      setIsDeleting(taskId);
      await deleteTaskMutation.mutateAsync(taskId);
      
      // Reset URL processing flag to allow future URL-based task openings
      setUrlTaskProcessed(false);
      
      // If we're deleting the currently viewed task, close the dialog
      if (selectedTask && selectedTask.id === taskId) {
        handleTaskDetailClose(false);
      }
    } catch (err) {
      console.error('Failed to delete task:', err);
    } finally {
      setIsDeleting(null);
    }
  };

  const handleTaskChat = (task: Task, e: React.MouseEvent) => {
    e.stopPropagation();
    // Navigate to chat page with the task's core agent thread
    const threadId = `core_agent_task_${task.id}`;
    router.push(`/chat?thread=${threadId}&task=${task.id}`);
  };

  const fetchTaskComments = async (taskId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/tasks/${taskId}/comments`);
      if (response.ok) {
        const comments = await response.json();
        setTaskComments(comments);
      }
    } catch (err) {
      console.error('Failed to fetch comments:', err);
      setTaskComments([]);
    }
  };

  const fetchTaskActivity = async (taskId: string) => {
    try {
      // Get general activity for this task
      const response = await fetch(`http://localhost:8000/api/recent-activity`);
      
      if (response.ok) {
        const allActivity = await response.json();
        // Filter activity for this specific task
        const filteredActivity = allActivity.filter((activity: ActivityItem) => 
          activity.related_task_id === taskId
        );
        setTaskActivity(filteredActivity);
      } else {
        setTaskActivity([]);
      }
    } catch (err) {
      console.error('Failed to fetch activity:', err);
      setTaskActivity([]);
    }
  };

  const getTimeAgo = (timestamp: string) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diffInSeconds = Math.floor((now.getTime() - time.getTime()) / 1000);
    
    if (diffInSeconds < 60) return 'Just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`;
    return `${Math.floor(diffInSeconds / 86400)} days ago`;
  };

  const handleTagInput = (value: string) => {
    const tags = value.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0);
    setNewTask(prev => ({ ...prev, tags }));
  };

  const handleSaveTitle = async () => {
    if (!selectedTask || !editedTitle.trim()) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/tasks/${selectedTask.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: editedTitle.trim()
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to update title');
      }
      
      // Update the selected task
      setSelectedTask({ ...selectedTask, title: editedTitle.trim() });
      setIsEditingTitle(false);
      
      // Refresh the activity to show the edit
      fetchTaskActivity(selectedTask.id);
    } catch (err) {
      console.error('Failed to update title:', err);
    }
  };

  const handleSaveDescription = async () => {
    if (!selectedTask) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/tasks/${selectedTask.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          description: editedDescription.trim()
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to update description');
      }
      
      // Update the selected task
      setSelectedTask({ ...selectedTask, description: editedDescription.trim() });
      setIsEditingDescription(false);
      
      // Refresh the activity to show the edit
      fetchTaskActivity(selectedTask.id);
    } catch (err) {
      console.error('Failed to update description:', err);
    }
  };

  const startEditingTitle = () => {
    if (selectedTask) {
      setEditedTitle(selectedTask.title);
      setIsEditingTitle(true);
    }
  };

  const startEditingDescription = () => {
    if (selectedTask) {
      setEditedDescription(selectedTask.description || '');
      setIsEditingDescription(true);
    }
  };

  const cancelEditingTitle = () => {
    setIsEditingTitle(false);
    setEditedTitle('');
  };

  const cancelEditingDescription = () => {
    setIsEditingDescription(false);
    setEditedDescription('');
  };

  const TaskCard = ({ task }: { task: Task }) => (
    <div 
      className="bg-card border border-border rounded-lg p-4 mb-3 cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => handleTaskClick(task)}
    >
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-medium text-foreground text-sm">{task.title}</h4>
        <div className="flex items-center space-x-1">
          <Button 
            variant="ghost" 
            size="sm" 
            className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground hover:bg-muted"
            onClick={(e) => handleTaskChat(task, e)}
            title="Open chat with Nova about this task"
          >
            <MessageCircle className="h-3 w-3" />
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button 
                variant="ghost" 
                size="sm" 
                className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground hover:bg-muted"
                onClick={(e) => e.stopPropagation()}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent onClick={(e) => e.stopPropagation()}>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Task</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete &quot;{task.title}&quot;? This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction 
                  onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    handleDeleteTask(task.id);
                  }}
                  disabled={isDeleting === task.id}
                  className="bg-red-600 hover:bg-red-700"
                >
                  {isDeleting === task.id ? 'Deleting...' : 'Delete'}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
      
      <div className="text-xs text-muted-foreground mb-3 line-clamp-2">
        <MarkdownMessage content={task.description || ''} className="text-xs" />
      </div>

      <div className="flex flex-wrap gap-1 mb-3">
        {(task.tags || []).map((tag: string) => (
          <Badge key={tag} variant="secondary" className="text-xs px-1 py-0">
            {tag}
          </Badge>
        ))}
      </div>

      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1">
            <Calendar className="h-3 w-3" />
            <span className="text-muted-foreground">
              {task.completed_at 
                ? new Date(task.completed_at).toLocaleDateString()
                : task.due_date 
                  ? new Date(task.due_date).toLocaleDateString()
                  : new Date(task.updated_at).toLocaleDateString()
              }
            </span>
          </div>
        </div>
      </div>


    </div>
  );

  // Handle dialog close to clean up URL
  const handleTaskDetailClose = (open: boolean) => {
    setIsTaskDetailOpen(open);
    if (!open) {
      setSelectedTask(null);
      // Clean up URL parameter when dialog is closed
      const currentParams = new URLSearchParams(window.location.search);
      if (currentParams.has('task')) {
        currentParams.delete('task');
        const newUrl = currentParams.toString() ? 
          `${window.location.pathname}?${currentParams.toString()}` : 
          window.location.pathname;
        router.replace(newUrl);
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <div className="text-muted-foreground">Loading kanban board...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <div className="text-red-500">Error loading kanban board: {error.message}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      
      <main className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Kanban Board</h1>
            <p className="text-sm text-muted-foreground">
              Manage your tasks across different stages
            </p>
          </div>
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button className="flex items-center space-x-2">
                <Plus className="h-4 w-4" />
                <span>Add Task</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Create New Task</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    value={newTask.title}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewTask(prev => ({ ...prev, title: e.target.value }))}
                    placeholder="Enter task title..."
                  />
                </div>
                <div>
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={newTask.description}
                    onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNewTask(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Enter task description..."
                    rows={3}
                  />
                </div>
                <div>
                  <Label htmlFor="tags">Tags (comma-separated)</Label>
                  <Input
                    id="tags"
                    value={newTask.tags.join(', ')}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleTagInput(e.target.value)}
                    placeholder="tag1, tag2, tag3..."
                  />
                </div>
                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateTask} disabled={!newTask.title.trim() || isCreating}>
                    {isCreating ? 'Creating...' : 'Create Task'}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Task Detail Dialog */}
        <Dialog open={isTaskDetailOpen} onOpenChange={handleTaskDetailClose}>
          <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
            {selectedTask && (
              <div className="space-y-4">
                <DialogHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                    {isEditingTitle ? (
                      <div className="flex items-center space-x-2 mb-2">
                        <Input
                          value={editedTitle}
                          onChange={(e) => setEditedTitle(e.target.value)}
                          className="text-xl font-bold"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleSaveTitle();
                            } else if (e.key === 'Escape') {
                              cancelEditingTitle();
                            }
                          }}
                          autoFocus
                        />
                        <Button size="sm" onClick={handleSaveTitle} disabled={!editedTitle.trim()}>
                          <Check className="h-4 w-4" />
                        </Button>
                        <Button size="sm" variant="outline" onClick={cancelEditingTitle}>
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2 mb-2 group">
                        <DialogTitle className="text-xl font-bold text-foreground">{selectedTask.title}</DialogTitle>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={startEditingTitle}
                          className="opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                    <div className="flex items-center gap-3 text-xs text-muted-foreground mb-2">
                      <span>Created {new Date(selectedTask.created_at).toLocaleDateString()}</span>
                      <span>•</span>
                      <span>Updated {new Date(selectedTask.updated_at).toLocaleDateString()}</span>
                      {(selectedTask.due_date || selectedTask.completed_at) && (
                        <>
                          <span>•</span>
                          <span>
                            {selectedTask.completed_at ? 'Completed' : 'Due'}: {' '}
                            {selectedTask.completed_at 
                              ? new Date(selectedTask.completed_at).toLocaleDateString()
                              : selectedTask.due_date 
                                ? new Date(selectedTask.due_date).toLocaleDateString()
                                : 'Not set'
                            }
                          </span>
                        </>
                      )}
                    </div>
                    {/* Tags in header */}
                    {selectedTask.tags && selectedTask.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {selectedTask.tags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs h-5">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col items-end space-y-2">
                    <div className="flex items-center space-x-2">
                      <div className={`w-3 h-3 rounded-full ${getStatusColor(selectedTask.status)}`}></div>
                      <Badge variant="secondary" className="text-sm font-medium">
                        {formatStatusName(selectedTask.status)}
                      </Badge>
                    </div>
                    {/* Related entities in header */}
                    {selectedTask.projects && selectedTask.projects.length > 0 && (
                      <div className="flex flex-col items-end space-y-1">
                        <div className="text-xs text-muted-foreground">
                          {selectedTask.projects.slice(0, 1).join(', ')}
                          {selectedTask.projects.length > 1 && ` +${selectedTask.projects.length - 1}`}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                </DialogHeader>

                {/* Description */}
                <div className="bg-muted/30 border border-border rounded-lg p-4 group">
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-sm font-medium text-muted-foreground">Description</Label>
                    {!isEditingDescription && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={startEditingDescription}
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Edit2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                  {isEditingDescription ? (
                    <div className="space-y-2">
                      <Textarea
                        value={editedDescription}
                        onChange={(e) => setEditedDescription(e.target.value)}
                        className="min-h-[100px] resize-none"
                        placeholder="Enter task description..."
                        onKeyDown={(e) => {
                          if (e.key === 'Escape') {
                            cancelEditingDescription();
                          }
                        }}
                        autoFocus
                      />
                      <div className="flex items-center space-x-2">
                        <Button size="sm" onClick={handleSaveDescription}>
                          <Check className="h-4 w-4 mr-1" />
                          Save
                        </Button>
                        <Button size="sm" variant="outline" onClick={cancelEditingDescription}>
                          <X className="h-4 w-4 mr-1" />
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-foreground leading-relaxed">
                      <MarkdownMessage content={selectedTask.description || 'No description provided.'} className="text-sm" />
                    </div>
                  )}
                </div>

                {/* Summary (if exists) */}
                {selectedTask.summary && (
                  <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                    <Label className="text-sm font-medium text-foreground mb-2 block flex items-center">
                      <FileText className="h-3 w-3 mr-2" />
                      Summary
                    </Label>
                    <div className="text-sm text-foreground leading-relaxed">
                      <MarkdownMessage content={selectedTask.summary} className="text-sm" />
                    </div>
                  </div>
                )}

                {/* Activity & Comments Section */}
                <div className="bg-card border border-border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <Label className="text-base font-semibold text-foreground flex items-center">
                      <Activity className="h-4 w-4 mr-2" />
                      Activity & Comments ({taskComments.length + taskActivity.filter(a => a.type !== 'comment_added').length})
                    </Label>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={e => handleTaskChat(selectedTask, e)}
                      className="hover:bg-muted rounded-full"
                      aria-label="Open chat for this task"
                    >
                      <MessageSquare className="h-5 w-5 text-primary" />
                    </Button>
                  </div>
                  
                  {/* Combined Activity and Comments Timeline */}
                  {(() => {
                    // Combine and sort all activity items
                    const allActivity: ActivityItem[] = [];
                    
                    // Add non-comment activities
                    taskActivity.filter(a => a.type !== 'comment_added').forEach(activity => {
                      allActivity.push({
                        ...activity,
                        itemType: 'activity' as const,
                        description: activity.description || activity.title || 'Activity',
                        time: getTimeAgo(activity.timestamp)
                      });
                    });
                    
                    // Add comments as activity items
                    taskComments.forEach(comment => {
                      allActivity.push({
                        id: comment.id,
                        timestamp: comment.created_at,
                        itemType: 'comment' as const,
                        author: comment.author,
                        content: comment.content,
                        description: `Comment by ${comment.author === 'user' ? 'You' : 'Nova'}`,
                        time: getTimeAgo(comment.created_at)
                      });
                    });
                    
                    // Sort by timestamp (most recent first)
                    allActivity.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
                    
                    return allActivity.length > 0 ? (
                      <div className="space-y-3 mb-4">
                        {allActivity.map((item, index) => (
                          <div key={`${item.itemType}-${item.id || index}`} className="border-l-2 border-muted pl-4 py-2">
                            {item.itemType === 'comment' ? (
                              // Comment display
                              <>
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center space-x-2">
                                    <MessageCircle className="h-3 w-3 text-muted-foreground" />
                                    <span className="text-sm font-medium text-foreground">
                                      {item.author === 'user' ? 'You' : 'Nova'} commented
                                    </span>
                                  </div>
                                  <span className="text-xs text-muted-foreground">
                                    {item.time}
                                  </span>
                                </div>
                                <div className="text-sm text-foreground leading-relaxed">
                                  <MarkdownMessage content={item.content || ''} className="text-sm" />
                                </div>
                              </>
                            ) : (
                              // Activity display
                              <>
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center space-x-2">
                                    <Activity className="h-3 w-3 text-muted-foreground" />
                                    <span className="text-sm font-medium text-foreground">
                                      {item.description}
                                    </span>
                                  </div>
                                  <span className="text-xs text-muted-foreground">
                                    {item.time}
                                  </span>
                                </div>
                              </>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground mb-4">No activity yet</div>
                    );
                  })()}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        <div className="grid grid-cols-1 lg:grid-cols-7 gap-6">
          {lanes.map((lane) => (
            <div key={lane.id} className="bg-card border border-border rounded-lg">
              <div className="p-4 border-b border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className={`w-3 h-3 rounded-full ${lane.color}`}></div>
                    <h3 className="font-semibold text-sm text-foreground">{lane.title}</h3>
                  </div>
                  <Badge variant="secondary" className="text-xs">
                    {lane.tasks.length}
                  </Badge>
                </div>
              </div>
              
              <div className="p-4 space-y-3">
                {lane.tasks.map((task) => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

export default function KanbanPageWithSuspense() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <div className="text-muted-foreground">Loading kanban board...</div>
        </div>
      </div>
    }>
      <KanbanPage />
    </Suspense>
  );
} 