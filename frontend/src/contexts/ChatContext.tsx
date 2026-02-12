"use client";

import { createContext, useContext } from "react";

interface ChatContextValue {
  // Message interactions
  copiedMessageId: string | null;
  ratedMessages: Record<string, 'up' | 'down'>;
  onCopyMessage: (id: string, content: string) => void;
  onRegenerateMessage: (index: number) => void;
  onRateMessage: (id: string, rating: 'up' | 'down') => void;

  // Escalation handlers
  onEscalationSubmit: (response: string) => Promise<void>;
  onEscalationApprove: () => Promise<void>;
  onEscalationDeny: () => Promise<void>;
  onEscalationAlwaysAllow: () => Promise<void>;

  // UI state
  onSetMessage: (message: string) => void;
  isLoading: boolean;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatContextProvider({
  value,
  children,
}: {
  value: ChatContextValue;
  children: React.ReactNode;
}) {
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatContext must be used within ChatContextProvider");
  return ctx;
}
