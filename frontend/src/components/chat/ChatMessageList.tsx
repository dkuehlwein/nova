'use client';

import { forwardRef } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { ChatMessageBubble } from './ChatMessageBubble';
import { EscalationBox } from './EscalationBox';
import { WelcomeScreen } from './WelcomeScreen';
import type { ChatMessage, PendingEscalation } from '@/types/chat';

function ChatLoadingSkeleton() {
  return (
    <div className="flex-1 overflow-y-auto chat-container p-4">
      <div className="space-y-4 animate-pulse">
        {/* User message skeleton */}
        <div className="flex justify-end">
          <div className="bg-primary/10 rounded-lg p-3 max-w-[70%]">
            <div className="h-4 bg-primary/20 rounded w-48" />
          </div>
        </div>
        {/* Assistant message skeleton */}
        <div className="flex justify-start">
          <div className="bg-muted rounded-lg p-3 max-w-[70%] space-y-2">
            <div className="h-4 bg-muted-foreground/20 rounded w-64" />
            <div className="h-4 bg-muted-foreground/20 rounded w-52" />
            <div className="h-4 bg-muted-foreground/20 rounded w-40" />
          </div>
        </div>
        {/* Loading indicator */}
        <div className="flex justify-center">
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading conversation...
          </div>
        </div>
      </div>
    </div>
  );
}

interface ChatMessageListProps {
  messages: ChatMessage[];
  pendingEscalation: PendingEscalation | null;
  pendingDecisionsCount: number;
  error: string | null;
  isLoadingChat?: boolean;
}

export const ChatMessageList = forwardRef<HTMLDivElement, ChatMessageListProps>(
  function ChatMessageList(
    { messages, pendingEscalation, pendingDecisionsCount, error, isLoadingChat },
    ref,
  ) {
    // Show loading skeleton when actively loading a chat conversation
    if (isLoadingChat) {
      return <ChatLoadingSkeleton />;
    }

    if (messages.length === 0) {
      return (
        <div className="flex-1 overflow-y-auto chat-container p-4">
          <WelcomeScreen pendingDecisionsCount={pendingDecisionsCount} />
        </div>
      );
    }

    return (
      <div className="flex-1 overflow-y-auto chat-container p-4">
        <div className="space-y-4">
          {messages.map((msg, index) => (
            <ChatMessageBubble key={msg.id} message={msg} messageIndex={index} />
          ))}

          {/* Escalation Box for pending decisions */}
          {pendingEscalation && (
            <EscalationBox
              question={pendingEscalation.question}
              instructions={pendingEscalation.instructions}
              escalationType={pendingEscalation.type || 'user_question'}
              toolName={pendingEscalation.tool_name}
              toolArgs={pendingEscalation.tool_args}
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
  },
);
