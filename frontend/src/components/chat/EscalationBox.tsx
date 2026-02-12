"use client";

import { AlertTriangle, Send, Loader2, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";
import { useChatContext } from "@/contexts/ChatContext";

interface EscalationBoxProps {
  question: string;
  instructions: string;
  escalationType?: 'user_question' | 'tool_approval_request';
  toolName?: string;
  toolArgs?: Record<string, unknown>;
}

export function EscalationBox({
  question,
  instructions,
  escalationType = 'user_question',
  toolName,
  toolArgs,
}: EscalationBoxProps) {
  const {
    onEscalationSubmit: onSubmit,
    onEscalationApprove: onApprove,
    onEscalationDeny: onDeny,
    onEscalationAlwaysAllow: onAlwaysAllow,
    isLoading: isSubmitting,
  } = useChatContext();
  const [response, setResponse] = useState("");

  const handleSubmit = async () => {
    if (response.trim() && !isSubmitting) {
      await onSubmit(response);
      setResponse(""); // Clear the response after submitting
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Tool approval UI - compact inline design with always-visible parameters
  if (escalationType === 'tool_approval_request') {
    return (
      <div className="my-3 border border-blue-200 dark:border-blue-700 bg-blue-50/50 dark:bg-blue-900/20 rounded-lg overflow-hidden">
        {/* Header row with tool name and action buttons */}
        <div className="flex items-center justify-between px-3 py-2 bg-blue-100/50 dark:bg-blue-800/30 border-b border-blue-200 dark:border-blue-700">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
              {toolName}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              variant="ghost"
              size="sm"
              onClick={onDeny}
              disabled={isSubmitting}
              className="h-7 px-2 text-xs text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-700"
            >
              {isSubmitting ? <Loader2 className="h-3 w-3 animate-spin" /> : "Deny"}
            </Button>
            <Button
              size="sm"
              onClick={onApprove}
              disabled={isSubmitting}
              className="h-7 px-2 text-xs bg-blue-600 hover:bg-blue-700 text-white"
            >
              {isSubmitting ? <Loader2 className="h-3 w-3 animate-spin" /> : "Allow"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onAlwaysAllow}
              disabled={isSubmitting}
              className="h-7 px-2 text-xs border-green-300 dark:border-green-700 text-green-700 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30"
              title="Add to auto-approved tools list"
            >
              {isSubmitting ? <Loader2 className="h-3 w-3 animate-spin" /> : "Always"}
            </Button>
          </div>
        </div>

        {/* Parameters - always visible */}
        {toolArgs && Object.keys(toolArgs).length > 0 && (
          <pre className="text-xs p-2 overflow-x-auto text-gray-700 dark:text-gray-300 bg-white/50 dark:bg-gray-900/30 max-h-32 overflow-y-auto">
            {JSON.stringify(toolArgs, null, 2)}
          </pre>
        )}
      </div>
    )
  }
  
  // Regular user question UI (existing orange styling, text area)
  return (
    <div className="my-4 border-2 border-orange-200 dark:border-orange-700 bg-orange-50 dark:bg-orange-900/30 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center space-x-2 mb-3">
        <AlertTriangle className="h-5 w-5 text-orange-600 dark:text-orange-400" />
        <Badge variant="secondary" className="bg-orange-100 dark:bg-orange-800/50 text-orange-800 dark:text-orange-200 border-orange-300 dark:border-orange-600">
          Decision Required
        </Badge>
      </div>

      {/* Question */}
      <div className="mb-4">
        <h4 className="font-medium text-orange-900 dark:text-orange-100 mb-2">Question from Nova:</h4>
        <div className="bg-white dark:bg-gray-800 border border-orange-200 dark:border-orange-700 rounded-md p-3 text-sm text-orange-800 dark:text-orange-200">
          {question}
        </div>
      </div>

      {/* Instructions */}
      <div className="mb-4 text-xs text-orange-600 dark:text-orange-400">
        {instructions}
      </div>

      {/* Response Input */}
      <div className="space-y-3">
        <div>
          <label className="text-sm font-medium text-orange-900 dark:text-orange-100 block mb-2">
            Your Response:
          </label>
          <Textarea
            placeholder="Type your response here... (Shift+Enter for new line, Enter to send)"
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            onKeyDown={handleKeyPress}
            className="min-h-[80px] bg-white dark:bg-gray-800 border-orange-200 dark:border-orange-700 focus:border-orange-400 dark:focus:border-orange-500 focus:ring-orange-400 dark:focus:ring-orange-500 text-gray-900 dark:text-gray-100 placeholder:text-gray-500 dark:placeholder:text-gray-400"
            disabled={isSubmitting}
            rows={3}
          />
        </div>

        <div className="flex justify-between items-center">
          <div className="text-xs text-orange-600 dark:text-orange-400">
            Your response will be sent to Nova to continue processing this task.
          </div>
          <Button
            onClick={handleSubmit}
            disabled={!response.trim() || isSubmitting}
            className="bg-orange-600 hover:bg-orange-700 text-white"
            size="sm"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Sending...
              </>
            ) : (
              <>
                <Send className="h-4 w-4 mr-2" />
                Send Response
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
} 