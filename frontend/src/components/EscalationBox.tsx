"use client";

import { AlertTriangle, Send, Loader2, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";

interface EscalationBoxProps {
  question: string;
  instructions: string;
  escalationType?: 'user_question' | 'tool_approval_request';
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  onSubmit: (response: string) => Promise<void>;
  onApprove?: () => Promise<void>;
  onDeny?: () => Promise<void>;
  onAlwaysAllow?: () => Promise<void>;
  isSubmitting?: boolean;
}

export function EscalationBox({
  question,
  instructions,
  escalationType = 'user_question',
  toolName,
  toolArgs,
  onSubmit,
  onApprove,
  onDeny,
  onAlwaysAllow,
  isSubmitting = false
}: EscalationBoxProps) {
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

  // Tool approval UI (blue styling, buttons instead of text area)
  if (escalationType === 'tool_approval_request') {
    return (
      <div className="my-4 border-2 border-blue-200 bg-blue-50 rounded-lg p-4">
        <div className="flex items-center space-x-2 mb-3">
          <Shield className="h-5 w-5 text-blue-600" />
          <Badge className="bg-blue-100 text-blue-800 border-blue-300">
            Tool Approval Required
          </Badge>
        </div>
        
        <div className="mb-4">
          <h4 className="font-medium text-blue-900 mb-2">Nova wants to use: {toolName}</h4>
          <div className="bg-white border border-blue-200 rounded-md p-3 text-sm">
            <p className="text-blue-800 mb-2">Nova is requesting permission to call this tool.</p>
            {toolArgs && Object.keys(toolArgs).length > 0 && (
              <details className="mt-2">
                <summary className="text-xs text-blue-600 cursor-pointer hover:text-blue-800">
                  Show parameters
                </summary>
                <pre className="text-xs mt-1 bg-gray-50 p-2 rounded border overflow-x-auto text-gray-800">
                  {JSON.stringify(toolArgs, null, 2)}
                </pre>
              </details>
            )}
          </div>
        </div>
        
        <div className="flex gap-3 flex-wrap">
          <Button 
            variant="outline" 
            onClick={onDeny} 
            disabled={isSubmitting}
            className="border-red-300 text-red-700 hover:bg-red-50"
          >
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            Deny
          </Button>
          <Button 
            onClick={onApprove} 
            disabled={isSubmitting}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            Approve Once
          </Button>
          <Button 
            onClick={onAlwaysAllow} 
            disabled={isSubmitting}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            Always Allow
          </Button>
        </div>
        
        <div className="mt-3 text-xs text-blue-600">
          Your choice will be remembered. &quot;Always Allow&quot; adds this tool to your approved list.
        </div>
      </div>
    )
  }
  
  // Regular user question UI (existing orange styling, text area)
  return (
    <div className="my-4 border-2 border-orange-200 bg-orange-50 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center space-x-2 mb-3">
        <AlertTriangle className="h-5 w-5 text-orange-600" />
        <Badge variant="secondary" className="bg-orange-100 text-orange-800 border-orange-300">
          Decision Required
        </Badge>
      </div>

      {/* Question */}
      <div className="mb-4">
        <h4 className="font-medium text-orange-900 mb-2">Question from Nova:</h4>
        <div className="bg-white border border-orange-200 rounded-md p-3 text-sm text-orange-800">
          {question}
        </div>
      </div>

      {/* Instructions */}
      <div className="mb-4 text-xs text-orange-600">
        {instructions}
      </div>

      {/* Response Input */}
      <div className="space-y-3">
        <div>
          <label className="text-sm font-medium text-orange-900 block mb-2">
            Your Response:
          </label>
          <Textarea
            placeholder="Type your response here... (Shift+Enter for new line, Enter to send)"
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            onKeyDown={handleKeyPress}
            className="min-h-[80px] bg-white border-orange-200 focus:border-orange-400 focus:ring-orange-400 text-gray-900 placeholder:text-gray-500"
            disabled={isSubmitting}
            rows={3}
          />
        </div>
        
        <div className="flex justify-between items-center">
          <div className="text-xs text-orange-600">
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