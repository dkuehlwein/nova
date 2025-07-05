"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";

interface CollapsibleToolCallProps {
  toolName: string;
  args: string;
  result?: string;  // Tool execution result
  tool_call_id?: string;  // Link to tool call
}

export function CollapsibleToolCall({ toolName, args, result }: CollapsibleToolCallProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="my-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800/50">
      {/* Tool header - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-gray-100 dark:hover:bg-gray-700/50 rounded-lg transition-colors"
      >
        <div className="flex items-center space-x-2">
          <Wrench className="h-4 w-4 text-blue-500" />
          <span className="font-medium text-sm">Using tool: {toolName}</span>
        </div>
        <div className="flex items-center space-x-1">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {isExpanded ? 'Hide' : 'Show'} details
          </span>
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-500" />
          )}
        </div>
      </button>
      
      {/* Collapsible details */}
      {isExpanded && (
        <div className="px-3 pb-3">
          <div className="border-t border-gray-200 dark:border-gray-600 pt-2 space-y-3">
            {/* Arguments */}
            <div>
              <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">Arguments:</div>
              <pre className="bg-gray-100 dark:bg-gray-900 rounded p-2 text-xs font-mono overflow-x-auto border">
                {args}
              </pre>
            </div>
            
            {/* Results */}
            {result && (
              <div>
                <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">Result:</div>
                <pre className={`rounded p-2 text-xs font-mono overflow-x-auto border ${
                  result.startsWith('Error:') 
                    ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800' 
                    : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                }`}>
                  {result}
                </pre>
              </div>
            )}
            
            {/* No result indicator */}
            {!result && (
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-500 italic">
                  Result not available (tool may still be executing)
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
} 