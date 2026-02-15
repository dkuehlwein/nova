'use client';

import { useState, useRef, useEffect } from 'react';
import { MessageSquare, Link, Trash2, Loader2, Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MarkdownMessage } from './MarkdownMessage';
import { formatDate } from '@/lib/format-utils';

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
  isLoading?: boolean;
  onSelect: (item: ChatHistoryItemData) => void;
  onDelete: (item: ChatHistoryItemData, e: React.MouseEvent) => void;
  onRename?: (id: string, newTitle: string) => Promise<void>;
}

export function ChatHistoryItem({
  item,
  isDeleting,
  isLoading,
  onSelect,
  onDelete,
  onRename,
}: ChatHistoryItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(item.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleStartEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditTitle(item.title);
    setIsEditing(true);
  };

  const handleSaveEdit = async () => {
    const trimmed = editTitle.trim();
    if (trimmed && trimmed !== item.title && onRename) {
      try {
        await onRename(item.id, trimmed);
      } catch {
        setEditTitle(item.title);
      }
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      setEditTitle(item.title);
      setIsEditing(false);
    }
  };

  return (
    <div
      onClick={() => !isEditing && !isLoading && onSelect(item)}
      className={`p-3 rounded-lg border cursor-pointer transition-colors group/chat relative ${
        isLoading ? 'bg-muted border-primary/50' : 'hover:bg-muted'
      }`}
    >
      <div className="flex items-start space-x-2">
        {isLoading ? (
          <Loader2 className="h-4 w-4 text-primary mt-0.5 flex-shrink-0 animate-spin" />
        ) : (
          <MessageSquare className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
            {isEditing ? (
              <input
                ref={inputRef}
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onBlur={handleSaveEdit}
                onKeyDown={handleKeyDown}
                onClick={(e) => e.stopPropagation()}
                className="text-sm font-medium w-full bg-background border border-border rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-ring"
              />
            ) : (
              <h4 className="text-sm font-medium truncate flex-1">
                <MarkdownMessage content={item.title} disableLinks />
              </h4>
            )}
            {item.task_id && !isEditing && (
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
        <div className="flex flex-col gap-0.5 flex-shrink-0">
          {onRename && !isEditing && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 opacity-0 group-hover/chat:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
              onClick={handleStartEdit}
              title="Rename chat"
            >
              <Pencil className="h-3 w-3" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 opacity-0 group-hover/chat:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
            onClick={(e) => onDelete(item, e)}
            disabled={isDeleting}
            title={item.task_id ? 'Delete chat and task' : 'Delete chat'}
          >
            {isDeleting ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="h-3 w-3" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
