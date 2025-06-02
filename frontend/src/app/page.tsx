"use client";

import Navbar from "@/components/Navbar";
import { AlertCircle, CheckCircle, ArrowRight, MessageSquare, KanbanSquare } from "lucide-react";
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
      priority: "high"
    },
    {
      id: 2,
      title: "Choose task assignment strategy",
      description: "Multiple team members available for the new marketing campaign",
      chatId: "chat-124", 
      createdAt: "4 hours ago",
      priority: "medium"
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
              Here&apos;s what needs your attention
            </p>
          </div>

          {/* Critical Alerts Section */}
          {pendingDecisions.length > 0 && (
            <div className="mb-8">
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6">
                <div className="flex items-center space-x-2 mb-4">
                  <AlertCircle className="h-5 w-5 text-red-500" />
                  <h3 className="text-lg font-semibold text-red-500">
                    Decisions Pending Your Input
                  </h3>
                  <Badge variant="destructive">{pendingDecisions.length}</Badge>
                </div>
                
                <div className="space-y-4">
                  {pendingDecisions.map((decision) => (
                    <div key={decision.id} className="bg-card border border-border rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            <h4 className="font-medium text-foreground">{decision.title}</h4>
                            <Badge variant={decision.priority === "high" ? "destructive" : "secondary"}>
                              {decision.priority}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground mb-2">{decision.description}</p>
                          <p className="text-xs text-muted-foreground">{decision.createdAt}</p>
                        </div>
                        <Link href={`/chat/${decision.chatId}`}>
                          <Button size="sm" className="ml-4">
                            <MessageSquare className="h-4 w-4 mr-1" />
                            Respond
                          </Button>
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Quick Actions */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <Link href="/chat">
              <div className="bg-card border border-border rounded-lg p-6 hover:bg-muted/50 transition-colors cursor-pointer">
                <div className="flex items-center space-x-2 mb-2">
                  <MessageSquare className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold text-foreground">Start New Chat</h3>
                </div>
                <p className="text-sm text-muted-foreground mb-3">
                  Ask Nova to help with emails, tasks, or decisions
                </p>
                <div className="flex items-center text-primary text-sm font-medium">
                  Open Chat <ArrowRight className="h-4 w-4 ml-1" />
                </div>
              </div>
            </Link>

            <Link href="/kanban">
              <div className="bg-card border border-border rounded-lg p-6 hover:bg-muted/50 transition-colors cursor-pointer">
                <div className="flex items-center space-x-2 mb-2">
                  <KanbanSquare className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold text-foreground">View All Tasks</h3>
                </div>
                <p className="text-sm text-muted-foreground mb-3">
                  Manage your kanban board and track progress
                </p>
                <div className="flex items-center text-primary text-sm font-medium">
                  Open Tasks <ArrowRight className="h-4 w-4 ml-1" />
                </div>
              </div>
            </Link>

            {pendingDecisions.length > 0 && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6">
                <div className="flex items-center space-x-2 mb-2">
                  <AlertCircle className="h-5 w-5 text-red-500" />
                  <h3 className="font-semibold text-red-500">Review Decisions</h3>
                  <Badge variant="destructive">{pendingDecisions.length}</Badge>
                </div>
                <p className="text-sm text-muted-foreground mb-3">
                  Items are waiting for your input to continue
                </p>
                <Button size="sm" variant="destructive" className="w-full">
                  Review All
                </Button>
              </div>
            )}
          </div>

          {/* Recent Activity */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-card border border-border rounded-lg p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Recent Activity</h3>
              <div className="space-y-4">
                {recentActivity.map((activity, index) => (
                  <div key={index} className="flex items-start space-x-3">
                    <div className="w-2 h-2 bg-primary rounded-full mt-2 flex-shrink-0"></div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-foreground">{activity.title}</p>
                      <p className="text-xs text-muted-foreground">{activity.description}</p>
                      <p className="text-xs text-muted-foreground mt-1">{activity.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-card border border-border rounded-lg p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">System Status</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span className="text-sm text-foreground">Nova Agent</span>
                  </div>
                  <Badge variant="outline" className="text-green-500">Operational</Badge>
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span className="text-sm text-foreground">Gmail MCP</span>
                  </div>
                  <Badge variant="outline" className="text-green-500">27 tools</Badge>
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span className="text-sm text-foreground">Kanban MCP</span>
                  </div>
                  <Badge variant="outline" className="text-green-500">10 tools</Badge>
                </div>
                
                <div className="pt-2 border-t border-border">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">Total Tools Available</span>
                    <Badge variant="secondary">37</Badge>
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
