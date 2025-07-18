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
  HourglassIcon
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useOverview as useOverviewQuery, useCurrentTask } from "@/hooks/useNovaQueries";
import { useNavbarSystemStatus } from "@/hooks/useUnifiedSystemStatus";
import { useNovaWebSocket } from "@/hooks/useNovaWebSocket";
import { StatusIndicatorCompact } from "@/components/status";

export default function Navbar() {
  const pathname = usePathname();
  const { data, isLoading: loading, isRefetching: refreshing } = useOverviewQuery();
  const currentTask = useCurrentTask();
  const { data: systemStatus, isLoading: healthLoading } = useNavbarSystemStatus();
  
  // Subscribe to WebSocket events for real-time updates
  useNovaWebSocket();

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

  const pendingDecisions = data?.task_counts?.needs_review || 0;

  return (
    <nav className="border-b border-border bg-card">
      <div className="flex h-20 items-center px-6">
        {/* Left Section - Logo and Navigation */}
        <div className="flex items-center space-x-8">
          {/* Logo and Brand */}
          <Link href="/" className="flex items-center space-x-2">
            <Brain className={`h-8 w-8 text-primary ${refreshing ? 'animate-pulse' : ''}`} />
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
                  {data?.total_tasks || 0}
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
                  {currentTask.needs_decision ? 'needs review' : 'in progress'}
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
                {data?.task_counts?.new || 0}
              </Badge>
            </div>
            
            {/* User Input Received */}
            <div className="flex items-center space-x-1">
              <UserCheck className="h-3 w-3 text-green-500" />
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data?.task_counts?.user_input_received || 0}
              </Badge>
            </div>
            
            {/* In Progress */}
            <div className="flex items-center space-x-1">
              <Eye className="h-3 w-3 text-purple-500" />
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data?.task_counts?.in_progress || 0}
              </Badge>
            </div>
            
            {/* Needs Review */}
            <div className="flex items-center space-x-1">
              <HourglassIcon className="h-3 w-3 text-red-500" />
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {data?.task_counts?.needs_review || 0}
              </Badge>
            </div>
          </div>

          {/* System Status */}
          <Link 
            href="/settings?tab=system-status" 
            className="flex items-center space-x-2 hover:opacity-80 transition-opacity"
            title={systemStatus?.summary?.top_issues?.join(", ") || "View system status"}
          >
            <StatusIndicatorCompact
              status={systemStatus?.overall_status || (healthLoading ? "loading" : "unknown")}
              service={systemStatus ? `${systemStatus.summary.healthy_services}/${systemStatus.summary.total_services} healthy` : "System Status"}
              showText={true}
              className="text-sm font-medium"
            />
            
            {/* Health Percentage Badge */}
            {systemStatus && systemStatus.overall_status !== "loading" && (
              <Badge 
                variant={systemStatus.overall_status === "operational" ? "default" : "destructive"}
                className="text-xs ml-2"
              >
                {systemStatus.overall_health_percentage.toFixed(0)}%
              </Badge>
            )}
          </Link>
        </div>
      </div>
    </nav>
  );
} 