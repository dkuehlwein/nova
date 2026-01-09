"use client";

import { Send, Loader2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useCallback } from "react";

interface ChatInputProps {
  message: string;
  isLoading: boolean;
  isConnected: boolean;
  onMessageChange: (value: string) => void;
  onSend: () => void;
}

export function ChatInput({
  message,
  isLoading,
  isConnected,
  onMessageChange,
  onSend,
}: ChatInputProps) {
  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  }, [onSend]);

  return (
    <div className="p-4 border-t border-border bg-card">
      <div className="flex space-x-3 items-end">
        <div className="flex-1">
          <Textarea
            placeholder="Ask Nova anything... (Shift+Enter for new line, Enter to send)"
            value={message}
            onChange={(e) => onMessageChange(e.target.value)}
            onKeyDown={handleKeyPress}
            className="min-h-[60px] max-h-[120px] resize-none transition-none"
            rows={2}
            disabled={isLoading}
          />
        </div>
        <Button
          onClick={onSend}
          disabled={!message.trim() || isLoading}
          className="h-[60px] px-6 flex-shrink-0"
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>

      {!isConnected && (
        <div className="mt-2 text-sm text-orange-600 flex items-center">
          <AlertTriangle className="h-4 w-4 mr-1" />
          Connection issues detected. Some features may not work properly.
        </div>
      )}
    </div>
  );
}
