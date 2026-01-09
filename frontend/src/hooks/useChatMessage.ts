"use client";

import { useState, useCallback } from "react";

export interface UseChatMessageReturn {
  copiedMessageId: string | null;
  ratedMessages: Record<string, 'up' | 'down'>;
  handleCopyMessage: (messageId: string, content: string) => Promise<void>;
  handleRateMessage: (messageId: string, rating: 'up' | 'down') => void;
}

/**
 * Hook for managing message-level interactions (copy, rate)
 */
export function useChatMessage(): UseChatMessageReturn {
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [ratedMessages, setRatedMessages] = useState<Record<string, 'up' | 'down'>>({});

  const handleCopyMessage = useCallback(async (messageId: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (err) {
      console.error('Failed to copy message:', err);
    }
  }, []);

  const handleRateMessage = useCallback((messageId: string, rating: 'up' | 'down') => {
    setRatedMessages(prev => {
      const newRatings = { ...prev };
      if (prev[messageId] === rating) {
        // Toggle off if clicking same rating
        delete newRatings[messageId];
      } else {
        newRatings[messageId] = rating;
      }
      return newRatings;
    });
    // TODO: Send rating to backend for analytics
  }, []);

  return {
    copiedMessageId,
    ratedMessages,
    handleCopyMessage,
    handleRateMessage,
  };
}
