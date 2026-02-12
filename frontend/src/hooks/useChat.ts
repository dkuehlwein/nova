import { useState, useCallback, useRef, useEffect } from 'react';
import { apiRequest, API_ENDPOINTS, getApiBaseUrlSync } from '@/lib/api';
import type {
  ToolCall,
  ChatMessage,
  PendingEscalation,
  ChatState,
  StreamMessageData,
  StreamToolData,
  StreamErrorData,
  StreamTraceData,
  StreamEvent,
} from '@/types/chat';

// Re-export for backward compatibility
export type { ToolCall, ChatMessage, PendingEscalation, ChatState, StreamEvent } from '@/types/chat';

// Helper to apply a buffered tool call or tool result to state
function applyToolEvent(
  prev: ChatState,
  messageId: string,
  event: { type: 'tool_call' | 'tool_result'; data: StreamToolData },
  contentUpdate?: string,
): ChatState {
  return {
    ...prev,
    messages: prev.messages.map(msg => {
      if (msg.id !== messageId) return msg;
      if (event.type === 'tool_call') {
        const toolData = event.data;
        return {
          ...msg,
          content: contentUpdate ?? msg.content,
          toolCalls: [
            ...(msg.toolCalls || []),
            {
              tool: toolData.tool,
              args: toolData.args || {},
              timestamp: toolData.timestamp || new Date().toISOString(),
              tool_call_id: toolData.tool_call_id,
            },
          ],
        };
      }
      // tool_result
      const resultData = event.data;
      return {
        ...msg,
        toolCalls: (msg.toolCalls || []).map(tc =>
          tc.tool_call_id === resultData.tool_call_id
            ? { ...tc, result: resultData.result }
            : tc
        ),
      };
    }),
  };
}

