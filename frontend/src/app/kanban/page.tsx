"use client";

import Navbar from "@/components/Navbar";
import { Plus, MoreHorizontal, AlertTriangle, Clock, CheckCircle, User, Calendar, PlayCircle, ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Task {
  id: string;
  title: string;
  description: string;
  priority: string;
  assignee: string;
  dueDate: string;
  tags: string[];
  needsDecision?: boolean;
  decisionType?: string;
  completedAt?: string;
}

interface Lane {
  id: string;
  title: string;
  color: string;
  tasks: Task[];
}

export default function KanbanPage() {
  // Mock kanban data - updated to match real task statuses
  const currentTask: Task | null = {
    id: "task-current",
    title: "Implement user dashboard",
    description: "Build the main dashboard with charts and metrics. This includes setting up the React components, integrating with the backend API, and ensuring responsive design across all devices.",
    priority: "high",
    assignee: "Nova AI",
    dueDate: "2024-01-20",
    tags: ["frontend", "dashboard", "react"]
  };

  const lanes: Lane[] = [
    {
      id: "new",
      title: "NEW",
      color: "bg-blue-500",
      tasks: [
        {
          id: "task-1",
          title: "Review quarterly reports",
          description: "Analyze Q4 performance metrics and prepare summary",
          priority: "high",
          assignee: "John Doe",
          dueDate: "2024-01-15",
          tags: ["reports", "analysis"]
        },
        {
          id: "task-2", 
          title: "Update client presentation",
          description: "Incorporate feedback from last meeting",
          priority: "medium",
          assignee: "Jane Smith",
          dueDate: "2024-01-18",
          tags: ["presentation", "client"]
        }
      ]
    },
    {
      id: "user-input-received",
      title: "USER INPUT RECEIVED", 
      color: "bg-green-500",
      tasks: [
        {
          id: "task-3",
          title: "Code review for authentication module",
          description: "Review pull request #234 with user's requested changes",
          priority: "high",
          assignee: "Mike Johnson",
          dueDate: "2024-01-12",
          tags: ["code-review", "security"]
        }
      ]
    },
    {
      id: "needs-review",
      title: "NEEDS REVIEW",
      color: "bg-red-500",
      tasks: [
        {
          id: "task-6",
          title: "Email approval for John Smith",
          description: "Draft email response needs approval before sending",
          priority: "high",
          assignee: "Nova AI",
          dueDate: "2024-01-10",
          tags: ["email", "approval"],
          needsDecision: true,
          decisionType: "email_approval"
        },
        {
          id: "task-7",
          title: "Choose deployment strategy",
          description: "Select between AWS and Azure for new microservice",
          priority: "medium",
          assignee: "DevOps Team",
          dueDate: "2024-01-15", 
          tags: ["deployment", "infrastructure"],
          needsDecision: true,
          decisionType: "strategy_choice"
        }
      ]
    },
    {
      id: "waiting",
      title: "WAITING",
      color: "bg-orange-500",
      tasks: [
        {
          id: "task-8",
          title: "Client feedback on proposal",
          description: "Waiting for client response on project proposal",
          priority: "medium",
          assignee: "Sales Team",
          dueDate: "2024-01-22",
          tags: ["client", "proposal"]
        }
      ]
    },
    {
      id: "done",
      title: "DONE",
      color: "bg-gray-500", 
      tasks: [
        {
          id: "task-9",
          title: "Setup CI/CD pipeline",
          description: "Configured GitHub Actions for automated deployment",
          priority: "high",
          assignee: "DevOps Team",
          dueDate: "2024-01-05",
          tags: ["devops", "automation"],
          completedAt: "2024-01-05"
        },
        {
          id: "task-10",
          title: "User authentication implementation",
          description: "Implemented JWT-based authentication system",
          priority: "high",
          assignee: "Security Team", 
          dueDate: "2024-01-08",
          tags: ["security", "auth"],
          completedAt: "2024-01-07"
        }
      ]
    }
  ];

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high": return "bg-red-500";
      case "medium": return "bg-yellow-500";
      case "low": return "bg-green-500";
      default: return "bg-gray-500";
    }
  };

  const TaskCard = ({ task }: { task: Task }) => (
    <div className="bg-card border border-border rounded-lg p-4 mb-3 cursor-pointer hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-medium text-foreground text-sm">{task.title}</h4>
        <div className="flex items-center space-x-1">
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
            <MoreHorizontal className="h-3 w-3" />
          </Button>
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
          <span className="text-muted-foreground">{task.assignee}</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${getPriorityColor(task.priority)}`}></div>
          <div className="flex items-center space-x-1">
            <Calendar className="h-3 w-3" />
            <span className="text-muted-foreground">
              {task.completedAt || task.dueDate}
            </span>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <div className="p-6">
        <div className="mx-auto max-w-7xl">
          {/* Header */}
          <div className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-foreground mb-1">Task Board</h1>
                <p className="text-muted-foreground">
                  Manage and track your tasks across different stages
                </p>
              </div>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Task
              </Button>
            </div>
          </div>

          {/* Current In-Progress Task - Highlighted Section */}
          {currentTask && (
            <div className="mb-8 bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/20 rounded-lg p-6">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-3">
                    <PlayCircle className="h-6 w-6 text-yellow-500" />
                    <h2 className="text-lg font-semibold text-foreground">Currently Working On</h2>
                    <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-700">
                      In Progress
                    </Badge>
                  </div>
                  
                  <h3 className="text-xl font-medium text-foreground mb-2">{currentTask.title}</h3>
                  <p className="text-muted-foreground mb-4 max-w-3xl">{currentTask.description}</p>
                  
                  <div className="flex items-center space-x-4 text-sm">
                    <div className="flex items-center space-x-1">
                      <User className="h-4 w-4" />
                      <span className="text-muted-foreground">{currentTask.assignee}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <Calendar className="h-4 w-4" />
                      <span className="text-muted-foreground">Due {currentTask.dueDate}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <div className={`w-3 h-3 rounded-full ${getPriorityColor(currentTask.priority)}`}></div>
                      <span className="text-muted-foreground capitalize">{currentTask.priority} priority</span>
                    </div>
                  </div>
                  
                  <div className="flex flex-wrap gap-2 mt-3">
                    {currentTask.tags.map((tag: string) => (
                      <Badge key={tag} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
                
                <div className="flex flex-col space-y-2">
                  <Button size="sm">
                    <ArrowRight className="h-4 w-4 mr-1" />
                    View Details
                  </Button>
                  <Button size="sm" variant="outline">
                    <CheckCircle className="h-4 w-4 mr-1" />
                    Mark Complete
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Kanban Board - Without In Progress Lane */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
            {lanes.map((lane) => (
              <div key={lane.id} className="bg-muted/50 rounded-lg p-4">
                {/* Lane Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-2">
                    <div className={`w-3 h-3 rounded-full ${lane.color}`}></div>
                    <h3 className="font-semibold text-foreground text-sm">
                      {lane.title}
                    </h3>
                    <Badge variant="secondary" className="text-xs">
                      {lane.tasks.length}
                    </Badge>
                  </div>
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                    <Plus className="h-3 w-3" />
                  </Button>
                </div>

                {/* Tasks */}
                <div className="space-y-3 min-h-[400px]">
                  {lane.tasks.map((task) => (
                    <TaskCard key={task.id} task={task} />
                  ))}
                  
                  {/* Drop Zone */}
                  <div className="border-2 border-dashed border-muted-foreground/20 rounded-lg p-4 text-center hover:border-muted-foreground/40 transition-colors">
                    <p className="text-xs text-muted-foreground">
                      Drop tasks here or click + to add
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
} 