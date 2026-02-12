export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  timestamp: string;
  result?: string;
  tool_call_id?: string;
  approved?: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  toolCalls?: ToolCall[];
  metadata?: {
    type?: string;
    collapsible_content?: string;
    is_collapsible?: boolean;
    title?: string;
    trace_id?: string;
    phoenix_url?: string;
  };
  phoenixUrl?: string;
}

export interface PendingEscalation {
  question: string;
  instructions: string;
  tool_call_id?: string;
  type?: 'user_question' | 'tool_approval_request';
  tool_name?: string;
  tool_args?: Record<string, unknown>;
}

export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  pendingEscalation: PendingEscalation | null;
  phoenixUrl: string | null;
}

export interface StreamMessageData {
  role: string;
  content: string;
  timestamp?: string;
  metadata?: {
    type?: string;
    is_collapsible?: boolean;
    title?: string;
  };
}

export interface StreamToolData {
  tool: string;
  args?: Record<string, unknown>;
  result?: string;
  tool_call_id?: string;
  timestamp?: string;
}

export interface StreamErrorData {
  error: string;
  details?: string;
  tool_call_id?: string;
}

export interface StreamStartData {
  thread_id: string;
  timestamp: string;
  trace_id?: string;
  phoenix_url?: string;
}

export interface StreamTraceData {
  trace_id?: string;
  phoenix_url: string;
}

export interface StreamEvent {
  type: 'start' | 'message' | 'tool_call' | 'tool_result' | 'complete' | 'error' | 'trace_info';
  data: StreamStartData | StreamMessageData | StreamToolData | StreamErrorData | StreamTraceData | Record<string, unknown>;
}