export function useChat() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    error: null,
    isConnected: true, // Updated by health check on mount
    pendingEscalation: null,
    phoenixUrl: null,
  });

  const [currentThreadId, setCurrentThreadId] = useState(() => `chat-${Date.now()}`);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Add a message to the chat
  const addMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: `msg-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
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

  // Load an existing chat conversation (now with escalation support)
  const loadChat = useCallback(async (chatId: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      // Set the thread ID first (especially important for task threads)
      setCurrentThreadId(chatId);
      
      // Use the task-data endpoint for ALL chats to get escalation support
      try {
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
              trace_id?: string;
              phoenix_url?: string;
            };
            tool_calls?: ToolCall[];
          }>;
          pending_escalation?: {
            question: string;
            instructions: string;
            tool_call_id?: string;
            type?: 'user_question' | 'tool_approval_request';
            tool_name?: string;
            tool_args?: Record<string, unknown>;
          };
        }>(API_ENDPOINTS.taskChatData(chatId));

        // Convert messages to ChatMessage format (with metadata!)
        // Keep messages separate to preserve the order of thinking -> tool call -> response
        const chatMessages: ChatMessage[] = taskChatData.messages.map((msg, index) => ({
          id: msg.id || `loaded-msg-${index}`,
          role: msg.sender === 'user' ? 'user' : (msg.sender === 'system' ? 'system' : 'assistant'),
          content: msg.content,
          timestamp: msg.created_at,
          isStreaming: false,
          metadata: msg.metadata || undefined,
          toolCalls: msg.tool_calls || undefined,
          phoenixUrl: msg.metadata?.phoenix_url,
        }));

        // Use escalation data from the endpoint (works for all chats now!)
        const pendingEscalation = taskChatData.pending_escalation || null;

        // Set the messages and escalation state
        setState(prev => ({
          ...prev,
          messages: chatMessages,
          isLoading: false,
          error: null,
          pendingEscalation,
        }));

        console.log(`Loaded chat ${chatId} with ${chatMessages.length} messages`);
        if (pendingEscalation) {
          console.log('Pending escalation detected:', pendingEscalation);
        }
        
      } catch {
        // For task threads that don't exist yet, this is normal
        // Clear messages and prepare for a new conversation
        console.log(`Chat thread ${chatId} not found or empty, starting new conversation`);
        setState(prev => ({
          ...prev,
          messages: [],
          isLoading: false,
          error: null,
          pendingEscalation: null,
        }));
      }
      
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load chat';
      console.error('Failed to load chat:', error);
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
        pendingEscalation: null,
      }));
    }
  }, []);

  // Send a message with streaming support
  const sendMessage = useCallback(async (content: string, useStreaming: boolean = true) => {
    if (!content.trim()) return;

    // Add user message
    addMessage({
      role: 'user',
      content: content.trim(),
    });

    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      if (useStreaming) {
        // Use streaming endpoint
        let assistantMessageId: string | null = null;
        let assistantContent = '';
        let assistantTimestamp: string | null = null;
        let bufferedToolCalls: Array<{type: 'tool_call' | 'tool_result', data: StreamToolData}> = [];
        let hasReceivedMessageContent = false;
        let toolCallIndex = 0; // Track tool call index for [[TOOL:N]] markers

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
            messages: [{
              role: 'user',
              content: content.trim(),
            }],
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
                    case 'start':
                      // Start event just indicates streaming has begun
                      // Trace info comes separately via trace_info event
                      break;

                    case 'trace_info':
                      // Handle trace info event - update current assistant message with Phoenix URL
                      const traceData = event.data as StreamTraceData;
                      if (traceData.phoenix_url) {
                        // Update conversation-level Phoenix URL
                        setState(prev => ({
                          ...prev,
                          phoenixUrl: traceData.phoenix_url,
                        }));
                        // Also update the current assistant message with the Phoenix URL
                        if (assistantMessageId) {
                          updateMessage(assistantMessageId, {
                            phoenixUrl: traceData.phoenix_url,
                          });
                        }
                      }
                      break;

                    case 'message':
                      const messageData = event.data as StreamMessageData;
                      if (messageData.role === 'assistant') {
                        // Handle assistant messages (memory context now comes via tool calls)
                        // Store timestamp from the first message
                        if (messageData.timestamp && !assistantTimestamp) {
                          assistantTimestamp = messageData.timestamp;
                        }
                        
                        // Create assistant message on first content
                        if (!assistantMessageId) {
                          assistantMessageId = addMessage({
                            role: 'assistant',
                            content: '',
                            isStreaming: true,
                          });
                        }
                        
                        // Defensive check: ensure messageData.content is a string
                        let contentToAdd = messageData.content;
                        if (typeof contentToAdd !== 'string') {
                          console.warn('Received non-string content in streaming:', contentToAdd);
                          contentToAdd = Array.isArray(contentToAdd) ? (contentToAdd as string[]).join('\n\n') : String(contentToAdd);
                        }
                        
                        // Accumulate content instead of overwriting
                        if (assistantContent && contentToAdd) {
                          // Add separator between responses for readability
                          assistantContent += '\n\n' + contentToAdd;
                        } else {
                          assistantContent = contentToAdd;
                        }
                        if (assistantMessageId) {
                          updateMessage(assistantMessageId, {
                            content: assistantContent,
                            isStreaming: true,
                            timestamp: assistantTimestamp || new Date().toISOString(),
                          });
                        }
                        
                        // Mark that we've received message content, now process any buffered tool calls
                        if (!hasReceivedMessageContent && contentToAdd && contentToAdd.trim()) {
                          hasReceivedMessageContent = true;
                          
                          // Process any buffered tool calls now that we have message content
                          for (const bufferedEvent of bufferedToolCalls) {
                            if (bufferedEvent.type === 'tool_call') {
                              assistantContent += `\n\n[[TOOL:${toolCallIndex}]]\n\n`;
                              toolCallIndex++;
                            }
                            setState(prev => applyToolEvent(
                              prev, assistantMessageId!, bufferedEvent, assistantContent
                            ));
                          }
                          bufferedToolCalls = [];
                        }
                      }
                      break;

                    case 'tool_call':
                      const toolData = event.data as StreamToolData;
                      
                      // If we haven't received message content yet, buffer this tool call
                      if (!hasReceivedMessageContent) {
                        bufferedToolCalls.push({type: 'tool_call', data: toolData});
                        // Create assistant message container if it doesn't exist (but don't show tool calls yet)
                        if (!assistantMessageId) {
                          assistantMessageId = addMessage({
                            role: 'assistant',
                            content: '',
                            isStreaming: true,
                          });
                          // Store timestamp from first tool call if not set
                          if (toolData.timestamp && !assistantTimestamp) {
                            assistantTimestamp = toolData.timestamp;
                          }
                        }
                        break;
                      }
                      
                      // If we've already received message content, process tool call immediately
                      if (!assistantMessageId) {
                        assistantMessageId = addMessage({
                          role: 'assistant',
                          content: '',
                          isStreaming: true,
                        });
                        if (toolData.timestamp && !assistantTimestamp) {
                          assistantTimestamp = toolData.timestamp;
                        }
                      }
                      
                      // Insert tool marker into content and add tool call
                      assistantContent += `\n\n[[TOOL:${toolCallIndex}]]\n\n`;
                      toolCallIndex++;
                      setState(prev => applyToolEvent(
                        prev, assistantMessageId!,
                        { type: 'tool_call', data: toolData },
                        assistantContent
                      ));
                      break;

                    case 'tool_result':
                      const resultData = event.data as StreamToolData;

                      // If we haven't received message content yet, buffer this tool result
                      if (!hasReceivedMessageContent) {
                        bufferedToolCalls.push({type: 'tool_result', data: resultData});
                        break;
                      }

                      // If we've already received message content, process tool result immediately
                      if (assistantMessageId) {
                        setState(prev => applyToolEvent(
                          prev, assistantMessageId!,
                          { type: 'tool_result', data: resultData }
                        ));
                      }
                      break;

                    case 'complete':
                      // Process any remaining buffered tool calls before completing
                      if (bufferedToolCalls.length > 0 && assistantMessageId) {
                        for (const bufferedEvent of bufferedToolCalls) {
                          setState(prev => applyToolEvent(prev, assistantMessageId!, bufferedEvent));
                        }
                        bufferedToolCalls = [];
                      }

                      if (assistantMessageId) {
                        updateMessage(assistantMessageId, {
                          content: assistantContent,
                          isStreaming: false,
                          timestamp: assistantTimestamp || new Date().toISOString(),
                        });
                      }
                      
                      // Check for pending escalations/tool approvals after stream completes
                      try {
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
                            tool_calls?: ToolCall[];
                          }>;
                          pending_escalation?: {
                            question: string;
                            instructions: string;
                            tool_call_id?: string;
                            type?: 'user_question' | 'tool_approval_request';
                            tool_name?: string;
                            tool_args?: Record<string, unknown>;
                          };
                        }>(API_ENDPOINTS.taskChatData(currentThreadId));

                        // Update pending escalation if found
                        if (taskChatData.pending_escalation) {
                          const escalation: PendingEscalation = {
                            question: taskChatData.pending_escalation.question,
                            instructions: taskChatData.pending_escalation.instructions,
                            tool_call_id: taskChatData.pending_escalation.tool_call_id,
                            type: taskChatData.pending_escalation.type,
                            tool_name: taskChatData.pending_escalation.tool_name,
                            tool_args: taskChatData.pending_escalation.tool_args,
                          };
                          setState(prev => ({ 
                            ...prev, 
                            pendingEscalation: escalation
                          }));
                          console.log('Tool approval detected after streaming:', escalation);
                        }
                      } catch (pollError) {
                        console.log('No escalation polling needed (normal for regular chats):', pollError);
                      }
                      break;

                    case 'error':
                      const errorData = event.data as StreamErrorData;
                      // Check if this is a tool-specific error
                      if ('tool_call_id' in errorData && errorData.tool_call_id) {
                        // Update specific tool call with error
                        setState(prev => ({
                          ...prev,
                          messages: prev.messages.map(msg => 
                            msg.id === assistantMessageId 
                              ? {
                                  ...msg,
                                  toolCalls: (msg.toolCalls || []).map(toolCall =>
                                    toolCall.tool_call_id === (errorData as unknown as {tool_call_id: string}).tool_call_id
                                      ? {
                                          ...toolCall,
                                          result: `Error: ${errorData.error}`,
                                        }
                                      : toolCall
                                  )
                                }
                              : msg
                          ),
                        }));
                      } else {
                        // General error
                        setState(prev => ({ ...prev, error: errorData.error }));
                        if (assistantMessageId) {
                          updateMessage(assistantMessageId, {
                            content: assistantContent || 'Error occurred while processing your message.',
                            isStreaming: false,
                            timestamp: assistantTimestamp || new Date().toISOString(),
                          });
                        }
                      }
                      break;

                    default:
                      // Silently ignore unknown event types (e.g. hook_processing_started)
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
        }>(API_ENDPOINTS.chatStream, {
          method: 'POST',
          body: JSON.stringify({
            messages: [{
              role: 'user',
              content: content.trim(),
            }],
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
  }, [currentThreadId, addMessage, updateMessage]);

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
      phoenixUrl: null,
    });
    // Generate a new thread ID for the new chat
    setCurrentThreadId(`chat-${Date.now()}`);
  }, [stopStreaming]);

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
            trace_id?: string;
            phoenix_url?: string;
          };
          tool_calls?: ToolCall[];
        }>;
        pending_escalation?: {
          question: string;
          instructions: string;
          tool_call_id?: string;
        };
      }>(API_ENDPOINTS.taskChatData(threadId));

      // Convert messages to ChatMessage format (with metadata!)
      // Keep messages separate to preserve the order of thinking -> tool call -> response
      const chatMessages: ChatMessage[] = taskChatData.messages.map((msg, index) => ({
        id: msg.id || `loaded-msg-${index}`,
        role: msg.sender === 'user' ? 'user' : (msg.sender === 'system' ? 'system' : 'assistant'),
        content: msg.content,
        timestamp: msg.created_at,
        isStreaming: false,
        metadata: msg.metadata || undefined,
        toolCalls: msg.tool_calls || undefined,
        phoenixUrl: msg.metadata?.phoenix_url,
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

  // Send escalation response for task chats
  const sendEscalationResponse = useCallback(async (taskId: string, response: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      await apiRequest(API_ENDPOINTS.taskChatMessage(taskId), {
        method: 'POST',
        body: JSON.stringify({
          content: response
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

  // Send tool approval response for any chat thread (not just tasks)  
  const sendToolApprovalResponse = useCallback(async (response: string) => {
    // Clear the escalation immediately for better UX
    setState(prev => ({ ...prev, pendingEscalation: null }));
    
    // Use the existing sendMessage function - it handles everything properly
    await sendMessage(response, true);
  }, [sendMessage]);

  // Respond to escalations (user questions and tool approvals)
  const respondToEscalation = useCallback(async (response: string) => {
    if (!state.pendingEscalation) {
      throw new Error('No pending escalation to respond to');
    }

    setState(prev => ({ ...prev, isLoading: true, pendingEscalation: null }));

    try {
      // Send response to backend
      await apiRequest(API_ENDPOINTS.escalationResponse(currentThreadId), {
        method: 'POST',
        body: JSON.stringify({ response }),
      });

      // The response has been sent, backend will resume processing
      // Wait a moment then check for new messages
      setTimeout(async () => {
        try {
          // Reload the task chat to get any new messages from the resumed processing
          if (currentThreadId.startsWith('core_agent_task_')) {
            const taskId = currentThreadId.replace('core_agent_task_', '');
            await loadTaskChat(taskId);
          }
        } catch (error) {
          console.warn('Failed to reload chat after escalation response:', error);
        } finally {
          setState(prev => ({ ...prev, isLoading: false }));
        }
      }, 1000);

    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to respond to escalation';
      setState(prev => ({ ...prev, error: errorMessage, isLoading: false }));
      throw error;
    }
  }, [state.pendingEscalation, currentThreadId, loadTaskChat]);

  // Mark the most recent pending tool call as approved in local message state
  const markToolCallApproved = useCallback((toolCallId?: string) => {
    if (!toolCallId) return;
    setState(prev => ({
      ...prev,
      messages: prev.messages.map(msg => ({
        ...msg,
        toolCalls: msg.toolCalls?.map(tc =>
          tc.tool_call_id === toolCallId ? { ...tc, approved: true } : tc
        ),
      })),
    }));
  }, []);

  // Tool approval specific responses
  const approveToolOnce = useCallback(async () => {
    if (!state.pendingEscalation || state.pendingEscalation.type !== 'tool_approval_request') {
      throw new Error('No pending tool approval to respond to');
    }

    const approvedToolCallId = state.pendingEscalation.tool_call_id;
    setState(prev => ({ ...prev, isLoading: true, pendingEscalation: null }));
    markToolCallApproved(approvedToolCallId);

    try {
      await apiRequest(API_ENDPOINTS.escalationResponse(currentThreadId), {
        method: 'POST',
        body: JSON.stringify({ type: 'approve', tool_call_id: approvedToolCallId }),
      });

      // Reload chat after approval
      setTimeout(async () => {
        try {
          if (currentThreadId.startsWith('core_agent_task_')) {
            const taskId = currentThreadId.replace('core_agent_task_', '');
            await loadTaskChat(taskId);
          } else {
            await loadChat(currentThreadId);
          }
        } catch (error) {
          console.warn('Failed to reload chat after tool approval:', error);
        } finally {
          setState(prev => ({ ...prev, isLoading: false }));
        }
      }, 1000);

    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to approve tool';
      setState(prev => ({ ...prev, error: errorMessage, isLoading: false }));
      throw error;
    }
  }, [state.pendingEscalation, currentThreadId, loadTaskChat, loadChat]);

  const alwaysAllowTool = useCallback(async () => {
    if (!state.pendingEscalation || state.pendingEscalation.type !== 'tool_approval_request') {
      throw new Error('No pending tool approval to respond to');
    }

    const approvedToolCallId = state.pendingEscalation.tool_call_id;
    setState(prev => ({ ...prev, isLoading: true, pendingEscalation: null }));
    markToolCallApproved(approvedToolCallId);

    try {
      await apiRequest(API_ENDPOINTS.escalationResponse(currentThreadId), {
        method: 'POST',
        body: JSON.stringify({ type: 'always_allow', tool_call_id: approvedToolCallId }),
      });

      // Reload chat after approval
      setTimeout(async () => {
        try {
          if (currentThreadId.startsWith('core_agent_task_')) {
            const taskId = currentThreadId.replace('core_agent_task_', '');
            await loadTaskChat(taskId);
          } else {
            await loadChat(currentThreadId);
          }
        } catch (error) {
          console.warn('Failed to reload chat after tool approval:', error);
        } finally {
          setState(prev => ({ ...prev, isLoading: false }));
        }
      }, 1000);

    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to approve tool';
      setState(prev => ({ ...prev, error: errorMessage, isLoading: false }));
      throw error;
    }
  }, [state.pendingEscalation, currentThreadId, loadTaskChat, loadChat]);

  const denyTool = useCallback(async () => {
    if (!state.pendingEscalation || state.pendingEscalation.type !== 'tool_approval_request') {
      throw new Error('No pending tool approval to respond to');
    }

    setState(prev => ({ ...prev, isLoading: true, pendingEscalation: null }));

    try {
      await apiRequest(API_ENDPOINTS.escalationResponse(currentThreadId), {
        method: 'POST',
        body: JSON.stringify({ type: 'deny' }),
      });

      // Reload chat after denial
      setTimeout(async () => {
        try {
          if (currentThreadId.startsWith('core_agent_task_')) {
            const taskId = currentThreadId.replace('core_agent_task_', '');
            await loadTaskChat(taskId);
          } else {
            await loadChat(currentThreadId);
          }
        } catch (error) {
          console.warn('Failed to reload chat after tool denial:', error);
        } finally {
          setState(prev => ({ ...prev, isLoading: false }));
        }
      }, 1000);

    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to deny tool';
      setState(prev => ({ ...prev, error: errorMessage, isLoading: false }));
      throw error;
    }
  }, [state.pendingEscalation, currentThreadId, loadTaskChat, loadChat]);

  // Health check: verify backend connectivity on mount and periodically
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const baseUrl = getApiBaseUrlSync();
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        const res = await fetch(`${baseUrl}${API_ENDPOINTS.health}`, {
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        setState(prev => prev.isConnected === res.ok ? prev : { ...prev, isConnected: res.ok });
      } catch {
        setState(prev => prev.isConnected === false ? prev : { ...prev, isConnected: false });
      }
    };

    checkHealth();
    const intervalId = setInterval(checkHealth, 30_000);

    return () => clearInterval(intervalId);
  }, []);

  // Cleanup: abort any in-flight streaming request on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  return {
    // State
    messages: state.messages,
    isLoading: state.isLoading,
    error: state.error,
    isConnected: state.isConnected,
    pendingEscalation: state.pendingEscalation,
    phoenixUrl: state.phoenixUrl,
    threadId: currentThreadId,

    // Actions
    sendMessage,
    clearChat,
    stopStreaming,
    addMessage,
    updateMessage,
    loadChat, // New function for loading existing chats
    loadTaskChat, // Load task chat with escalation support
    sendEscalationResponse, // Send response to escalation (for task chats)
    sendToolApprovalResponse, // Send tool approval response (for any chat thread)
    respondToEscalation, // General escalation response
    approveToolOnce, // Approve tool once
    alwaysAllowTool, // Always allow tool
    denyTool, // Deny tool

    // Utilities (manual trigger only)
    testAgent,
  };
} 