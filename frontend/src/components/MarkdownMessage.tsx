"use client";

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CollapsibleToolCall } from './CollapsibleToolCall';

interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  timestamp: string;
  result?: string;  // Tool result content
  tool_call_id?: string;  // Link to tool call
}

interface MarkdownMessageProps {
  content: string;
  className?: string;
  toolCalls?: ToolCall[];
}

// Regex to match tool call pattern: 🔧 **Using tool: toolname**\n```json\n{args}\n```
const TOOL_CALL_PATTERN = /🔧 \*\*Using tool: ([^*]+)\*\*\n```json\n([\s\S]*?)\n```/g;

function parseContentWithToolCalls(content: string) {
  // Defensive check: ensure content is a string
  if (typeof content !== 'string') {
    console.warn('parseContentWithToolCalls received non-string content:', content);
    // If it's an array, join it; otherwise convert to string
    content = Array.isArray(content) ? content.join('\n\n') : String(content);
  }

  const parts: Array<{ type: 'text' | 'tool'; content: string; toolName?: string; args?: string }> = [];
  let lastIndex = 0;
  let match;

  // Reset the regex
  TOOL_CALL_PATTERN.lastIndex = 0;

  while ((match = TOOL_CALL_PATTERN.exec(content)) !== null) {
    // Add text before the tool call
    if (match.index > lastIndex) {
      const textBefore = content.slice(lastIndex, match.index);
      if (textBefore && textBefore.trim()) {
        parts.push({ type: 'text', content: textBefore });
      }
    }

    // Add the tool call
    parts.push({
      type: 'tool',
      content: match[0],
      toolName: match[1],
      args: match[2],
    });

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < content.length) {
    const remainingText = content.slice(lastIndex);
    if (remainingText && remainingText.trim()) {
      parts.push({ type: 'text', content: remainingText });
    }
  }

  return parts;
}

export function MarkdownMessage({ content, className = "", toolCalls }: MarkdownMessageProps) {
  // Defensive check: ensure content is a string
  if (typeof content !== 'string') {
    console.warn('MarkdownMessage received non-string content:', content);
    // If it's an array, join it; otherwise convert to string
    content = Array.isArray(content) ? content.join('\n\n') : String(content);
  }

  // Prioritize toolCalls prop over content parsing for better reliability
  const hasStreamingToolCalls = toolCalls && toolCalls.length > 0;
  const parts = hasStreamingToolCalls ? [] : parseContentWithToolCalls(content);

  // If no tool calls found in content and no toolCalls prop, render normally
  if (!hasStreamingToolCalls && (parts.length <= 1 && parts[0]?.type === 'text')) {
    return (
      <div className={`prose prose-sm max-w-none dark:prose-invert ${className}`}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Custom styling for different elements
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
            
            // Style code blocks
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            code: ({ children, inline }: any) => {
              if (inline) {
                return (
                  <code className="px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-sm font-mono">
                    {children}
                  </code>
                );
              }
              return (
                <code className="block p-3 bg-gray-50 dark:bg-gray-900 rounded-lg border text-sm font-mono overflow-x-auto whitespace-pre-wrap">
                  {children}
                </code>
              );
            },
            
            // Style pre blocks
            pre: ({ children }) => (
              <pre className="bg-gray-50 dark:bg-gray-900 rounded-lg border p-3 overflow-x-auto">
                {children}
              </pre>
            ),
            
            // Style headings
            h1: ({ children }) => <h1 className="text-lg font-semibold mb-2">{children}</h1>,
            h2: ({ children }) => <h2 className="text-base font-semibold mb-2">{children}</h2>,
            h3: ({ children }) => <h3 className="text-sm font-semibold mb-1">{children}</h3>,
            
            // Style strong/bold text
            strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
            
            // Style lists
            ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
            li: ({ children }) => <li className="text-sm">{children}</li>,
            
            // Style blockquotes
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 italic my-2">
                {children}
              </blockquote>
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  }

  // Render mixed content with tool calls
  return (
    <div className={`prose prose-sm max-w-none dark:prose-invert ${className}`}>
      {/* Render streaming tool calls first (from props) - modern approach */}
      {hasStreamingToolCalls && toolCalls?.map((toolCall, index) => (
        <CollapsibleToolCall
          key={`streaming-tool-${toolCall.tool_call_id || index}`}
          toolName={toolCall.tool}
          args={JSON.stringify(toolCall.args, null, 2)}
          result={toolCall.result}
          tool_call_id={toolCall.tool_call_id}
        />
      ))}
      
      {/* Always render remaining content */}
      <div>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Custom styling for different elements
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
            
            // Style code blocks
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            code: ({ children, inline }: any) => {
              if (inline) {
                return (
                  <code className="px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-sm font-mono">
                    {children}
                  </code>
                );
              }
              return (
                <code className="block p-3 bg-gray-50 dark:bg-gray-900 rounded-lg border text-sm font-mono overflow-x-auto whitespace-pre-wrap">
                  {children}
                </code>
              );
            },
            
            // Style pre blocks
            pre: ({ children }) => (
              <pre className="bg-gray-50 dark:bg-gray-900 rounded-lg border p-3 overflow-x-auto">
                {children}
              </pre>
            ),
            
            // Style headings
            h1: ({ children }) => <h1 className="text-lg font-semibold mb-2">{children}</h1>,
            h2: ({ children }) => <h2 className="text-base font-semibold mb-2">{children}</h2>,
            h3: ({ children }) => <h3 className="text-sm font-semibold mb-1">{children}</h3>,
            
            // Style strong/bold text
            strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
            
            // Style lists
            ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
            li: ({ children }) => <li className="text-sm">{children}</li>,
            
            // Style blockquotes
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 italic my-2">
                {children}
              </blockquote>
            ),
          }}
        >
          {hasStreamingToolCalls ? content : (parts.length > 0 ? parts.find(p => p.type === 'text')?.content || content : content)}
        </ReactMarkdown>
      </div>
      
      {/* Legacy format compatibility when no streaming tool calls */}
      {!hasStreamingToolCalls && parts.map((part, index) => {
        if (part.type === 'tool' && part.toolName && part.args) {
          return (
            <CollapsibleToolCall
              key={index}
              toolName={part.toolName}
              args={part.args}
            />
          );
        }
        return null; // Text content already handled above
      })}
    </div>
  );
} 