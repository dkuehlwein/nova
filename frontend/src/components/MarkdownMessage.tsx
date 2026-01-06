"use client";

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Zap } from 'lucide-react';
import { CollapsibleToolCall } from './CollapsibleToolCall';

interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  timestamp: string;
  result?: string;  // Tool result content
  tool_call_id?: string;  // Link to tool call
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

// Regex to match tool call pattern: 🔧 **Using tool: toolname**\n```json\n{args}\n```
const TOOL_CALL_PATTERN = /🔧 \*\*Using tool: ([^*]+)\*\*\n```json\n([\s\S]*?)\n```/g;

function parseContentWithToolCalls(content: string | string[]) {
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

export function MarkdownMessage({ content, className = "", toolCalls, disableLinks = false }: MarkdownMessageProps) {
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
          components={disableLinks ? {
            // Disable links if requested (to prevent nested <a> tags)
            a: ({ children }) => <span className="text-blue-600 dark:text-blue-400">{children}</span>,
          } : undefined}
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
      {hasStreamingToolCalls && toolCalls?.map((toolCall, index) => {
        // Special handling for skill activation
        if (toolCall.tool === 'enable_skill') {
          const skillName = (toolCall.args as { skill_name?: string }).skill_name || 'Unknown';
          return <SkillActivationBlock key={`skill-${toolCall.tool_call_id || index}`} skillName={skillName} />;
        }
        // Regular tool call display
        return (
          <CollapsibleToolCall
            key={`streaming-tool-${toolCall.tool_call_id || index}`}
            toolName={toolCall.tool}
            args={JSON.stringify(toolCall.args, null, 2)}
            result={toolCall.result}
            tool_call_id={toolCall.tool_call_id}
          />
        );
      })}
      
      {/* Always render remaining content */}
      <div>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={disableLinks ? {
            // Disable links if requested (to prevent nested <a> tags)
            a: ({ children }) => <span className="text-blue-600 dark:text-blue-400">{children}</span>,
          } : undefined}
        >
          {hasStreamingToolCalls ? content : (parts.length > 0 ? parts.find(p => p.type === 'text')?.content || content : content)}
        </ReactMarkdown>
      </div>
      
      {/* Legacy format compatibility when no streaming tool calls */}
      {!hasStreamingToolCalls && parts.map((part, index) => {
        if (part.type === 'tool' && part.toolName && part.args) {
          // Special handling for skill activation in legacy format
          if (part.toolName === 'enable_skill') {
            try {
              const args = JSON.parse(part.args);
              return <SkillActivationBlock key={index} skillName={args.skill_name || 'Unknown'} />;
            } catch {
              return <SkillActivationBlock key={index} skillName="Unknown" />;
            }
          }
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