"use client";

import Navbar from "@/components/Navbar";
import { Plus, MoreHorizontal, AlertTriangle, User, Calendar, Trash2, Eye, Clock, FileText, MessageCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useKanban, Task } from "@/hooks/useKanban";
import { useState, useEffect } from "react";
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

export default function KanbanPage() {
  const { 
    tasksByStatus, 
    loading, 
    error, 
    formatStatusName, 
    getStatusColor, 
    createTask,
    deleteTask,
    getTaskById
  } = useKanban();

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
  const [commentText, setCommentText] = useState('');
  const [isAddingComment, setIsAddingComment] = useState(false);

  // Handle URL task parameter to auto-open task dialog
  useEffect(() => {
    const taskId = searchParams.get('task');
    if (taskId && !loading && !urlTaskProcessed) {
      handleTaskClick({ id: taskId } as Task);
      setUrlTaskProcessed(true);
    }
  }, [searchParams, loading, urlTaskProcessed]);

  // Convert API data to lanes format
  const lanes: Lane[] = Object.entries(tasksByStatus).map(([status, tasks]) => ({
    id: status,
    title: formatStatusName(status),
    color: getStatusColor(status),
    tasks: tasks || []
  }));

  const handleCreateTask = async () => {
    if (!newTask.title.trim()) return;
    
    try {
      setIsCreating(true);
      await createTask({
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
      await deleteTask(taskId);
      
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

  const handleTaskClick = async (task: Task) => {
    try {
      // Fetch latest task details
      const taskDetails = await getTaskById(task.id);
      setSelectedTask(taskDetails);
      setIsTaskDetailOpen(true);
    } catch (err) {
      console.error('Failed to fetch task details:', err);
      // Fallback to using the task data we already have
      setSelectedTask(task);
      setIsTaskDetailOpen(true);
    }
  };

  const handleTagInput = (value: string) => {
    const tags = value.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0);
    setNewTask(prev => ({ ...prev, tags }));
  };

  const handleAddComment = async () => {
    if (!selectedTask || !commentText.trim()) return;
    
    try {
      setIsAddingComment(true);
      const response = await fetch(`http://localhost:8000/api/tasks/${selectedTask.id}/comments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content: commentText,
          author: 'user'
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to add comment');
      }
      
      // Refresh task details to get updated comment count
      const updatedTask = await getTaskById(selectedTask.id);
      setSelectedTask(updatedTask);
      setCommentText('');
    } catch (err) {
      console.error('Failed to add comment:', err);
    } finally {
      setIsAddingComment(false);
    }
  };

  const TaskCard = ({ task }: { task: Task }) => (
    <div 
      className="bg-card border border-border rounded-lg p-4 mb-3 cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => handleTaskClick(task)}
    >
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-medium text-foreground text-sm">{task.title}</h4>
        <div className="flex items-center space-x-1">
          {task.needs_decision && (
            <AlertTriangle className="h-3 w-3 text-red-500" />
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="ghost" 
                size="sm" 
                className="h-6 w-6 p-0"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                handleTaskClick(task);
              }}>
                <Eye className="h-3 w-3 mr-2" />
                View Details
              </DropdownMenuItem>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <DropdownMenuItem 
                    className="text-red-600"
                    onSelect={(e: Event) => {
                      e.preventDefault();
                    }}
                    onClick={(e: React.MouseEvent) => {
                      e.stopPropagation();
                    }}
                  >
                    <Trash2 className="h-3 w-3 mr-2" />
                    Delete Task
                  </DropdownMenuItem>
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
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      
      <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
        {task.description}
      </p>

      <div className="flex flex-wrap gap-1 mb-3">
        {task.tags.map((tag: string) => (
          <Badge key={tag} variant="secondary" className="text-xs px-1 py-0">
            {tag}
          </Badge>
        ))}
      </div>

      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center space-x-1">
          <User className="h-3 w-3" />
          <span className="text-muted-foreground">
            {task.persons.length > 0 ? task.persons[0] : 'Unassigned'}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          {task.needs_decision && (
            <div className="w-2 h-2 rounded-full bg-red-500"></div>
          )}
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

      {task.needs_decision && (
        <div className="mt-2 pt-2 border-t border-border">
          <div className="flex items-center space-x-1">
            <AlertTriangle className="h-3 w-3 text-red-500" />
            <span className="text-xs text-red-500 font-medium">Decision Required</span>
          </div>
          {task.decision_type && (
            <span className="text-xs text-muted-foreground">
              Type: {task.decision_type.replace('_', ' ')}
            </span>
          )}
        </div>
      )}
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
          <div className="text-red-500">Error loading kanban board: {error}</div>
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
            <DialogHeader className="border-b pb-4">
              <DialogTitle className="text-xl font-semibold">Task Details</DialogTitle>
            </DialogHeader>
            {selectedTask && (
              <div className="space-y-8 py-6">
                {/* Header Section with Status and Key Info */}
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h1 className="text-2xl font-bold text-foreground mb-2">{selectedTask.title}</h1>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center space-x-2">
                        <Calendar className="h-4 w-4" />
                        <span>Created {new Date(selectedTask.created_at).toLocaleDateString()}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Clock className="h-4 w-4" />
                        <span>Updated {new Date(selectedTask.updated_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className={`w-3 h-3 rounded-full ${getStatusColor(selectedTask.status)}`}></div>
                    <Badge variant="secondary" className="text-sm font-medium">
                      {formatStatusName(selectedTask.status)}
                    </Badge>
                  </div>
                </div>

                {/* Description Card */}
                <div className="bg-muted/30 border border-border rounded-lg p-6">
                  <Label className="text-base font-semibold text-foreground mb-3 block">Description</Label>
                  <p className="text-foreground leading-relaxed">
                    {selectedTask.description || 'No description provided.'}
                  </p>
                </div>

                {/* Summary Card (if exists) */}
                {selectedTask.summary && (
                  <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
                    <Label className="text-base font-semibold text-foreground mb-3 block flex items-center">
                      <FileText className="h-4 w-4 mr-2" />
                      Summary
                    </Label>
                    <p className="text-foreground leading-relaxed">
                      {selectedTask.summary}
                    </p>
                  </div>
                )}

                {/* Decision Required Alert */}
                {selectedTask.needs_decision && (
                  <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-6">
                    <div className="flex items-center space-x-3 text-red-700 dark:text-red-300 mb-3">
                      <AlertTriangle className="h-5 w-5" />
                      <span className="font-semibold text-base">Decision Required</span>
                    </div>
                    {selectedTask.decision_type && (
                      <p className="text-sm text-red-600 dark:text-red-400 mb-2">
                        Type: {selectedTask.decision_type.replace('_', ' ')}
                      </p>
                    )}
                    <p className="text-sm text-red-600 dark:text-red-400">
                      This task requires your attention before Nova can continue.
                    </p>
                  </div>
                )}

                {/* Metadata Grid */}
                <div className="grid grid-cols-2 gap-6">
                  {/* Dates */}
                  <div className="space-y-4">
                    {(selectedTask.due_date || selectedTask.completed_at) && (
                      <div className="bg-card border border-border rounded-lg p-4">
                        <Label className="text-sm font-medium text-muted-foreground mb-2 block">
                          {selectedTask.completed_at ? 'Completed' : 'Due Date'}
                        </Label>
                        <div className="flex items-center space-x-2">
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm text-foreground">
                            {selectedTask.completed_at 
                              ? new Date(selectedTask.completed_at).toLocaleDateString()
                              : selectedTask.due_date 
                                ? new Date(selectedTask.due_date).toLocaleDateString()
                                : 'Not set'
                            }
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Tags */}
                  {selectedTask.tags.length > 0 && (
                    <div className="bg-card border border-border rounded-lg p-4">
                      <Label className="text-sm font-medium text-muted-foreground mb-3 block">Tags</Label>
                      <div className="flex flex-wrap gap-2">
                        {selectedTask.tags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Related Entities */}
                {(selectedTask.persons.length > 0 || selectedTask.projects.length > 0) && (
                  <div className="bg-card border border-border rounded-lg p-6">
                    <Label className="text-base font-semibold text-foreground mb-4 block">Related Entities</Label>
                    <div className="grid grid-cols-1 gap-4">
                      {selectedTask.persons.length > 0 && (
                        <div>
                          <Label className="text-sm font-medium text-muted-foreground mb-2 block">People</Label>
                          <div className="flex flex-wrap gap-2">
                            {selectedTask.persons.map((person) => (
                              <Badge key={person} variant="outline" className="flex items-center space-x-2 px-3 py-1">
                                <User className="h-3 w-3" />
                                <span>{person}</span>
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedTask.projects.length > 0 && (
                        <div>
                          <Label className="text-sm font-medium text-muted-foreground mb-2 block">Projects</Label>
                          <div className="flex flex-wrap gap-2">
                            {selectedTask.projects.map((project) => (
                              <Badge key={project} variant="outline" className="px-3 py-1">
                                {project}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Comments Section */}
                <div className="bg-card border border-border rounded-lg p-6">
                  <Label className="text-base font-semibold text-foreground mb-4 block">Comments</Label>
                  
                  {/* Comment Count Status */}
                  <div className="mb-4">
                    {selectedTask.comments_count > 0 ? (
                      <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                        <MessageCircle className="h-4 w-4" />
                        <span>{selectedTask.comments_count} comment{selectedTask.comments_count !== 1 ? 's' : ''}</span>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                        <MessageCircle className="h-4 w-4" />
                        <span>No comments yet</span>
                      </div>
                    )}
                  </div>

                  {/* Add Comment */}
                  <div className="border-t pt-4">
                    <Label className="text-sm font-medium text-foreground mb-2 block">Add a comment</Label>
                    <div className="space-y-3">
                      <Textarea
                        placeholder="Share your thoughts, updates, or questions about this task..."
                        className="min-h-[80px] resize-none"
                        rows={3}
                        value={commentText}
                        onChange={(e) => setCommentText(e.target.value)}
                      />
                      <div className="flex justify-end">
                        <Button 
                          size="sm" 
                          className="px-6"
                          onClick={handleAddComment}
                          disabled={!commentText.trim() || isAddingComment}
                        >
                          <MessageCircle className="h-4 w-4 mr-2" />
                          {isAddingComment ? 'Adding...' : 'Add Comment'}
                        </Button>
                      </div>
                    </div>
                  </div>
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