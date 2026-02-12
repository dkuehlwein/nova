"use client";

import { forwardRef } from "react";
import { AlertTriangle } from "lucide-react";
import { ChatMessageBubble } from "./ChatMessageBubble";
import { EscalationBox } from "./EscalationBox";
import { WelcomeScreen } from "./WelcomeScreen";
import type { ChatMessage, PendingEscalation } from "@/types/chat";

interface ChatMessageListProps {
  messages: ChatMessage[];
  pendingEscalation: PendingEscalation | null;
  pendingDecisionsCount: number;
  error: string | null;
}

export const ChatMessageList = forwardRef<HTMLDivElement, ChatMessageListProps>(
  function ChatMessageList(
    { messages, pendingEscalation, pendingDecisionsCount, error },
    ref
  ) {
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
            <ChatMessageBubble
              key={msg.id}
              message={msg}
              messageIndex={index}
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
