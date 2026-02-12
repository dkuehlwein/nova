"use client";

import { Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useChatContext } from "@/contexts/ChatContext";

interface WelcomeScreenProps {
  pendingDecisionsCount: number;
}

export function WelcomeScreen({
  pendingDecisionsCount,
}: WelcomeScreenProps) {
  const { onSetMessage, isLoading } = useChatContext();
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="w-16 h-16 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center mb-4">
        <Bot className="h-8 w-8 text-white" />
      </div>
      <h3 className="text-lg font-semibold mb-2">Welcome to Nova Chat</h3>
      <p className="text-muted-foreground max-w-md mb-6">
        I&apos;m Nova, your AI assistant. I can help you manage tasks, organize your team,
        track projects, and much more.
        {pendingDecisionsCount > 0 && (
          <span className="block mt-2 text-orange-600 font-medium">
            You have {pendingDecisionsCount} task(s) that need your decision!
          </span>
        )}
      </p>
      <div className="grid grid-cols-2 gap-3 max-w-lg">
        <Button
          variant="outline"
          onClick={() => onSetMessage("What can you help me with?")}
          disabled={isLoading}
        >
          Get Started
        </Button>
        <Button
          variant="outline"
          onClick={() => onSetMessage("Show me tasks that need my attention")}
          disabled={isLoading}
        >
          Check Tasks
        </Button>
      </div>
    </div>
  );
}
