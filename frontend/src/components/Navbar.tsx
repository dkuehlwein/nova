import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Brain, 
  MessageSquare, 
  KanbanSquare, 
  Settings, 
  AlertTriangle,
  CheckCircle,
  Clock
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function Navbar() {
  const pathname = usePathname();

  // Mock data - will be replaced with real API calls later
  const statusData = {
    openTasks: 12,
    blockedTasks: 3,
    inProgressTasks: 5,
    completedTasks: 24,
    pendingDecisions: 2,
    agentStatus: "operational", // "operational" | "busy" | "offline"
    mcpServices: 37
  };

  const isActive = (path: string) => pathname === path;

  return (
    <nav className="border-b border-border bg-card">
      <div className="flex h-16 items-center px-6">
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
                {statusData.pendingDecisions > 0 && (
                  <Badge variant="destructive" className="text-xs px-1 py-0 min-w-[16px] h-4">
                    {statusData.pendingDecisions}
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
              {statusData.pendingDecisions > 0 && (
                <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              )}
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
                {statusData.openTasks + statusData.inProgressTasks}
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

        {/* Streamlined Status - Focus on Core Metrics */}
        <div className="ml-auto flex items-center space-x-4">
          {/* Task Status Overview */}
          <div className="flex items-center space-x-3 text-sm">
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
              <span className="text-muted-foreground">Active</span>
              <Badge variant="secondary" className="text-xs px-1 py-0">
                {statusData.openTasks + statusData.inProgressTasks}
              </Badge>
            </div>
            
            {statusData.blockedTasks > 0 && (
              <div className="flex items-center space-x-1">
                <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                <span className="text-muted-foreground">Blocked</span>
                <Badge variant="destructive" className="text-xs px-1 py-0">
                  {statusData.blockedTasks}
                </Badge>
              </div>
            )}
          </div>

          {/* Single Decision Alert - Primary Source of Truth */}
          {statusData.pendingDecisions > 0 && (
            <Link href="/">
              <div className="flex items-center space-x-2 px-3 py-1 bg-red-500/10 border border-red-500/20 rounded-md cursor-pointer hover:bg-red-500/20 transition-colors">
                <AlertTriangle className="h-4 w-4 text-red-500" />
                <span className="text-sm text-red-500 font-medium">
                  {statusData.pendingDecisions} pending
                </span>
              </div>
            </Link>
          )}

          {/* Agent Status */}
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1">
              {statusData.agentStatus === "operational" && (
                <CheckCircle className="h-4 w-4 text-green-500" />
              )}
              {statusData.agentStatus === "busy" && (
                <Clock className="h-4 w-4 text-yellow-500 animate-spin" />
              )}
              {statusData.agentStatus === "offline" && (
                <AlertTriangle className="h-4 w-4 text-red-500" />
              )}
              <span className="text-sm text-muted-foreground capitalize">
                {statusData.agentStatus}
              </span>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
} 