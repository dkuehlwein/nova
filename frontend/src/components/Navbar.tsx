import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Brain, 
  MessageSquare, 
  KanbanSquare, 
  Settings, 
  CheckCircle,
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
    <nav className="border-b border-border bg-card">
      <div className="flex h-20 items-center px-6">
        {/* Left Section - Logo and Navigation */}
        <div className="flex items-center space-x-8">
          {/* Logo and Brand */}
          <Link href="/" className="flex items-center space-x-2">
            <Brain className="h-8 w-8 text-primary" />
            <h1 className="text-2xl font-bold text-foreground">Nova</h1>
          </Link>

          {/* Main Navigation */}
          <div className="flex items-center space-x-1">
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
        </div>

        {/* Center Section - Current Working Task */}
        <div className="flex-1 flex justify-center px-4">
          {currentTask ? (
            <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/20 rounded-lg px-4 py-2 max-w-lg">
              <div className="flex items-center space-x-2">
                <PlayCircle className="h-4 w-4 text-yellow-500 flex-shrink-0" />
                <span className="text-xs text-muted-foreground">Working on:</span>
                <span className="text-sm font-medium text-foreground truncate">
                  {currentTask.title}
                </span>
                <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-700 text-xs flex-shrink-0">
                  {currentTask.assignee}
                </Badge>
              </div>
            </div>
          ) : (
            <div className="flex items-center space-x-2 text-muted-foreground">
              <CheckCircle className="h-4 w-4" />
              <span className="text-sm">No active tasks</span>
            </div>
          )}
        </div>

        {/* Right Section - Lane Counts and Status */}
        <div className="flex items-center space-x-6">
          {/* Lane Count Summary */}
          <div className="flex items-center space-x-4 text-sm">
            {/* New */}
            <div className="flex items-center space-x-1">
              <InboxIcon className="h-3 w-3 text-blue-500" />
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data.task_counts.NEW || 0}
              </Badge>
            </div>
            
            {/* User Input Received */}
            <div className="flex items-center space-x-1">
              <UserCheck className="h-3 w-3 text-green-500" />
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data.task_counts.USER_INPUT_RECEIVED || 0}
              </Badge>
            </div>
            
            {/* Needs Review - Highlighted */}
            <div className="flex items-center space-x-1">
              <Eye className="h-3 w-3 text-red-500" />
              <Badge variant={pendingDecisions > 0 ? "destructive" : "secondary"} className="text-xs px-1 py-0">
                {data.task_counts.NEEDS_REVIEW || 0}
              </Badge>
            </div>
            
            {/* Waiting */}
            <div className="flex items-center space-x-1">
              <HourglassIcon className="h-3 w-3 text-orange-500" />
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data.task_counts.WAITING || 0}
              </Badge>
            </div>
            
            {/* In Progress */}
            <div className="flex items-center space-x-1">
              <PlayCircle className="h-3 w-3 text-yellow-500" />
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data.task_counts.IN_PROGRESS || 0}
              </Badge>
            </div>
            
            {/* Done */}
            <div className="flex items-center space-x-1">
              <CheckCircle className="h-3 w-3 text-gray-500" />
              <Badge variant="outline" className="text-xs px-1 py-0">
                {data.task_counts.DONE || 0}
              </Badge>
            </div>
            
            {/* Failed - Only show if there are failed tasks */}
            {(data.task_counts.FAILED || 0) > 0 && (
              <div className="flex items-center space-x-1">
                <XCircle className="h-3 w-3 text-red-600" />
                <Badge variant="destructive" className="text-xs px-1 py-0">
                  {data.task_counts.FAILED}
                </Badge>
              </div>
            )}
          </div>

          {/* System Status & Alert */}
          <div className="flex items-center space-x-3">
            {/* System Status */}
            <div className="flex items-center space-x-1">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm text-muted-foreground">
                {data.system_status}
              </span>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
} 