"use client";

import { AlertTriangle, Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";

interface EscalationBoxProps {
  question: string;
  instructions: string;
  onSubmit: (response: string) => Promise<void>;
  isSubmitting?: boolean;
}

export function EscalationBox({ question, instructions, onSubmit, isSubmitting = false }: EscalationBoxProps) {
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