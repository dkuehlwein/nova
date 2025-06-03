"use client";

import Navbar from "@/components/Navbar";
import { AlertTriangle, CheckCircle, ArrowRight, MessageSquare, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useOverview } from "@/hooks/useOverview";
import { useState, useEffect } from "react";
import { apiRequest, API_ENDPOINTS } from "@/lib/api";

interface PendingDecision {
  id: string;
  title: string;
  description: string;
  status: string;
  created_at: string;
  needs_decision: boolean;
  decision_type?: string;
  tags: string[];
}

interface RecentActivityItem {
  id: string;
  title: string;
  description: string;
  status: string;
  updated_at: string;
  tags: string[];
}

export default function Nova() {
  const { data: overviewData, loading: overviewLoading } = useOverview();
  const [pendingDecisions, setPendingDecisions] = useState<PendingDecision[]>([]);
  const [recentTasks, setRecentTasks] = useState<RecentActivityItem[]>([]);
  const [decisionsLoading, setDecisionsLoading] = useState(true);
  const [recentTasksLoading, setRecentTasksLoading] = useState(true);

  // Fetch pending decisions (input needed tasks)
  useEffect(() => {
    const fetchPendingDecisions = async () => {
      try {
        setDecisionsLoading(true);
        const decisions = await apiRequest<PendingDecision[]>(API_ENDPOINTS.pendingDecisions);
        setPendingDecisions(decisions.slice(0, 4)); // Limit to 4 tasks
      } catch (error) {
        console.error('Failed to fetch pending decisions:', error);
      } finally {
        setDecisionsLoading(false);
      }
    };

    fetchPendingDecisions();
  }, []);

  // Fetch recent activity tasks
  useEffect(() => {
    const fetchRecentTasks = async () => {
      try {
        setRecentTasksLoading(true);
        const tasksByStatus = await apiRequest<Record<string, RecentActivityItem[]>>(API_ENDPOINTS.tasksByStatus);
        // Combine all tasks and sort by updated_at, then take first 4
        const allTasks: RecentActivityItem[] = [];
        Object.values(tasksByStatus).forEach((tasks) => {
          if (Array.isArray(tasks)) {
            allTasks.push(...tasks);
          }
        });
        
        const sortedTasks = allTasks
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
          .slice(0, 4);
        
        setRecentTasks(sortedTasks);
      } catch (error) {
        console.error('Failed to fetch recent tasks:', error);
      } finally {
        setRecentTasksLoading(false);
      }
    };

    fetchRecentTasks();
  }, []);
  

  // Format time difference for display
  const formatTimeAgo = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60));
    
    if (diffInHours < 1) {
      return 'Less than 1 hour ago';
    } else if (diffInHours < 24) {
      return `${diffInHours} hour${diffInHours > 1 ? 's' : ''} ago`;
    } else {
      const diffInDays = Math.floor(diffInHours / 24);
      return `${diffInDays} day${diffInDays > 1 ? 's' : ''} ago`;
    }
  };

  // Determine priority based on decision type and age
  const getPriority = (decision: PendingDecision) => {
    const createdDate = new Date(decision.created_at);
    const now = new Date();
    const ageInHours = (now.getTime() - createdDate.getTime()) / (1000 * 60 * 60);
    
    if (ageInHours > 24) return 'high';
    if (decision.decision_type === 'task_review') return 'medium';
    return 'medium';
  };

  // Format status name for display
  const formatStatusName = (status: string): string => {
    return status.replace(/_/g, ' ').toUpperCase();
  };

  if (overviewLoading || decisionsLoading || recentTasksLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <div className="text-muted-foreground">Loading overview...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="flex-1 p-6">
        <div className="mx-auto max-w-6xl">
          {/* Welcome Section */}
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h2 className="text-3xl font-bold text-foreground mb-2">
                Welcome back
              </h2>
              <p className="text-muted-foreground text-lg">
                {pendingDecisions.length > 0 
                  ? "Your Nova assistant is ready to help with your tasks and decisions."
                  : "All caught up! Your Nova assistant is ready for new tasks."
                }
              </p>
            </div>
            <Link href="/chat">
              <Button className="flex items-center space-x-2" size="lg">
                <MessageSquare className="h-5 w-5" />
                <span>Start Chat</span>
              </Button>
            </Link>
          </div>

          {/* Two Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            {/* Left Column - Input Needed */}
            <div className="space-y-6">
              <div className="bg-card border border-border rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <AlertTriangle className="h-6 w-6 text-red-500" />
                    <h3 className="text-xl font-semibold text-foreground">
                      Input Needed
                    </h3>
                  </div>
                  <Badge variant="destructive" className="text-sm px-2 py-1">
                    {pendingDecisions.length} tasks
                  </Badge>
                </div>
                
                <div className="space-y-3">
                  {pendingDecisions.length > 0 ? (
                    pendingDecisions.map((decision) => (
                      <Link key={decision.id} href={`/kanban?task=${decision.id}`}>
                        <div className="bg-background border border-border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center space-x-2 mb-2">
                                <h4 className="font-medium text-foreground text-sm">{decision.title}</h4>
                                <Badge 
                                  variant={getPriority(decision) === "high" ? "destructive" : "secondary"}
                                  className="text-xs"
                                >
                                  {getPriority(decision)}
                                </Badge>
                              </div>
                              <p className="text-sm text-muted-foreground mb-2 line-clamp-2">{decision.description}</p>
                              <div className="flex items-center space-x-3 text-xs text-muted-foreground">
                                <div className="flex items-center space-x-1">
                                  <Clock className="h-3 w-3" />
                                  <span>{formatTimeAgo(decision.created_at)}</span>
                                </div>
                                <div className="flex items-center space-x-1">
                                  <span className="capitalize">
                                    {decision.decision_type ? decision.decision_type.replace('_', ' ') : 'Review'}
                                  </span>
                                </div>
                              </div>
                              {decision.tags.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {decision.tags.slice(0, 2).map((tag) => (
                                    <Badge key={tag} variant="outline" className="text-xs">
                                      {tag}
                                    </Badge>
                                  ))}
                                  {decision.tags.length > 2 && (
                                    <Badge variant="outline" className="text-xs">
                                      +{decision.tags.length - 2}
                                    </Badge>
                                  )}
                                </div>
                              )}
                            </div>
                            <ArrowRight className="h-4 w-4 text-muted-foreground ml-4" />
                          </div>
                        </div>
                      </Link>
                    ))
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-green-500" />
                      <p className="text-sm">No tasks requiring input</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Right Column - Recent Activity */}
            <div className="space-y-6">
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">Recent Activity</h3>
                <div className="space-y-3">
                  {recentTasks.length > 0 ? (
                    recentTasks.map((task) => (
                      <Link key={task.id} href={`/kanban?task=${task.id}`}>
                        <div className="flex items-start space-x-3 p-3 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
                          <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></div>
                          <div className="flex-1">
                            <div className="flex items-center justify-between mb-1">
                              <p className="text-sm font-medium text-foreground">{task.title}</p>
                              <Badge variant="secondary" className="text-xs">
                                {formatStatusName(task.status)}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground line-clamp-2 mb-1">{task.description}</p>
                            <div className="flex items-center justify-between">
                              <p className="text-xs text-muted-foreground">{formatTimeAgo(task.updated_at)}</p>
                              {task.tags.length > 0 && (
                                <div className="flex gap-1">
                                  {task.tags.slice(0, 2).map((tag) => (
                                    <Badge key={tag} variant="outline" className="text-xs">
                                      {tag}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </Link>
                    ))
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <p className="text-sm">No recent activity</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* System Status - Bottom spanning both columns */}
          <div className="bg-card border border-border rounded-lg p-6">
            <div className="flex items-center space-x-3 mb-4">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <div>
                <h3 className="text-lg font-semibold text-foreground">System Status</h3>
                <p className="text-sm text-muted-foreground">
                  {overviewData?.system_status === 'operational' 
                    ? 'All services running normally' 
                    : 'Check system status'}
                </p>
              </div>
            </div>
            
          </div>
        </div>
      </main>
    </div>
  );
}

