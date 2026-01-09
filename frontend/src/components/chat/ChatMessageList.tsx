"use client";

import { forwardRef, useCallback } from "react";
import { AlertTriangle } from "lucide-react";
import { ChatMessageBubble } from "./ChatMessageBubble";
import { EscalationBox } from "./EscalationBox";
import { WelcomeScreen } from "./WelcomeScreen";
import type { ChatMessage, PendingEscalation } from "@/hooks/useChat";

interface ChatMessageListProps {
  messages: ChatMessage[];
  pendingEscalation: PendingEscalation | null;
  pendingDecisionsCount: number;
  error: string | null;
  isLoading: boolean;
  copiedMessageId: string | null;
  ratedMessages: Record<string, 'up' | 'down'>;
  onCopyMessage: (id: string, content: string) => void;
  onRegenerateMessage: (index: number) => void;
  onRateMessage: (id: string, rating: 'up' | 'down') => void;
  onEscalationSubmit: (response: string) => Promise<void>;
  onEscalationApprove: () => Promise<void>;
  onEscalationDeny: () => Promise<void>;
  onEscalationAlwaysAllow: () => Promise<void>;
  onSetMessage: (message: string) => void;
}

export const ChatMessageList = forwardRef<HTMLDivElement, ChatMessageListProps>(
  function ChatMessageList(
    {
      messages,
      pendingEscalation,
      pendingDecisionsCount,
      error,
      isLoading,
      copiedMessageId,
      ratedMessages,
      onCopyMessage,
      onRegenerateMessage,
      onRateMessage,
      onEscalationSubmit,
      onEscalationApprove,
      onEscalationDeny,
      onEscalationAlwaysAllow,
      onSetMessage,
    },
    ref
  ) {
    const handleRegenerate = useCallback((messageIndex: number) => {
      if (messageIndex === 0) return;
      const userMessage = messages[messageIndex - 1];
      if (userMessage && userMessage.role === 'user') {
        onRegenerateMessage(messageIndex);
      }
    }, [messages, onRegenerateMessage]);

    if (messages.length === 0) {
      return (
        <div className="flex-1 overflow-y-auto chat-container p-4">
          <WelcomeScreen
            pendingDecisionsCount={pendingDecisionsCount}
            isLoading={isLoading}
            onSetMessage={onSetMessage}
          />
        </div>
      );
    }

    return (
      <div className="flex-1 overflow-y-auto chat-container p-4">
        <div className="space-y-4">
          {messages.map((msg, index) => (
            <ChatMessageBubble
              key={msg.id}
              message={msg}
              messageIndex={index}
              copiedMessageId={copiedMessageId}
              ratedMessages={ratedMessages}
              isLoading={isLoading}
              onCopy={onCopyMessage}
              onRegenerate={handleRegenerate}
              onRate={onRateMessage}
            />
          ))}

          {/* Escalation Box for pending decisions */}
          {pendingEscalation && (
            <EscalationBox
              question={pendingEscalation.question}
              instructions={pendingEscalation.instructions}
              escalationType={pendingEscalation.type || 'user_question'}
              toolName={pendingEscalation.tool_name}
              toolArgs={pendingEscalation.tool_args}
              onSubmit={onEscalationSubmit}
              onApprove={onEscalationApprove}
              onDeny={onEscalationDeny}
              onAlwaysAllow={onEscalationAlwaysAllow}
              isSubmitting={isLoading}
            />
          )}

          {error && (
            <div className="flex justify-center">
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-2 rounded-lg text-sm">
                <AlertTriangle className="h-4 w-4 inline mr-2" />
                {error}
              </div>
            </div>
          )}
          <div ref={ref} />
        </div>
      </div>
    );
  }
);
