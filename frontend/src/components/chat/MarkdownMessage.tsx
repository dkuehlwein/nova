"use client";

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useState, useMemo } from 'react';
import { Zap, Brain, ChevronDown, ChevronRight } from 'lucide-react';
import { CollapsibleToolCall } from './CollapsibleToolCall';
import type { ToolCall } from '@/types/chat';
import { parseContentIntoParts } from '@/lib/markdown-parser';

// Component to display model thinking in a collapsible section
function ThinkingBlock({ thinking }: { thinking: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const firstLine = thinking.trim().split('\n')[0]?.substring(0, 60);

  return (
    <div className="my-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800/50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center space-x-2 text-left hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-slate-500 flex-shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-slate-500 flex-shrink-0" />
        )}
        <Brain className="h-4 w-4 text-slate-500" />
        <span className="font-medium text-sm text-slate-600 dark:text-slate-400">
          Thinking
        </span>
        {!isExpanded && firstLine && firstLine !== '...' && (
          <span className="text-xs text-slate-400 dark:text-slate-500 truncate max-w-[250px]">
            {firstLine}{firstLine.length >= 60 ? '...' : ''}
          </span>
        )}
      </button>
      {isExpanded && (
        <div className="px-3 pb-3 pt-1 border-t border-slate-200 dark:border-slate-700">
          <div className="text-xs text-slate-600 dark:text-slate-400 whitespace-pre-wrap font-mono bg-slate-100 dark:bg-slate-900 p-2 rounded max-h-64 overflow-y-auto">
            {thinking}
          </div>
        </div>
      )}
    </div>
  );
}

// Special component for skill activation display
function SkillActivationBlock({ skillName }: { skillName: string }) {
  return (
    <div className="my-2 border border-purple-200 dark:border-purple-800 rounded-lg bg-purple-50 dark:bg-purple-900/20">
      <div className="px-3 py-2 flex items-center space-x-2">
        <Zap className="h-4 w-4 text-purple-500" />
        <span className="font-medium text-sm text-purple-700 dark:text-purple-300">
          Skill Activated: {skillName}
        </span>
      </div>
    </div>
  );
}

interface MarkdownMessageProps {
  content: string | string[];
  className?: string;
  toolCalls?: ToolCall[];
  disableLinks?: boolean;
}

export function MarkdownMessage({ content, className = "", toolCalls, disableLinks = false }: MarkdownMessageProps) {
  // Defensive check: ensure content is a string
  if (typeof content !== 'string') {
    console.warn('MarkdownMessage received non-string content:', content);
    // If it's an array, join it; otherwise convert to string
    content = Array.isArray(content) ? content.join('\n\n') : String(content);
  }

  // Parse content into ordered parts (thinking blocks and text)
  const contentParts = useMemo(() => parseContentIntoParts(content), [content]);

  // Prioritize toolCalls prop over content parsing for better reliability
  const hasStreamingToolCalls = toolCalls && toolCalls.length > 0;

  // Helper to render markdown content
  const renderMarkdown = (text: string) => (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={disableLinks ? {
        a: ({ children }) => <span className="text-blue-600 dark:text-blue-400">{children}</span>,
      } : undefined}
    >
      {text}
    </ReactMarkdown>
  );

  // Helper to render a tool call
  const renderToolCall = (toolCall: ToolCall, index: number) => {
    if (toolCall.tool === 'enable_skill') {
      const skillName = (toolCall.args as { skill_name?: string }).skill_name || 'Unknown';
      return <SkillActivationBlock key={`skill-${toolCall.tool_call_id || index}`} skillName={skillName} />;
    }
    return (
      <CollapsibleToolCall
        key={`tool-${toolCall.tool_call_id || index}`}
        toolName={toolCall.tool}
        args={JSON.stringify(toolCall.args, null, 2)}
        result={toolCall.result}
        approved={toolCall.approved}
      />
    );
  };

  // Check if content has tool markers (loaded from history) vs streaming (no markers)
  const hasToolMarkers = contentParts.some(p => p.type === 'tool_marker');

  // Track which tool calls have been rendered via markers
  const renderedToolIndices = new Set<number>();

  // Render content parts in order
  return (
    <div className={`prose prose-sm max-w-none dark:prose-invert ${className}`}>
      {contentParts.map((part, partIndex) => {
        if (part.type === 'thinking') {
          return (
            <ThinkingBlock
              key={`thinking-${partIndex}`}
              thinking={part.content}
            />
          );
        } else if (part.type === 'tool_marker') {
          // Render tool call at its marker position
          const toolCall = toolCalls?.[part.toolIndex];
          if (toolCall) {
            renderedToolIndices.add(part.toolIndex);
            return renderToolCall(toolCall, part.toolIndex);
          }
          return null;
        } else {
          // Text part - render it
          // For streaming (no markers), render all tool calls after first text block
          const isFirstTextPart = contentParts.slice(0, partIndex).every(p => p.type === 'thinking');
          const shouldRenderAllToolCalls = !hasToolMarkers && isFirstTextPart && hasStreamingToolCalls;
          return (
            <div key={`text-${partIndex}`}>
              {renderMarkdown(part.content)}
              {/* Render all tool calls after first text block (streaming mode only) */}
              {shouldRenderAllToolCalls && toolCalls?.map((tc, i) => renderToolCall(tc, i))}
            </div>
          );
        }
      })}

      {/* If there are no text parts but we have tool calls (streaming mode), render them */}
      {!hasToolMarkers && contentParts.every(p => p.type === 'thinking') && hasStreamingToolCalls && (
        <div>
          {toolCalls?.map((tc, i) => renderToolCall(tc, i))}
        </div>
      )}

      {/* If content is empty but we have tool calls */}
      {contentParts.length === 0 && hasStreamingToolCalls && (
        <div>
          {toolCalls?.map((tc, i) => renderToolCall(tc, i))}
        </div>
      )}

      {/* Render any tool calls that weren't rendered via markers (fallback) */}
      {hasToolMarkers && hasStreamingToolCalls && (
        <>
          {toolCalls?.filter((_, i) => !renderedToolIndices.has(i)).map((tc, i) => renderToolCall(tc, i))}
        </>
      )}
    </div>
  );
} 