"use client";

import Navbar from "@/components/Navbar";
import { Send, AlertTriangle, MessageSquare, Bot, Loader2, StopCircle, Copy, RotateCcw, Check, ThumbsUp, ThumbsDown, Trash2, Link } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useState, useEffect, useRef, useMemo, useCallback, Suspense } from "react";
import { useChat, ChatMessage } from "@/hooks/useChat";
import { apiRequest, API_ENDPOINTS } from "@/lib/api";
import { useSearchParams, useRouter } from "next/navigation";
import { EscalationBox } from "@/components/EscalationBox";
import { MarkdownMessage } from "@/components/MarkdownMessage";
import { SystemMessage } from "@/components/SystemMessage";
import { useUserSettings } from "@/hooks/useNovaQueries";

interface PendingDecision {
  id: string;
  title: string;
  description: string;
  status: string;
  needs_decision: boolean;
  decision_type?: string;
  updated_at: string;
}

interface ChatHistoryItem {
  id: string;
  title: string;
  last_message: string;
  updated_at: string;
  last_activity?: string;
  needs_decision: boolean;
  task_id?: string;
  message_count?: number;
  has_decision?: boolean;
}

function ChatPage() {
  const [message, setMessage] = useState("");
  const [pendingDecisions, setPendingDecisions] = useState<PendingDecision[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([]);
  const [loadingDecisions, setLoadingDecisions] = useState(true);
  const [loadingMoreChats, setLoadingMoreChats] = useState(false);
  const [hasMoreChats, setHasMoreChats] = useState(true);
  const [chatOffset, setChatOffset] = useState(0);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [taskInfo, setTaskInfo] = useState<{ id: string; title: string } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const searchParams = useSearchParams();
  const router = useRouter();
  const {
    messages,
    isLoading,
    error,
    isConnected,
    pendingEscalation,
    sendMessage,
    clearChat,
    stopStreaming,
    loadChat,
    loadTaskChat,
    sendEscalationResponse,
    sendToolApprovalResponse,
  } = useChat();
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const chatHistoryContainerRef = useRef<HTMLDivElement>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [ratedMessages, setRatedMessages] = useState<Record<string, 'up' | 'down'>>({});
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);
  const { data: userSettings } = useUserSettings();

  // Memoize the stable data to prevent unnecessary re-renders
  const memoizedPendingDecisions = useMemo(() => pendingDecisions, [pendingDecisions]);
  const memoizedChatHistory = useMemo(() => chatHistory, [chatHistory]);

  // Simple autoscroll effect - scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  // Load more chats
  const loadMoreChats = useCallback(async () => {
    if (!loadingMoreChats && hasMoreChats) {
      await loadChats(chatOffset);
    }
  }, [chatOffset, loadingMoreChats, hasMoreChats]);

  const loadChats = async (offset: number, isInitial: boolean = false, fallbackDecisions?: PendingDecision[]) => {
    try {
      if (!isInitial) {
        setLoadingMoreChats(true);
      }

      const chats = await apiRequest<{
        id: string;
        title: string;
        created_at: string;
        updated_at: string;
        last_message?: string;
        last_activity?: string;
        has_decision: boolean;
        message_count: number;
      }[]>(`${API_ENDPOINTS.chats}?limit=5&offset=${offset}`);

      const chatHistoryItems: ChatHistoryItem[] = chats.map(chat => {
        // Extract task ID from thread ID pattern: core_agent_task_<task_id>
        const taskId = chat.id.startsWith('core_agent_task_') 
          ? chat.id.replace('core_agent_task_', '') 
          : undefined;
        
        return {
          id: chat.id,
          title: chat.title,
          last_message: chat.last_message || 'No messages yet',
          updated_at: chat.updated_at,
          last_activity: chat.last_activity,
          needs_decision: chat.has_decision,
          message_count: chat.message_count,
          has_decision: chat.has_decision,
          task_id: taskId,
        };
      });

      if (isInitial) {
        setChatHistory(chatHistoryItems);
        setChatOffset(chats.length);
      } else {
        setChatHistory(prev => [...prev, ...chatHistoryItems]);
        setChatOffset(prev => prev + chats.length);
      }

      // If we got fewer than 5 chats, there are no more
      setHasMoreChats(chats.length === 5);

    } catch (error) {
      console.error('Failed to load chats:', error);
      if (isInitial && fallbackDecisions) {
        // Fallback for initial load: Create chat history from pending decisions
        const fallbackChatHistory: ChatHistoryItem[] = fallbackDecisions.map(decision => ({
          id: `chat-${decision.id}`,
          title: decision.title,
          last_message: `Decision needed: ${decision.description.substring(0, 50)}...`,
          updated_at: decision.updated_at,
          last_activity: undefined,
          needs_decision: true,
          task_id: decision.id,
        }));
        setChatHistory(fallbackChatHistory);
      }
    } finally {
      if (!isInitial) {
        setLoadingMoreChats(false);
      }
    }
  };

  // Load initial data
  useEffect(() => {
    if (dataLoaded) return; // Prevent double loading

    // Handle URL parameters for any chat conversation
    const threadParam = searchParams.get('thread');
    const taskParam = searchParams.get('task');
    
    if (threadParam) {
      // If task param is also provided, load task context for bonus info
      if (taskParam) {
        const fetchTaskInfo = async () => {
          try {
            const task = await apiRequest<{ id: string; title: string }>(`/api/tasks/${taskParam}`);
            setTaskInfo({ id: task.id, title: task.title });
          } catch {
            // Task doesn't exist in database - this indicates orphaned LangGraph data
            console.error(`Task ${taskParam} not found in database. This chat thread is orphaned and should be cleaned up.`);
            setTaskInfo({ id: taskParam, title: `Orphaned Task ${taskParam.substring(0, 8)}` });
          }
        };
        fetchTaskInfo();
        
        // Load with escalation support for task chats
        loadTaskChat(taskParam);
      } else {
        // Load any conversation by thread ID - now with universal escalation support!
        loadChat(threadParam);
      }
    }

    const loadData = async () => {
      try {
        setLoadingDecisions(true);
        
        // Fetch pending decisions (tasks that need user input)
        const decisions = await apiRequest<PendingDecision[]>(API_ENDPOINTS.pendingDecisions);
        setPendingDecisions(decisions);

        // Fetch initial chat history from backend (first 5 chats)
        await loadChats(0, true, decisions);
        
        setDataLoaded(true); // Mark as loaded
      } catch (error) {
        console.error('Failed to load chat data:', error);
      } finally {
        setLoadingDecisions(false);
      }
    };

    loadData();
  }, [dataLoaded, searchParams, loadChat, loadTaskChat]); // Depend on dataLoaded flag

  const handleSendMessage = useCallback(async () => {
    if (message.trim() && !isLoading) {
      const messageToSend = message;
      setMessage("");
      await sendMessage(messageToSend, true); // Use streaming by default
    }
  }, [message, isLoading, sendMessage]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }, [handleSendMessage]);

  // Format timestamp in German local time
  const formatTimestamp = useCallback((timestamp: string) => {
    if (!timestamp) return '';
    try {
      return new Date(timestamp).toLocaleString('de-DE', { 
        timeZone: 'Europe/Berlin', 
        hour: '2-digit', 
        minute: '2-digit', 
        day: '2-digit', 
        month: '2-digit', 
        year: '2-digit' 
      });
    } catch {
      return timestamp;
    }
  }, []);

  const formatDate = useCallback((timestamp: string) => {
    if (!timestamp) return '';
    try {
      return new Date(timestamp).toLocaleDateString('de-DE', { 
        timeZone: 'Europe/Berlin',
        weekday: 'short',
        day: '2-digit', 
        month: '2-digit', 
        year: '2-digit' 
      });
    } catch {
      return timestamp;
    }
  }, []);

  // Sort chat history by last message timestamp (newest first)
  const sortedChatHistory = useMemo(() => {
    return memoizedChatHistory
      .slice()
      .sort((a, b) => {
        // Use last_activity if available, otherwise fall back to updated_at
        const timeA = new Date(a.last_activity || a.updated_at).getTime();
        const timeB = new Date(b.last_activity || b.updated_at).getTime();
        return timeB - timeA; // Newest first
      });
  }, [memoizedChatHistory]);

  const handleChatSelect = useCallback(async (chatItem: ChatHistoryItem) => {
    try {
      if (chatItem.task_id) {
        // Task-specific chat - update URL with both thread and task params
        const threadId = `core_agent_task_${chatItem.task_id}`;
        const newUrl = `/chat?thread=${threadId}&task=${chatItem.task_id}`;
        router.push(newUrl);
        
        setTaskInfo({ id: chatItem.task_id, title: chatItem.title });
        await loadTaskChat(chatItem.task_id);
      } else {
        // Regular chat - update URL with thread param only
        const newUrl = `/chat?thread=${chatItem.id}`;
        router.push(newUrl);
        
        setTaskInfo(null);
        await loadChat(chatItem.id);
      }
    } catch (error) {
      console.error('Failed to load chat:', error);
      // Fallback: set a message to continue the conversation
      if (chatItem.task_id) {
        setMessage(`Show me details about task: ${chatItem.title}`);
      } else {
        setMessage(`Continue our conversation: ${chatItem.title}`);
      }
    }
  }, [loadChat, loadTaskChat, router]);

  // Handle copy message
  const handleCopyMessage = useCallback(async (messageId: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (err) {
      console.error('Failed to copy message:', err);
    }
  }, []);

  // Handle regenerate message
  const handleRegenerateMessage = useCallback(async (messageIndex: number) => {
    if (messageIndex === 0) return; // Can't regenerate if no previous user message
    
    // Find the user message that prompted this response
    const userMessage = messages[messageIndex - 1];
    if (userMessage && userMessage.role === 'user') {
      await sendMessage(userMessage.content, true);
    }
  }, [messages, sendMessage]);

  // Handle rating messages
  const handleRateMessage = useCallback((messageId: string, rating: 'up' | 'down') => {
    setRatedMessages(prev => {
      const newRatings = { ...prev };
      if (prev[messageId] === rating) {
        delete newRatings[messageId];
      } else {
        newRatings[messageId] = rating;
      }
      return newRatings;
    });
    // TODO: Send rating to backend for analytics
  }, []);

  // Handle delete chat
  const handleDeleteChat = useCallback(async (chatItem: ChatHistoryItem, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent selecting the chat when clicking delete

    // Show confirmation dialog with appropriate warning
    const isTaskChat = !!chatItem.task_id;
    const confirmMessage = isTaskChat
      ? `This chat is connected to a task. Deleting it will also delete the task "${chatItem.title}" and all its data.\n\nAre you sure you want to continue?`
      : `Delete this conversation "${chatItem.title}"?\n\nThis action cannot be undone.`;

    if (!window.confirm(confirmMessage)) {
      return;
    }

    setDeletingChatId(chatItem.id);

    try {
      const response = await apiRequest<{
        success: boolean;
        deleted_chat: string;
        deleted_task: string | null;
        message: string;
      }>(API_ENDPOINTS.deleteChat(chatItem.id), {
        method: 'DELETE',
      });

      if (response.success) {
        // Remove from chat history
        setChatHistory(prev => prev.filter(c => c.id !== chatItem.id));

        // If this was a task chat, also remove from pending decisions
        if (chatItem.task_id) {
          setPendingDecisions(prev => prev.filter(d => d.id !== chatItem.task_id));
        }

        // If we just deleted the currently active chat, clear it
        const currentThread = searchParams.get('thread');
        if (currentThread === chatItem.id) {
          router.push('/chat');
          clearChat();
          setTaskInfo(null);
        }
      }
    } catch (error) {
      console.error('Failed to delete chat:', error);
      alert('Failed to delete chat. Please try again.');
    } finally {
      setDeletingChatId(null);
    }
  }, [searchParams, router, clearChat]);

  const renderMessage = useCallback((msg: ChatMessage) => {
    // Handle system messages separately
    if (msg.role === "system") {
      return (
        <SystemMessage
          key={msg.id}
          content={msg.content}
          collapsibleContent={msg.metadata?.collapsible_content}
          isCollapsible={msg.metadata?.is_collapsible || false}
          timestamp={msg.timestamp}
          messageType={msg.metadata?.type || "system_prompt"}
          title={msg.metadata?.title}
        />
      );
    }

    // Handle tool approval decision messages with special styling
    if (msg.role === "user" && msg.metadata?.type === "tool_approval_decision") {
      return (
        <div key={msg.id} className="flex justify-center mb-4">
          <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 text-blue-800 dark:text-blue-200 rounded-lg px-4 py-2 text-sm font-medium shadow-sm">
            {msg.content}
          </div>
        </div>
      );
    }

    // Handle messages with special metadata (like task context) using SystemMessage component
    if ((msg.role === "assistant" || msg.role === "user") && msg.metadata?.is_collapsible) {
      // For task_context messages, use clean metadata approach
      // Title from metadata, content goes in collapsible section
      return (
        <SystemMessage
          key={msg.id}
          content="" // Empty - title from metadata shows the header
          collapsibleContent={msg.content} // Clean content without headers
          isCollapsible={msg.metadata?.is_collapsible || false}
          timestamp={msg.timestamp}
          messageType={msg.metadata?.type || "task_context"}
          title={msg.metadata?.title}
        />
      );
    }

    // Handle regular user/assistant messages
    const messageIndex = messages.findIndex(m => m.id === msg.id);
    
    return (
      <div
        key={msg.id}
        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} mb-6 group`}
      >
        <div
          className={`max-w-[85%] min-w-[250px] ${
            msg.role === "user"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "bg-card border shadow-sm"
          } rounded-xl p-4 pb-8 relative transition-shadow hover:shadow-md`}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-semibold">
                {msg.role === "assistant" ? "Nova" : "You"}
              </span>
              {msg.isStreaming && (
                <Loader2 className="h-3 w-3 animate-spin opacity-60" />
              )}
            </div>
            <span className={`text-xs ${msg.role === 'user' ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
              {formatTimestamp(msg.timestamp)}
            </span>
          </div>
          
          <div className="text-sm break-words min-h-[1.25rem]">
            {msg.content || msg.toolCalls ? (
              <MarkdownMessage content={msg.content || ''} toolCalls={msg.toolCalls} />
            ) : (msg.isStreaming ? (
              <div className="flex items-center space-x-2 opacity-60">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                  <div className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                  <div className="w-2 h-2 bg-current rounded-full animate-bounce"></div>
                </div>
                <span>Nova is thinking...</span>
              </div>
            ) : '')}
          </div>
          
          {/* Message Actions - Positioned in the bottom padding area */}
          {!msg.isStreaming && msg.content && (
            <div className={`absolute bottom-2 right-2 flex items-center space-x-1 backdrop-blur-sm border rounded-lg px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity shadow-sm ${
              msg.role === "user"
                ? "bg-primary-foreground/20 border-primary-foreground/30"
                : "bg-background/90 border-border/50"
            }`}>
              <Button
                variant="ghost"
                size="sm"
                className={`h-6 px-1.5 text-xs ${
                  msg.role === "user"
                    ? "hover:bg-primary-foreground/20 text-primary-foreground"
                    : "hover:bg-muted"
                }`}
                onClick={() => handleCopyMessage(msg.id, msg.content)}
                disabled={copiedMessageId === msg.id}
              >
                {copiedMessageId === msg.id ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>

              {msg.role === "assistant" && messageIndex > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-1.5 text-xs hover:bg-muted"
                  onClick={() => handleRegenerateMessage(messageIndex)}
                  disabled={isLoading}
                >
                  <RotateCcw className="h-3 w-3" />
                </Button>
              )}

              {/* Rating buttons for assistant messages */}
              {msg.role === "assistant" && (
                <>
                  <div className="w-px h-4 bg-border mx-1" />
                  <Button
                    variant="ghost"
                    size="sm"
                    className={`h-6 px-1.5 text-xs hover:bg-muted ${
                      ratedMessages[msg.id] === 'up' ? 'text-green-600' : ''
                    }`}
                    onClick={() => handleRateMessage(msg.id, 'up')}
                  >
                    <ThumbsUp className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className={`h-6 px-1.5 text-xs hover:bg-muted ${
                      ratedMessages[msg.id] === 'down' ? 'text-red-600' : ''
                    }`}
                    onClick={() => handleRateMessage(msg.id, 'down')}
                  >
                    <ThumbsDown className="h-3 w-3" />
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }, [formatTimestamp, handleCopyMessage, handleRegenerateMessage, handleRateMessage, messages, copiedMessageId, isLoading, ratedMessages]);

  return (
    <div className="chat-page bg-background">
      <Navbar />

      <div className="flex h-[calc(100vh-var(--navbar-height))]">
        {/* Sidebar - Chat History */}
        <div className="chat-sidebar w-80 border-r border-border bg-card flex flex-col">
          <div className="p-4 border-b border-border">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-foreground">Chat History</h2>
              <div className="flex items-center space-x-2">
                {isConnected ? (
                  <Badge variant="default" className="text-xs bg-green-500">
                    Connected
                  </Badge>
                ) : (
                  <Badge variant="destructive" className="text-xs">
                    Disconnected
                  </Badge>
                )}
              </div>
            </div>
            
            <div className="space-y-2">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => {
                  // Clear the URL parameters and start fresh
                  router.push('/chat');
                  setTaskInfo(null);
                  clearChat();
                }}
                className="w-full"
                disabled={isLoading}
              >
                New Chat
              </Button>
              
              {isLoading && messages.length > 0 && messages[messages.length - 1]?.isStreaming && (
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={stopStreaming}
                  className="w-full"
                >
                  <StopCircle className="h-4 w-4 mr-2" />
                  Stop
                </Button>
              )}
            </div>
          </div>

          {/* Chat History List */}
          <div className="flex-1 overflow-y-auto chat-container" ref={chatHistoryContainerRef}>
            {loadingDecisions ? (
              <div className="p-4 text-center">
                <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Loading chats...</p>
              </div>
            ) : (
              <>
                {/* Pending Decisions Section */}
                {memoizedPendingDecisions.length > 0 && (
                  <div className="p-4">
                    <h3 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wide flex items-center">
                      <AlertTriangle className="h-4 w-4 mr-1 text-orange-500" />
                      Needs Decision ({memoizedPendingDecisions.length})
                    </h3>
                    <div className="space-y-2">
                      {memoizedPendingDecisions.map((decision) => {
                        const chatItem: ChatHistoryItem = {
                          id: `core_agent_task_${decision.id}`,
                          title: decision.title,
                          last_message: decision.description,
                          updated_at: decision.updated_at,
                          needs_decision: true,
                          task_id: decision.id,
                        };
                        return (
                          <div
                            key={decision.id}
                            onClick={() => handleChatSelect(chatItem)}
                            className="p-3 rounded-lg border border-orange-200 dark:border-orange-700 bg-orange-50 dark:bg-orange-900/30 hover:bg-orange-100 dark:hover:bg-orange-900/50 cursor-pointer transition-colors group/decision"
                          >
                            <div className="flex items-start space-x-2">
                              <AlertTriangle className="h-4 w-4 text-orange-500 dark:text-orange-400 mt-0.5 flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <h4 className="text-sm font-medium text-orange-900 dark:text-orange-100 truncate">
                                  {decision.title}
                                </h4>
                                <div className="text-xs text-orange-700 dark:text-orange-300 line-clamp-2 mt-1">
                                  <MarkdownMessage content={decision.description} disableLinks />
                                </div>
                                <p className="text-xs text-orange-600 dark:text-orange-400 mt-2">
                                  {formatDate(decision.updated_at)}
                                </p>
                              </div>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 w-6 p-0 opacity-0 group-hover/decision:opacity-100 transition-opacity text-orange-600 dark:text-orange-400 hover:text-destructive flex-shrink-0"
                                onClick={(e) => handleDeleteChat(chatItem, e)}
                                disabled={deletingChatId === chatItem.id}
                                title="Delete chat and task"
                              >
                                {deletingChatId === chatItem.id ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <Trash2 className="h-3 w-3" />
                                )}
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Regular Chat History */}
                <div className="p-4">
                  <h3 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wide">
                    Recent Chats
                  </h3>
                  {(() => {
                    const visibleChats = sortedChatHistory.filter(chat => !chat.needs_decision);
                    if (visibleChats.length === 0) {
                      return (
                        <p className="text-sm text-muted-foreground text-center py-4">
                          No chat history yet
                        </p>
                      );
                    }
                    return (
                      <div className="space-y-2">
                        {visibleChats.map((chatItem) => (
                          <div
                            key={chatItem.id}
                            onClick={() => handleChatSelect(chatItem)}
                            className="p-3 rounded-lg border hover:bg-muted cursor-pointer transition-colors group/chat relative"
                          >
                            <div className="flex items-start space-x-2">
                              <MessageSquare className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1">
                                  <h4 className="text-sm font-medium truncate flex-1">
                                    <MarkdownMessage content={chatItem.title} disableLinks />
                                  </h4>
                                  {chatItem.task_id && (
                                    <span title="Connected to task">
                                      <Link className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                                    </span>
                                  )}
                                </div>
                                <div className="text-xs text-muted-foreground line-clamp-2 mt-1">
                                  <MarkdownMessage content={chatItem.last_message} disableLinks />
                                </div>
                                <p className="text-xs text-muted-foreground mt-2">
                                  {formatDate(chatItem.last_activity || chatItem.updated_at)}
                                </p>
                              </div>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 w-6 p-0 opacity-0 group-hover/chat:opacity-100 transition-opacity text-muted-foreground hover:text-destructive flex-shrink-0"
                                onClick={(e) => handleDeleteChat(chatItem, e)}
                                disabled={deletingChatId === chatItem.id}
                                title={chatItem.task_id ? "Delete chat and task" : "Delete chat"}
                              >
                                {deletingChatId === chatItem.id ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <Trash2 className="h-3 w-3" />
                                )}
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                  
                  {/* Load More Button */}
                  {hasMoreChats && sortedChatHistory.filter(chat => !chat.needs_decision).length > 0 && (
                    <div className="mt-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={loadMoreChats}
                        disabled={loadingMoreChats}
                        className="w-full"
                      >
                        {loadingMoreChats ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                            Loading...
                          </>
                        ) : (
                          'Load More Chats'
                        )}
                      </Button>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Chat Header */}
          <div className="p-4 border-b border-border bg-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center">
                  <Bot className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">
                    {taskInfo ? `Nova - Task: ${taskInfo.title}` : "Nova Assistant"}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {taskInfo 
                      ? "Chatting about this specific task" 
                      : isConnected ? "Ready to help with your tasks" : "Connecting..."
                    }
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {userSettings && (
                  <Badge variant="outline" className="text-xs">
                    {userSettings.chat_llm_model}
                  </Badge>
                )}
                {taskInfo && (
                  <Badge variant="secondary" className="text-xs">
                    Task Chat
                  </Badge>
                )}
                {error && (
                  <Badge variant="destructive" className="text-xs">
                    Error
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto chat-container p-4" ref={messagesContainerRef}>
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="w-16 h-16 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center mb-4">
                  <Bot className="h-8 w-8 text-white" />
                </div>
                <h3 className="text-lg font-semibold mb-2">Welcome to Nova Chat</h3>
                <p className="text-muted-foreground max-w-md mb-6">
                  I&apos;m Nova, your AI assistant. I can help you manage tasks, organize your team, 
                  track projects, and much more. 
                  {memoizedPendingDecisions.length > 0 && (
                    <span className="block mt-2 text-orange-600 font-medium">
                      You have {memoizedPendingDecisions.length} task(s) that need your decision!
                    </span>
                  )}
                </p>
                <div className="grid grid-cols-2 gap-3 max-w-lg">
                  <Button 
                    variant="outline" 
                    onClick={() => setMessage("What can you help me with?")}
                    disabled={isLoading}
                  >
                    Get Started
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => setMessage("Show me tasks that need my attention")}
                    disabled={isLoading}
                  >
                    Check Tasks
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((msg) => renderMessage(msg))}
                
                {/* Escalation Box for pending decisions */}
                {pendingEscalation && (
                  <EscalationBox
                    question={pendingEscalation.question}
                    instructions={pendingEscalation.instructions}
                    escalationType={pendingEscalation.type || 'user_question'}
                    toolName={pendingEscalation.tool_name}
                    toolArgs={pendingEscalation.tool_args}
                    onSubmit={async (response) => {
                      // Use task ID from URL params or taskInfo for task chats
                      const taskId = taskInfo?.id || searchParams.get('task');
                      if (taskId) {
                        await sendEscalationResponse(taskId, response);
                      } else {
                        // For regular chat threads, use the tool approval handler
                        await sendToolApprovalResponse(response);
                      }
                    }}
                    onApprove={async () => {
                      const taskId = taskInfo?.id || searchParams.get('task');
                      if (taskId) {
                        await sendEscalationResponse(taskId, "approve");
                      } else {
                        // For regular chat threads, use the tool approval handler
                        await sendToolApprovalResponse("approve");
                      }
                    }}
                    onDeny={async () => {
                      const taskId = taskInfo?.id || searchParams.get('task');
                      if (taskId) {
                        await sendEscalationResponse(taskId, "deny");
                      } else {
                        // For regular chat threads, use the tool approval handler
                        await sendToolApprovalResponse("deny");
                      }
                    }}
                    onAlwaysAllow={async () => {
                      const taskId = taskInfo?.id || searchParams.get('task');
                      if (taskId) {
                        await sendEscalationResponse(taskId, "always_allow");
                      } else {
                        // For regular chat threads, use the tool approval handler
                        await sendToolApprovalResponse("always_allow");
                      }
                    }}
                    isSubmitting={isLoading}
                  />
                )}
                
                {error && (
                  <div className="flex justify-center">
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-2 rounded-lg text-sm">
                      <AlertTriangle className="h-4 w-4 inline mr-2" />
                      {error}
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Message Input */}
          <div className="p-4 border-t border-border bg-card">
            <div className="flex space-x-3 items-end">
              <div className="flex-1">
                <Textarea
                  placeholder="Ask Nova anything... (Shift+Enter for new line, Enter to send)"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={handleKeyPress}
                  className="min-h-[60px] max-h-[120px] resize-none transition-none"
                  rows={2}
                  disabled={isLoading}
                />
              </div>
              <Button 
                onClick={handleSendMessage}
                disabled={!message.trim() || isLoading}
                className="h-[60px] px-6 flex-shrink-0"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
            
            {!isConnected && (
              <div className="mt-2 text-sm text-orange-600 flex items-center">
                <AlertTriangle className="h-4 w-4 mr-1" />
                Connection issues detected. Some features may not work properly.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ChatPageWithSuspense() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <div className="text-muted-foreground">Loading chat...</div>
        </div>
      </div>
    }>
      <ChatPage />
    </Suspense>
  );
} 