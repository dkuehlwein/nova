"use client";

import { MessageSquare, Link, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarkdownMessage } from "./MarkdownMessage";
import { formatDate } from "@/lib/format-utils";

export interface ChatHistoryItemData {
  id: string;
  title: string;
  last_message: string;
  updated_at: string;
  last_activity?: string;
  needs_decision: boolean;
  task_id?: string;
  message_count?: number;
  has_decision?: boolean;
}

interface ChatHistoryItemProps {
  item: ChatHistoryItemData;
  isDeleting: boolean;
  onSelect: (item: ChatHistoryItemData) => void;
  onDelete: (item: ChatHistoryItemData, e: React.MouseEvent) => void;
}

export function ChatHistoryItem({
  item,
  isDeleting,
  onSelect,
  onDelete,
}: ChatHistoryItemProps) {
  return (
    <div
      onClick={() => onSelect(item)}
      className="p-3 rounded-lg border hover:bg-muted cursor-pointer transition-colors group/chat relative"
    >
      <div className="flex items-start space-x-2">
        <MessageSquare className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
            <h4 className="text-sm font-medium truncate flex-1">
              <MarkdownMessage content={item.title} disableLinks />
            </h4>
            {item.task_id && (
              <span title="Connected to task">
                <Link className="h-3 w-3 text-muted-foreground flex-shrink-0" />
              </span>
            )}
          </div>
          <div className="text-xs text-muted-foreground line-clamp-2 mt-1">
            <MarkdownMessage content={item.last_message} disableLinks />
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {formatDate(item.last_activity || item.updated_at)}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0 opacity-0 group-hover/chat:opacity-100 transition-opacity text-muted-foreground hover:text-destructive flex-shrink-0"
          onClick={(e) => onDelete(item, e)}
          disabled={isDeleting}
          title={item.task_id ? "Delete chat and task" : "Delete chat"}
        >
          {isDeleting ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Trash2 className="h-3 w-3" />
          )}
        </Button>
      </div>
    </div>
  );
}
