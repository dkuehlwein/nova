"use client";

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useState } from 'react';
import { Zap, Brain, ChevronDown, ChevronRight } from 'lucide-react';
import { CollapsibleToolCall } from './CollapsibleToolCall';

interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  timestamp: string;
  result?: string;  // Tool result content
  tool_call_id?: string;  // Link to tool call
}

// Component to display model thinking in a collapsible section
function ThinkingBlock({ thinking, index }: { thinking: string; index?: number }) {
  const [isExpanded, setIsExpanded] = useState(false);

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
          {index !== undefined ? `Thinking (${index + 1})` : 'Model Thinking'}
        </span>
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

// Content part types for ordered rendering
type ContentPart =
  | { type: 'thinking'; content: string }
  | { type: 'text'; content: string }
  | { type: 'tool_marker'; toolIndex: number };

// Parse text for tool markers [[TOOL:index]] and split into text/marker parts
function parseTextWithToolMarkers(text: string): ContentPart[] {
  const parts: ContentPart[] = [];
  const toolMarkerRegex = /\[\[TOOL:(\d+)\]\]/g;
  let lastIndex = 0;
  let match;

  while ((match = toolMarkerRegex.exec(text)) !== null) {
    // Add text before the marker
    const textBefore = text.slice(lastIndex, match.index).trim();
    if (textBefore) {
      parts.push({ type: 'text', content: textBefore });
    }
    // Add the tool marker
    parts.push({ type: 'tool_marker', toolIndex: parseInt(match[1], 10) });
    lastIndex = match.index + match[0].length;
  }

  // Add remaining text after last marker
  const textAfter = text.slice(lastIndex).trim();
  if (textAfter) {
    parts.push({ type: 'text', content: textAfter });
  }

  return parts;
}

// Parse content into ordered parts (thinking blocks, text, and tool markers)
// Preserves the order: thinking1, text1, tool1, thinking2, text2, tool2, etc.
// Also handles incomplete thinking blocks during streaming (has <think> but no </think> yet)
function parseContentIntoParts(content: string): ContentPart[] {
  const parts: ContentPart[] = [];

  // Pattern to match </think> tags (with optional opening <think>)
  // We split on </think> to preserve order
  const segments = content.split(/<\/think>/i);

  // Helper to add text content, parsing for tool markers
  const addTextContent = (text: string) => {
    const trimmed = text.trim();
    if (trimmed) {
      // Check for tool markers in the text
      const textParts = parseTextWithToolMarkers(trimmed);
      parts.push(...textParts);
    }
  };

  for (let i = 0; i < segments.length; i++) {
    const segment = segments[i];

    if (i < segments.length - 1) {
      // This segment ends with </think>, so it contains thinking
      // Check if it starts with <think> and remove it
      const thinkStartMatch = segment.match(/^([\s\S]*?)<think>\s*([\s\S]*)$/i);

      if (thinkStartMatch) {
        // There's text before <think>
        addTextContent(thinkStartMatch[1]);
        const thinkingContent = thinkStartMatch[2].trim();
        if (thinkingContent) {
          parts.push({ type: 'thinking', content: thinkingContent });
        }
      } else {
        // No <think> tag - the segment before </think> may contain tool markers
        // Parse for tool markers first, then treat remaining text as thinking
        const toolMarkerRegex = /\[\[TOOL:(\d+)\]\]/g;
        let lastIndex = 0;
        let match;
        const thinkingParts: string[] = [];

        while ((match = toolMarkerRegex.exec(segment)) !== null) {
          // Add text before the marker as thinking content
          const textBefore = segment.slice(lastIndex, match.index).trim();
          if (textBefore) {
            thinkingParts.push(textBefore);
          }
          // If we have accumulated thinking content, push it before the tool marker
          if (thinkingParts.length > 0) {
            parts.push({ type: 'thinking', content: thinkingParts.join('\n\n') });
            thinkingParts.length = 0;
          }
          // Add the tool marker
          parts.push({ type: 'tool_marker', toolIndex: parseInt(match[1], 10) });
          lastIndex = match.index + match[0].length;
        }

        // Add remaining text after last marker as thinking
        const textAfter = segment.slice(lastIndex).trim();
        if (textAfter) {
          thinkingParts.push(textAfter);
        }
        if (thinkingParts.length > 0) {
          parts.push({ type: 'thinking', content: thinkingParts.join('\n\n') });
        }
      }
    } else {
      // Last segment - this is text after the last </think>
      // BUT: Check if there's an incomplete thinking block (streaming scenario)
      const incompleteThinkMatch = segment.match(/^([\s\S]*?)<think>\s*([\s\S]*)$/i);

      if (incompleteThinkMatch) {
        // Has <think> but no </think> yet - this is an incomplete thinking block during streaming
        addTextContent(incompleteThinkMatch[1]);
        const thinkingContent = incompleteThinkMatch[2].trim();
        // Always push thinking content, even if empty (shows "thinking..." indicator)
        parts.push({ type: 'thinking', content: thinkingContent || '...' });
      } else {
        // Regular text content (may contain tool markers)
        addTextContent(segment);
      }
    }
  }

  // If no </think> was found and no parts added, check for incomplete thinking
  if (segments.length === 1 && parts.length === 0) {
    const incompleteThinkMatch = content.match(/^([\s\S]*?)<think>\s*([\s\S]*)$/i);

    if (incompleteThinkMatch) {
      // Incomplete thinking block during streaming
      addTextContent(incompleteThinkMatch[1]);
      const thinkingContent = incompleteThinkMatch[2].trim();
      // Always push thinking content, even if empty (shows "thinking..." indicator)
      parts.push({ type: 'thinking', content: thinkingContent || '...' });
    } else {
      // Plain text content (may contain tool markers)
      addTextContent(content);
    }
  }

  return parts;
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
  const contentParts = parseContentIntoParts(content);

  // Count thinking blocks for numbering (only number if multiple)
  const thinkingCount = contentParts.filter(p => p.type === 'thinking').length;
  let thinkingIndex = 0;

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
        tool_call_id={toolCall.tool_call_id}
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
          const currentThinkingIndex = thinkingIndex++;
          return (
            <ThinkingBlock
              key={`thinking-${partIndex}`}
              thinking={part.content}
              index={thinkingCount > 1 ? currentThinkingIndex : undefined}
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