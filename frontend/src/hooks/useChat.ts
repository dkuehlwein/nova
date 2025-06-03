import { useState, useCallback, useRef } from 'react';
import { apiRequest, API_ENDPOINTS, getApiBaseUrlSync } from '@/lib/api';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
}

export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
}

export interface StreamEvent {
  type: 'message' | 'tool_call' | 'tool_result' | 'complete' | 'error';
  data: any;
}

export function useChat() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    error: null,
    isConnected: false,
  });

  const [threadId] = useState(() => `chat-${Date.now()}`);
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
            thread_id: threadId,
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

        let assistantContent = '';

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
                      if (event.data.role === 'assistant') {
                        assistantContent = event.data.content;
                        updateMessage(assistantMessageId, {
                          content: assistantContent,
                          isStreaming: true,
                        });
                      }
                      break;

                    case 'tool_call':
                      // Add a visual indicator for tool usage
                      updateMessage(assistantMessageId, {
                        content: assistantContent + `\n\n🔧 Using tool: ${event.data.tool}...`,
                        isStreaming: true,
                      });
                      break;

                    case 'complete':
                      updateMessage(assistantMessageId, {
                        content: assistantContent,
                        isStreaming: false,
                      });
                      break;

                    case 'error':
                      setState(prev => ({ ...prev, error: event.data.error }));
                      updateMessage(assistantMessageId, {
                        content: assistantContent || 'Error occurred while processing your message.',
                        isStreaming: false,
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
            thread_id: threadId,
            stream: false,
          }),
        });

        addMessage({
          role: 'assistant',
          content: response.message.content,
        });
      }

      setState(prev => ({ ...prev, isConnected: true }));

    } catch (error: any) {
      if (error.name === 'AbortError') {
        // Request was cancelled, this is expected
        return;
      }

      console.error('Chat error:', error);
      setState(prev => ({
        ...prev,
        error: error.message || 'Failed to send message',
        isConnected: false,
      }));

      addMessage({
        role: 'assistant',
        content: 'Sorry, I encountered an error while processing your message. Please try again.',
      });
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [state.messages, threadId, addMessage, updateMessage]);

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
      isConnected: false,
    });
  }, [stopStreaming]);

  // Check agent health
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
    } catch (error: any) {
      setState(prev => ({
        ...prev,
        isConnected: false,
        error: error.message || 'Failed to check agent health',
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
    } catch (error: any) {
      console.error('Agent test failed:', error);
      throw error;
    }
  }, []);

  return {
    // State
    messages: state.messages,
    isLoading: state.isLoading,
    error: state.error,
    isConnected: state.isConnected,
    threadId,

    // Actions
    sendMessage,
    clearChat,
    stopStreaming,
    addMessage,
    updateMessage,

    // Utilities
    checkHealth,
    testAgent,
  };
} 