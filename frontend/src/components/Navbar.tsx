import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Brain, 
  MessageSquare, 
  KanbanSquare, 
  Settings, 
  AlertTriangle,
  CheckCircle,
  Clock,
  PlayCircle,
  InboxIcon,
  UserCheck,
  Eye,
  HourglassIcon,
  XCircle
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useOverview } from "@/hooks/useOverview";

export default function Navbar() {
  const pathname = usePathname();
  const { data, loading, currentTask } = useOverview();

  const isActive = (path: string) => pathname === path;

  if (loading || !data) {
    return (
      <nav className="border-b border-border bg-card">
        <div className="flex h-16 items-center px-6">
          <Link href="/" className="flex items-center space-x-2">
            <Brain className="h-8 w-8 text-primary" />
            <h1 className="text-2xl font-bold text-foreground">Nova</h1>
          </Link>
          <div className="ml-8 text-muted-foreground">Loading...</div>
        </div>
      </nav>
    );
  }

  const pendingDecisions = data.task_counts.NEEDS_REVIEW || 0;

  return (
    <div className="border-b border-border bg-card">
      {/* Top Bar - Lane Counts */}
      <div className="border-b border-border bg-muted/20 px-6 py-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-6 text-sm">
            {/* New */}
            <div className="flex items-center space-x-1">
              <InboxIcon className="h-4 w-4 text-blue-500" />
              <span className="text-muted-foreground">New</span>
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data.task_counts.NEW || 0}
              </Badge>
            </div>
            
            {/* User Input Received */}
            <div className="flex items-center space-x-1">
              <UserCheck className="h-4 w-4 text-green-500" />
              <span className="text-muted-foreground">User Input Received</span>
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data.task_counts.USER_INPUT_RECEIVED || 0}
              </Badge>
            </div>
            
            {/* Needs Review */}
            <div className="flex items-center space-x-1">
              <Eye className="h-4 w-4 text-red-500" />
              <span className="text-muted-foreground">Needs Review</span>
              <Badge variant="destructive" className="text-xs px-1 py-0">
                {data.task_counts.NEEDS_REVIEW || 0}
              </Badge>
            </div>
            
            {/* Waiting */}
            <div className="flex items-center space-x-1">
              <HourglassIcon className="h-4 w-4 text-orange-500" />
              <span className="text-muted-foreground">Waiting</span>
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data.task_counts.WAITING || 0}
              </Badge>
            </div>
            
            {/* In Progress */}
            <div className="flex items-center space-x-1">
              <PlayCircle className="h-4 w-4 text-yellow-500" />
              <span className="text-muted-foreground">In Progress</span>
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data.task_counts.IN_PROGRESS || 0}
              </Badge>
            </div>
            
            {/* Done */}
            <div className="flex items-center space-x-1">
              <CheckCircle className="h-4 w-4 text-gray-500" />
              <span className="text-muted-foreground">Done</span>
              <Badge variant="outline" className="text-xs px-1 py-0">
                {data.task_counts.DONE || 0}
              </Badge>
            </div>
            
            {/* Failed */}
            {(data.task_counts.FAILED || 0) > 0 && (
              <div className="flex items-center space-x-1">
                <XCircle className="h-4 w-4 text-red-600" />
                <span className="text-muted-foreground">Failed</span>
                <Badge variant="destructive" className="text-xs px-1 py-0">
                  {data.task_counts.FAILED}
                </Badge>
              </div>
            )}
          </div>
          
          {/* Agent Status */}
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm text-muted-foreground">
                {data.system_status}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Middle Bar - Current Working Task */}
      {currentTask && (
        <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border-b border-yellow-500/20 px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <PlayCircle className="h-5 w-5 text-yellow-500" />
              <span className="text-sm text-muted-foreground">Currently working on:</span>
              <span className="text-sm font-medium text-foreground max-w-[400px] truncate">
                {currentTask.title}
              </span>
              <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-700 text-xs">
                {currentTask.assignee}
              </Badge>
            </div>
            
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="text-xs">
                {currentTask.priority} priority
              </Badge>
              <Button size="sm" variant="outline" asChild>
                <Link href="/kanban">View Details</Link>
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Main Navigation Bar */}
      <nav className="px-6">
        <div className="flex h-16 items-center">
          {/* Logo and Brand */}
          <Link href="/" className="flex items-center space-x-2">
            <Brain className="h-8 w-8 text-primary" />
            <h1 className="text-2xl font-bold text-foreground">Nova</h1>
          </Link>

          {/* Main Navigation */}
          <div className="ml-8 flex items-center space-x-1">
            <Link href="/">
              <Button 
                variant={isActive("/") ? "secondary" : "ghost"} 
                size="sm"
                className="flex items-center space-x-2"
              >
                <div className="flex items-center space-x-1">
                  <span>Overview</span>
                  {pendingDecisions > 0 && (
                    <Badge variant="destructive" className="text-xs px-1 py-0 min-w-[16px] h-4">
                      {pendingDecisions}
                    </Badge>
                  )}
                </div>
              </Button>
            </Link>

            <Link href="/chat">
              <Button 
                variant={isActive("/chat") ? "secondary" : "ghost"} 
                size="sm"
                className="flex items-center space-x-2"
              >
                <MessageSquare className="h-4 w-4" />
                <span>Chat</span>
              </Button>
            </Link>

            <Link href="/kanban">
              <Button 
                variant={isActive("/kanban") ? "secondary" : "ghost"} 
                size="sm"
                className="flex items-center space-x-2"
              >
                <KanbanSquare className="h-4 w-4" />
                <span>Tasks</span>
                <Badge variant="outline" className="text-xs px-1 py-0">
                  {data.total_tasks}
                </Badge>
              </Button>
            </Link>

            <Link href="/settings">
              <Button 
                variant={isActive("/settings") ? "secondary" : "ghost"} 
                size="sm"
                className="flex items-center space-x-2"
              >
                <Settings className="h-4 w-4" />
                <span>Settings</span>
              </Button>
            </Link>
          </div>

          {/* Right side - Awaiting Input Alert */}
          <div className="ml-auto">
            {pendingDecisions > 0 && (
              <Link href="/">
                <div className="flex items-center space-x-2 px-3 py-1 bg-red-500/10 border border-red-500/20 rounded-md cursor-pointer hover:bg-red-500/20 transition-colors">
                  <AlertTriangle className="h-4 w-4 text-red-500" />
                  <span className="text-sm text-red-500 font-medium">
                    Awaiting Input
                  </span>
                  <Badge variant="destructive" className="text-xs px-1 py-0 h-4">
                    {pendingDecisions}
                  </Badge>
                </div>
              </Link>
            )}
          </div>
        </div>
      </nav>
    </div>
  );
} 