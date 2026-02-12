"use client";

import { AlertTriangle, Loader2, StopCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChatHistoryItem, type ChatHistoryItemData } from "./ChatHistoryItem";
import { PendingDecisionItem, type PendingDecision } from "./PendingDecisionItem";

interface ChatSidebarProps {
  isConnected: boolean;
  isLoading: boolean;
  isStreaming: boolean;
  loadingDecisions: boolean;
  hasMoreChats: boolean;
  loadingMoreChats: boolean;
  deletingChatId: string | null;
  pendingDecisions: PendingDecision[];
  chatHistory: ChatHistoryItemData[];
  onNewChat: () => void;
  onStopStreaming: () => void;
  onChatSelect: (item: ChatHistoryItemData) => void;
  onDeleteChat: (item: ChatHistoryItemData, e: React.MouseEvent) => void;
  onLoadMore: () => void;
  onRenameChat?: (id: string, newTitle: string) => Promise<void>;
}

export function ChatSidebar({
  isConnected,
  isLoading,
  isStreaming,
  loadingDecisions,
  hasMoreChats,
  loadingMoreChats,
  deletingChatId,
  pendingDecisions,
  chatHistory,
  onNewChat,
  onStopStreaming,
  onChatSelect,
  onDeleteChat,
  onLoadMore,
  onRenameChat,
}: ChatSidebarProps) {
  // Filter out chats that need decisions (they show in pending section)
  const regularChats = chatHistory.filter(chat => !chat.needs_decision);

  return (
    <div className="chat-sidebar w-80 border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Chat History</h2>
          <div className="flex items-center space-x-2">
            {isConnected ? (
              <Badge variant="default" className="text-xs bg-green-500">
                Connected
              </Badge>
            ) : (
              <Badge variant="destructive" className="text-xs">
                Disconnected
              </Badge>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onNewChat}
            className="w-full"
            disabled={isLoading}
          >
            New Chat
          </Button>

          {isLoading && isStreaming && (
            <Button
              variant="outline"
              size="sm"
              onClick={onStopStreaming}
              className="w-full"
            >
              <StopCircle className="h-4 w-4 mr-2" />
              Stop
            </Button>
          )}
        </div>
      </div>

      {/* Chat History List */}
      <div className="flex-1 overflow-y-auto chat-container">
        {loadingDecisions ? (
          <div className="p-4 text-center">
            <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Loading chats...</p>
          </div>
        ) : (
          <>
            {/* Pending Decisions Section */}
            {pendingDecisions.length > 0 && (
              <div className="p-4">
                <h3 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wide flex items-center">
                  <AlertTriangle className="h-4 w-4 mr-1 text-orange-500" />
                  Needs Decision ({pendingDecisions.length})
                </h3>
                <div className="space-y-2">
                  {pendingDecisions.map((decision) => (
                    <PendingDecisionItem
                      key={decision.id}
                      decision={decision}
                      isDeleting={deletingChatId === `core_agent_task_${decision.id}`}
                      onSelect={onChatSelect}
                      onDelete={onDeleteChat}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Regular Chat History */}
            <div className="p-4">
              <h3 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wide">
                Recent Chats
              </h3>
              {regularChats.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No chat history yet
                </p>
              ) : (
                <div className="space-y-2">
                  {regularChats.map((chatItem) => (
                    <ChatHistoryItem
                      key={chatItem.id}
                      item={chatItem}
                      isDeleting={deletingChatId === chatItem.id}
                      onSelect={onChatSelect}
                      onDelete={onDeleteChat}
                      onRename={onRenameChat}
                    />
                  ))}
                </div>
              )}

              {/* Load More Button */}
              {hasMoreChats && regularChats.length > 0 && (
                <div className="mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onLoadMore}
                    disabled={loadingMoreChats}
                    className="w-full"
                  >
                    {loadingMoreChats ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Loading...
                      </>
                    ) : (
                      'Load More Chats'
                    )}
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
