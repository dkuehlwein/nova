// Content part types for ordered rendering
export type ContentPart =
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
export function parseContentIntoParts(content: string): ContentPart[] {
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
