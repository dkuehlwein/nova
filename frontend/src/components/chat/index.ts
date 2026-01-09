// Chat components barrel export

// Moved from components root
export { EscalationBox } from "./EscalationBox";
export { SystemMessage } from "./SystemMessage";
export { MarkdownMessage } from "./MarkdownMessage";
export { CollapsibleToolCall } from "./CollapsibleToolCall";

// New chat page components
export { ChatSidebar } from "./ChatSidebar";
export { ChatHeader } from "./ChatHeader";
export { ChatMessageList } from "./ChatMessageList";
export { ChatMessageBubble } from "./ChatMessageBubble";
export { ChatInput } from "./ChatInput";
export { PendingDecisionItem } from "./PendingDecisionItem";
export { ChatHistoryItem } from "./ChatHistoryItem";
export { WelcomeScreen } from "./WelcomeScreen";

// Re-export types
export type { PendingDecision } from "./PendingDecisionItem";
export type { ChatHistoryItemData } from "./ChatHistoryItem";
