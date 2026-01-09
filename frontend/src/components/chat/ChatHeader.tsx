"use client";

import { Bot, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface ChatHeaderProps {
  taskInfo: { id: string; title: string } | null;
  isConnected: boolean;
  phoenixUrl: string | null;
  error: string | null;
  userSettings?: { chat_llm_model: string } | null;
}

export function ChatHeader({
  taskInfo,
  isConnected,
  phoenixUrl,
  error,
  userSettings,
}: ChatHeaderProps) {
  return (
    <div className="p-4 border-b border-border bg-card">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center">
            <Bot className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              {taskInfo ? `Nova - Task: ${taskInfo.title}` : "Nova Assistant"}
            </h2>
            <p className="text-sm text-muted-foreground">
              {taskInfo
                ? "Chatting about this specific task"
                : isConnected ? "Ready to help with your tasks" : "Connecting..."
              }
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {userSettings && (
            <Badge variant="outline" className="text-xs">
              {userSettings.chat_llm_model}
            </Badge>
          )}
          {phoenixUrl && (
            <a
              href={phoenixUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="View trace in Phoenix"
            >
              <Badge variant="outline" className="text-xs cursor-pointer hover:bg-accent flex items-center gap-1">
                <ExternalLink className="h-3 w-3" />
                Trace
              </Badge>
            </a>
          )}
          {taskInfo && (
            <Badge variant="secondary" className="text-xs">
              Task Chat
            </Badge>
          )}
          {error && (
            <Badge variant="destructive" className="text-xs">
              Error
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}
