"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench, Copy, Check, ShieldCheck } from "lucide-react";

interface CollapsibleToolCallProps {
  toolName: string;
  args: string;
  result?: string;
  approved?: boolean;
}

export function CollapsibleToolCall({ toolName, args, result, approved }: CollapsibleToolCallProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopyToolName = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(toolName);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      try {
        const blob = new Blob([toolName], { type: 'text/plain' });
        await navigator.clipboard.write([new ClipboardItem({ 'text/plain': blob })]);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      } catch {
        // Both clipboard APIs failed - don't show false success
      }
    }
  };

  return (
    <div className="my-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800/50 group">
      {/* Tool header - always visible */}
      <div className="w-full px-3 py-2 flex items-center justify-between">
        <div className="flex items-center space-x-2 min-w-0">
          <Wrench className="h-4 w-4 text-blue-500 flex-shrink-0" />
          <span className="text-sm text-gray-600 dark:text-gray-400 flex-shrink-0">Using tool:</span>
          <span
            className="font-medium text-sm font-mono select-all cursor-text truncate"
            onClick={(e) => e.stopPropagation()}
          >
            {toolName}
          </span>
          <button
            onClick={handleCopyToolName}
            className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-opacity flex-shrink-0"
            title="Copy tool name"
          >
            {copied ? (
              <Check className="h-3 w-3 text-green-500" />
            ) : (
              <Copy className="h-3 w-3 text-gray-400" />
            )}
          </button>
          {approved && (
            <span className="flex items-center space-x-1 text-xs text-green-600 dark:text-green-400 flex-shrink-0">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Approved</span>
            </span>
          )}
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center space-x-1 ml-2 px-1.5 py-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors flex-shrink-0"
        >
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {isExpanded ? 'Hide' : 'Show'}
          </span>
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-500" />
          )}
        </button>
      </div>

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
