"use client";

import { Loader2, Copy, RotateCcw, Check, ThumbsUp, ThumbsDown, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarkdownMessage } from "./MarkdownMessage";
import { SystemMessage } from "./SystemMessage";
import { formatTimestamp } from "@/lib/format-utils";
import type { ChatMessage } from "@/hooks/useChat";

interface ChatMessageBubbleProps {
  message: ChatMessage;
  messageIndex: number;
  copiedMessageId: string | null;
  ratedMessages: Record<string, 'up' | 'down'>;
  isLoading: boolean;
  onCopy: (messageId: string, content: string) => void;
  onRegenerate: (messageIndex: number) => void;
  onRate: (messageId: string, rating: 'up' | 'down') => void;
}

export function ChatMessageBubble({
  message,
  messageIndex,
  copiedMessageId,
  ratedMessages,
  isLoading,
  onCopy,
  onRegenerate,
  onRate,
}: ChatMessageBubbleProps) {
  // Handle system messages
  if (message.role === "system") {
    return (
      <SystemMessage
        content={message.content}
        collapsibleContent={message.metadata?.collapsible_content}
        isCollapsible={message.metadata?.is_collapsible || false}
        timestamp={message.timestamp}
        messageType={message.metadata?.type || "system_prompt"}
        title={message.metadata?.title}
      />
    );
  }

  // Handle tool approval decision messages with special styling
  if (message.role === "user" && message.metadata?.type === "tool_approval_decision") {
    return (
      <div className="flex justify-center mb-4">
        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 text-blue-800 dark:text-blue-200 rounded-lg px-4 py-2 text-sm font-medium shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  // Handle messages with special metadata (like task context) using SystemMessage component
  if ((message.role === "assistant" || message.role === "user") && message.metadata?.is_collapsible) {
    return (
      <SystemMessage
        content=""
        collapsibleContent={message.content}
        isCollapsible={message.metadata?.is_collapsible || false}
        timestamp={message.timestamp}
        messageType={message.metadata?.type || "task_context"}
        title={message.metadata?.title}
      />
    );
  }

  // Handle regular user/assistant messages
  return (
    <div
      className={`flex ${message.role === "user" ? "justify-end" : "justify-start"} mb-6 group`}
    >
      <div
        className={`max-w-[85%] min-w-[250px] ${
          message.role === "user"
            ? "bg-primary text-primary-foreground shadow-sm"
            : "bg-card border shadow-sm"
        } rounded-xl p-4 pb-8 relative transition-shadow hover:shadow-md`}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-semibold">
              {message.role === "assistant" ? "Nova" : "You"}
            </span>
            {message.isStreaming && (
              <Loader2 className="h-3 w-3 animate-spin opacity-60" />
            )}
            {message.role === "assistant" && message.phoenixUrl && !message.isStreaming && (
              <a
                href={message.phoenixUrl}
                target="_blank"
                rel="noopener noreferrer"
                title="View trace in Phoenix"
                className="text-muted-foreground/70 hover:text-foreground transition-colors ml-1"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
          <span className={`text-xs ${message.role === 'user' ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
            {formatTimestamp(message.timestamp)}
          </span>
        </div>

        <div className="text-sm break-words min-h-[1.25rem]">
          {message.content || message.toolCalls ? (
            <MarkdownMessage content={message.content || ''} toolCalls={message.toolCalls} />
          ) : (message.isStreaming ? (
            <div className="flex items-center space-x-2 opacity-60">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                <div className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                <div className="w-2 h-2 bg-current rounded-full animate-bounce"></div>
              </div>
              <span>Nova is thinking...</span>
            </div>
          ) : '')}
        </div>

        {/* Message Actions - Positioned in the bottom padding area */}
        {!message.isStreaming && message.content && (
          <div className={`absolute bottom-2 right-2 flex items-center space-x-1 backdrop-blur-sm border rounded-lg px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity shadow-sm ${
            message.role === "user"
              ? "bg-primary-foreground/20 border-primary-foreground/30"
              : "bg-background/90 border-border/50"
          }`}>
            <Button
              variant="ghost"
              size="sm"
              className={`h-6 px-1.5 text-xs ${
                message.role === "user"
                  ? "hover:bg-primary-foreground/20 text-primary-foreground"
                  : "hover:bg-muted"
              }`}
              onClick={() => onCopy(message.id, message.content)}
              disabled={copiedMessageId === message.id}
            >
              {copiedMessageId === message.id ? (
                <Check className="h-3 w-3" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </Button>

            {message.role === "assistant" && messageIndex > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-1.5 text-xs hover:bg-muted"
                onClick={() => onRegenerate(messageIndex)}
                disabled={isLoading}
              >
                <RotateCcw className="h-3 w-3" />
              </Button>
            )}

            {/* Rating buttons for assistant messages */}
            {message.role === "assistant" && (
              <>
                <div className="w-px h-4 bg-border mx-1" />
                <Button
                  variant="ghost"
                  size="sm"
                  className={`h-6 px-1.5 text-xs hover:bg-muted ${
                    ratedMessages[message.id] === 'up' ? 'text-green-600' : ''
                  }`}
                  onClick={() => onRate(message.id, 'up')}
                >
                  <ThumbsUp className="h-3 w-3" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className={`h-6 px-1.5 text-xs hover:bg-muted ${
                    ratedMessages[message.id] === 'down' ? 'text-red-600' : ''
                  }`}
                  onClick={() => onRate(message.id, 'down')}
                >
                  <ThumbsDown className="h-3 w-3" />
                </Button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
