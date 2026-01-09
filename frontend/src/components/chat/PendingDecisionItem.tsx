"use client";

import { AlertTriangle, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarkdownMessage } from "./MarkdownMessage";
import { formatDate } from "@/lib/format-utils";
import type { ChatHistoryItemData } from "./ChatHistoryItem";

export interface PendingDecision {
  id: string;
  title: string;
  description: string;
  status: string;
  needs_decision: boolean;
  decision_type?: string;
  updated_at: string;
}

interface PendingDecisionItemProps {
  decision: PendingDecision;
  isDeleting: boolean;
  onSelect: (item: ChatHistoryItemData) => void;
  onDelete: (item: ChatHistoryItemData, e: React.MouseEvent) => void;
}

export function PendingDecisionItem({
  decision,
  isDeleting,
  onSelect,
  onDelete,
}: PendingDecisionItemProps) {
  // Convert decision to ChatHistoryItemData format for handlers
  const chatItem: ChatHistoryItemData = {
    id: `core_agent_task_${decision.id}`,
    title: decision.title,
    last_message: decision.description,
    updated_at: decision.updated_at,
    needs_decision: true,
    task_id: decision.id,
  };

  return (
    <div
      onClick={() => onSelect(chatItem)}
      className="p-3 rounded-lg border border-orange-200 dark:border-orange-700 bg-orange-50 dark:bg-orange-900/30 hover:bg-orange-100 dark:hover:bg-orange-900/50 cursor-pointer transition-colors group/decision"
    >
      <div className="flex items-start space-x-2">
        <AlertTriangle className="h-4 w-4 text-orange-500 dark:text-orange-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-orange-900 dark:text-orange-100 truncate">
            {decision.title}
          </h4>
          <div className="text-xs text-orange-700 dark:text-orange-300 line-clamp-2 mt-1">
            <MarkdownMessage content={decision.description} disableLinks />
          </div>
          <p className="text-xs text-orange-600 dark:text-orange-400 mt-2">
            {formatDate(decision.updated_at)}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0 opacity-0 group-hover/decision:opacity-100 transition-opacity text-orange-600 dark:text-orange-400 hover:text-destructive flex-shrink-0"
          onClick={(e) => onDelete(chatItem, e)}
          disabled={isDeleting}
          title="Delete chat and task"
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
