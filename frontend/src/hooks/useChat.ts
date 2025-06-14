import { useState, useCallback, useRef } from 'react';
import { apiRequest, API_ENDPOINTS, getApiBaseUrlSync } from '@/lib/api';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  metadata?: {
    type?: string;
    collapsible_content?: string;
    is_collapsible?: boolean;
    title?: string;
  };
}

export interface PendingEscalation {
  question: string;
  instructions: string;
  tool_call_id?: string;
}

export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  pendingEscalation: PendingEscalation | null;
}

interface StreamMessageData {
  role: string;
  content: string;
  timestamp?: string;
}

interface StreamToolData {
  tool: string;
  args?: Record<string, unknown>;
  result?: unknown;
  timestamp?: string;
}

interface StreamErrorData {
  error: string;
  details?: string;
}

export interface StreamEvent {
  type: 'message' | 'tool_call' | 'tool_result' | 'complete' | 'error';
  data: StreamMessageData | StreamToolData | StreamErrorData | Record<string, unknown>;
}

export function useChat() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    error: null,
    isConnected: true, // Start as connected to avoid initial health check
    pendingEscalation: null,
  });

  const [currentThreadId, setCurrentThreadId] = useState(() => `chat-${Date.now()}`);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Add a message to the chat
  const addMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
    };

    setState(prev => ({
      ...prev,
      messages: [...prev.messages, newMessage],
    }));

    return newMessage.id;
  }, []);

  // Update a message (useful for streaming)
  const updateMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    setState(prev => ({
      ...prev,
      messages: prev.messages.map(msg => 
        msg.id === id ? { ...msg, ...updates } : msg
      ),
    }));
  }, []);

  // Load an existing chat conversation
  const loadChat = useCallback(async (chatId: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      // Set the thread ID first (especially important for task threads)
      setCurrentThreadId(chatId);
      
      // Try to fetch chat messages from the backend
      try {
        const backendMessages = await apiRequest<{
          id: string;
          sender: string;
          content: string;
          created_at: string;
          needs_decision: boolean;
        }[]>(API_ENDPOINTS.chatMessages(chatId));

        // Convert backend messages to frontend format
        const chatMessages: ChatMessage[] = backendMessages.map((msg, index) => ({
          id: msg.id || `loaded-msg-${index}`,
          role: msg.sender === 'user' ? 'user' : (msg.sender === 'system' ? 'system' : 'assistant'),
          content: msg.content,
          timestamp: msg.created_at,
          isStreaming: false,
          metadata: (msg as {metadata?: {type?: string; is_collapsible?: boolean; title?: string}}).metadata || undefined,
        }));

        // Set the messages
        setState(prev => ({
          ...prev,
          messages: chatMessages,
          isLoading: false,
          error: null,
        }));

        console.log(`Loaded chat ${chatId} with ${chatMessages.length} messages`);
        
      } catch {
        // For task threads that don't exist yet, this is normal
        // Clear messages and prepare for a new conversation
        console.log(`Chat thread ${chatId} not found or empty, starting new conversation`);
        setState(prev => ({
          ...prev,
          messages: [],
          isLoading: false,
          error: null,
        }));
      }
      
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load chat';
      console.error('Failed to load chat:', error);
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
    }
  }, []);

  // Send a message with streaming support
  const sendMessage = useCallback(async (content: string, useStreaming: boolean = true) => {
    if (!content.trim()) return;

    // Add user message
    const userMessageId = addMessage({
      role: 'user',
      content: content.trim(),
    });

    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      if (useStreaming) {
        // Use streaming endpoint
        const assistantMessageId = addMessage({
          role: 'assistant',
          content: '',
          isStreaming: true,
        });

        let assistantContent = '';
        let assistantTimestamp: string | null = null;

        // Cancel any ongoing request
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        const baseUrl = getApiBaseUrlSync();
        const response = await fetch(`${baseUrl}${API_ENDPOINTS.chatStream}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            messages: state.messages.concat([{
              role: 'user',
              content: content.trim(),
              timestamp: new Date().toISOString(),
              id: userMessageId,
            }]).map(msg => ({
              role: msg.role,
              content: msg.content,
            })),
            thread_id: currentThreadId,
            stream: true,
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response reader available');
        }

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = new TextDecoder().decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  const event: StreamEvent = data;

                  switch (event.type) {
                    case 'message':
                      const messageData = event.data as StreamMessageData;
                      if (messageData.role === 'assistant') {
                        // Store timestamp from the first message
                        if (messageData.timestamp && !assistantTimestamp) {
                          assistantTimestamp = messageData.timestamp;
                        }
                        
                        // Accumulate content instead of overwriting
                        if (assistantContent && messageData.content) {
                          // Add separator between responses for readability
                          assistantContent += '\n\n' + messageData.content;
                        } else {
                          assistantContent = messageData.content;
                        }
                        updateMessage(assistantMessageId, {
                          content: assistantContent,
                          isStreaming: true,
                          timestamp: assistantTimestamp || new Date().toISOString(),
                        });
                      }
                      break;

                    case 'tool_call':
                      // Handle tool calls for display purposes
                      // You can display tool calls if needed
                      break;

                    case 'complete':
                      updateMessage(assistantMessageId, {
                        content: assistantContent,
                        isStreaming: false,
                        timestamp: assistantTimestamp || new Date().toISOString(),
                      });
                      break;

                    case 'error':
                      const errorData = event.data as StreamErrorData;
                      setState(prev => ({ ...prev, error: errorData.error }));
                      updateMessage(assistantMessageId, {
                        content: assistantContent || 'Error occurred while processing your message.',
                        isStreaming: false,
                        timestamp: assistantTimestamp || new Date().toISOString(),
                      });
                      break;
                  }
                } catch (parseError) {
                  console.warn('Failed to parse streaming data:', parseError);
                }
              }
            }
          }
        } finally {
          reader.releaseLock();
        }

      } else {
        // Use non-streaming endpoint
        const response = await apiRequest<{
          message: { content: string };
          thread_id: string;
        }>(API_ENDPOINTS.chat, {
          method: 'POST',
          body: JSON.stringify({
            messages: state.messages.concat([{
              role: 'user',
              content: content.trim(),
              timestamp: new Date().toISOString(),
              id: userMessageId,
            }]).map(msg => ({
              role: msg.role,
              content: msg.content,
            })),
            thread_id: currentThreadId,
            stream: false,
          }),
        });

        addMessage({
          role: 'assistant',
          content: response.message.content,
        });
      }

      setState(prev => ({ ...prev, isConnected: true }));

    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        // Request was cancelled, this is expected
        return;
      }

      console.error('Chat error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message';
      setState(prev => ({
        ...prev,
        error: errorMessage,
        isConnected: false,
      }));

      addMessage({
        role: 'assistant',
        content: 'Sorry, I encountered an error while processing your message. Please try again.',
      });
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [state.messages, currentThreadId, addMessage, updateMessage]);

  // Stop any ongoing streaming
  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setState(prev => ({ ...prev, isLoading: false }));
  }, []);

  // Clear the chat
  const clearChat = useCallback(() => {
    stopStreaming();
    setState({
      messages: [],
      isLoading: false,
      error: null,
      isConnected: true, // Keep connected status
      pendingEscalation: null,
    });
    // Generate a new thread ID for the new chat
    setCurrentThreadId(`chat-${Date.now()}`);
  }, [stopStreaming]);

  // Check agent health (manual trigger only)
  const checkHealth = useCallback(async () => {
    try {
      const health = await apiRequest<{
        status: string;
        agent_ready: boolean;
      }>(API_ENDPOINTS.chatHealth);

      setState(prev => ({
        ...prev,
        isConnected: health.agent_ready,
        error: health.agent_ready ? null : 'Agent not ready',
      }));

      return health;
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to check agent health';
      setState(prev => ({
        ...prev,
        isConnected: false,
        error: errorMessage,
      }));
      throw error;
    }
  }, []);

  // Test the agent
  const testAgent = useCallback(async () => {
    try {
      const result = await apiRequest<{
        response: string;
        status: string;
      }>(API_ENDPOINTS.chatTest, { method: 'POST' });

      return result;
    } catch (error: unknown) {
      console.error('Agent test failed:', error);
      throw error;
    }
  }, []);

  // Load task chat with escalation support
  const loadTaskChat = useCallback(async (taskId: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      // Set the thread ID for task chat
      const threadId = `core_agent_task_${taskId}`;
      setCurrentThreadId(threadId);
      
      // Use the new task chat data endpoint that includes escalation info
      const taskChatData = await apiRequest<{
        messages: Array<{
          id: string;
          sender: string;
          content: string;
          created_at: string;
          needs_decision: boolean;
          metadata?: {
            type?: string;
            is_collapsible?: boolean;
            title?: string;
          };
        }>;
        pending_escalation?: {
          question: string;
          instructions: string;
          tool_call_id?: string;
        };
      }>(API_ENDPOINTS.taskChatData(threadId));

      // Convert messages to ChatMessage format (with metadata!)
      const chatMessages: ChatMessage[] = taskChatData.messages.map((msg, index) => ({
        id: msg.id || `loaded-msg-${index}`,
        role: msg.sender === 'user' ? 'user' : (msg.sender === 'system' ? 'system' : 'assistant'),
        content: msg.content,
        timestamp: msg.created_at,
        isStreaming: false,
        metadata: (msg as {metadata?: {type?: string; is_collapsible?: boolean; title?: string}}).metadata || undefined,
      }));

      // Use escalation data from the endpoint
      const pendingEscalation = taskChatData.pending_escalation || null;

      // Set the messages and escalation state
      setState(prev => ({
        ...prev,
        messages: chatMessages,
        isLoading: false,
        error: null,
        pendingEscalation,
      }));

      console.log(`Loaded task chat ${taskId} with ${chatMessages.length} messages`);
      if (pendingEscalation) {
        console.log('Pending escalation detected:', pendingEscalation);
      }
      
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load task chat';
      console.error('Failed to load task chat:', error);
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
        pendingEscalation: null,
      }));
    }
  }, []);

  // Send escalation response
  const sendEscalationResponse = useCallback(async (taskId: string, response: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      await apiRequest(API_ENDPOINTS.taskChatMessage(taskId), {
        method: 'POST',
        body: JSON.stringify({
          content: response,
          author: 'human'
        }),
      });

      // Clear the escalation and reload the task chat
      setState(prev => ({ ...prev, pendingEscalation: null }));
      await loadTaskChat(taskId);
      
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to send escalation response';
      console.error('Failed to send escalation response:', error);
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
    }
  }, [loadTaskChat]);

  return {
    // State
    messages: state.messages,
    isLoading: state.isLoading,
    error: state.error,
    isConnected: state.isConnected,
    pendingEscalation: state.pendingEscalation,
    threadId: currentThreadId,

    // Actions
    sendMessage,
    clearChat,
    stopStreaming,
    addMessage,
    updateMessage,
    loadChat, // New function for loading existing chats
    loadTaskChat, // Load task chat with escalation support
    sendEscalationResponse, // Send response to escalation

    // Utilities (manual trigger only)
    checkHealth,
    testAgent,
  };
} 