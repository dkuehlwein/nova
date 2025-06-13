"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";

interface CollapsibleToolCallProps {
  toolName: string;
  args: string;
}

export function CollapsibleToolCall({ toolName, args }: CollapsibleToolCallProps) {
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
            {isExpanded ? 'Hide' : 'Show'} arguments
          </span>
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-500" />
          )}
        </div>
      </button>
      
      {/* Collapsible arguments */}
      {isExpanded && (
        <div className="px-3 pb-3">
          <div className="border-t border-gray-200 dark:border-gray-600 pt-2">
            <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">Arguments:</div>
            <pre className="bg-gray-100 dark:bg-gray-900 rounded p-2 text-xs font-mono overflow-x-auto border">
              {args}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
} 