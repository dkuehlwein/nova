"use client";

import Navbar from "@/components/Navbar";
import { AlertTriangle, CheckCircle, ArrowRight, MessageSquare, KanbanSquare, Clock, User, Calendar } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function Nova() {
  // Mock data - will be replaced with real API calls later
  const pendingDecisions = [
    {
      id: 1,
      title: "Approve email draft to John Smith",
      description: "AI has prepared a response to John's inquiry about project timeline",
      chatId: "chat-123",
      createdAt: "2 hours ago",
      priority: "high",
      type: "email_approval"
    },
    {
      id: 2,
      title: "Choose task assignment strategy",
      description: "Multiple team members available for the new marketing campaign",
      chatId: "chat-124", 
      createdAt: "4 hours ago",
      priority: "medium",
      type: "strategy_choice"
    }
  ];

  const recentActivity = [
    {
      type: "task_created",
      title: "Created task: Review quarterly reports",
      description: "Moved to TODO lane",
      time: "5 minutes ago"
    },
    {
      type: "email_processed",
      title: "Processed 3 new emails",
      description: "2 replies sent, 1 pending your review",
      time: "15 minutes ago"
    },
    {
      type: "task_completed",
      title: "Completed: Update client presentation",
      description: "Moved to DONE lane",
      time: "1 hour ago"
    }
  ];

  const systemStats = {
    tasksTotal: 47,
    tasksActive: 17,
    tasksCompleted: 24,
    emailsProcessed: 156,
    conversationsActive: 8
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="flex-1 p-6">
        <div className="mx-auto max-w-7xl">
          {/* Welcome Section */}
          <div className="mb-8">
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

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - Primary Actions */}
            <div className="lg:col-span-2 space-y-6">
              {/* Decisions Pending - Primary Focus */}
              {pendingDecisions.length > 0 && (
                <div className="bg-gradient-to-r from-red-500/10 to-orange-500/10 border border-red-500/20 rounded-lg p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <AlertTriangle className="h-6 w-6 text-red-500" />
                      <h3 className="text-xl font-semibold text-foreground">
                        Your Input Needed
                      </h3>
                    </div>
                    <Badge variant="destructive" className="text-sm px-2 py-1">
                      {pendingDecisions.length} pending
                    </Badge>
                  </div>
                  
                  <div className="space-y-3">
                    {pendingDecisions.map((decision) => (
                      <div key={decision.id} className="bg-card border border-border rounded-lg p-4 hover:shadow-md transition-shadow">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center space-x-2 mb-2">
                              <h4 className="font-medium text-foreground">{decision.title}</h4>
                              <Badge 
                                variant={decision.priority === "high" ? "destructive" : "secondary"}
                                className="text-xs"
                              >
                                {decision.priority}
                              </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground mb-2">{decision.description}</p>
                            <div className="flex items-center space-x-3 text-xs text-muted-foreground">
                              <div className="flex items-center space-x-1">
                                <Clock className="h-3 w-3" />
                                <span>{decision.createdAt}</span>
                              </div>
                              <div className="flex items-center space-x-1">
                                <span className="capitalize">{decision.type.replace('_', ' ')}</span>
                              </div>
                            </div>
                          </div>
                          <Link href={`/chat?id=${decision.chatId}`}>
                            <Button size="sm" className="ml-4 flex items-center space-x-1">
                              <MessageSquare className="h-4 w-4" />
                              <span>Review</span>
                              <ArrowRight className="h-3 w-3" />
                            </Button>
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recent Activity */}
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">Recent Activity</h3>
                <div className="space-y-3">
                  {recentActivity.map((activity, index) => (
                    <div key={index} className="flex items-start space-x-3 p-3 rounded-lg hover:bg-muted/50 transition-colors">
                      <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-foreground">{activity.title}</p>
                        <p className="text-xs text-muted-foreground">{activity.description}</p>
                        <p className="text-xs text-muted-foreground mt-1">{activity.time}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Column - Quick Actions & Stats */}
            <div className="space-y-6">
              {/* Quick Actions */}
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">Quick Actions</h3>
                <div className="space-y-3">
                  <Link href="/chat">
                    <Button className="w-full justify-start" variant="outline">
                      <MessageSquare className="h-4 w-4 mr-2" />
                      Start New Chat
                    </Button>
                  </Link>
                  <Link href="/kanban">
                    <Button className="w-full justify-start" variant="outline">
                      <KanbanSquare className="h-4 w-4 mr-2" />
                      View Task Board
                    </Button>
                  </Link>
                </div>
              </div>

              {/* System Overview */}
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">System Overview</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Active Tasks</span>
                    <span className="text-sm font-medium">{systemStats.tasksActive}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Completed Tasks</span>
                    <span className="text-sm font-medium">{systemStats.tasksCompleted}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Emails Processed</span>
                    <span className="text-sm font-medium">{systemStats.emailsProcessed}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Active Conversations</span>
                    <span className="text-sm font-medium">{systemStats.conversationsActive}</span>
                  </div>
                </div>
              </div>

              {/* Status Indicator */}
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  <div>
                    <p className="text-sm font-medium text-foreground">System Operational</p>
                    <p className="text-xs text-muted-foreground">All services running normally</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
