"use client";

import Navbar from "@/components/Navbar";
import { Send, AlertTriangle, MessageSquare, Bot, User, Loader2, StopCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useChat, ChatMessage } from "@/hooks/useChat";
import { apiRequest, API_ENDPOINTS } from "@/lib/api";
import { useSearchParams } from "next/navigation";
import { EscalationBox } from "@/components/EscalationBox";

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
  } = useChat();

  // Memoize the stable data to prevent unnecessary re-renders
  const memoizedPendingDecisions = useMemo(() => pendingDecisions, [pendingDecisions]);
  const memoizedChatHistory = useMemo(() => chatHistory, [chatHistory]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    const scrollToBottom = () => {
      if (messagesEndRef.current) {
        const chatContainer = messagesEndRef.current.closest('.chat-container');
        if (chatContainer) {
          const { scrollTop, scrollHeight, clientHeight } = chatContainer;
          // Only auto-scroll if user is already near the bottom (within 100px)
          const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
          
          if (isNearBottom) {
            messagesEndRef.current.scrollIntoView({ 
              behavior: "smooth",
              block: "end",
              inline: "nearest"
            });
          }
        }
      }
    };

    // Small delay to ensure DOM has updated
    const timeoutId = setTimeout(scrollToBottom, 50);
    return () => clearTimeout(timeoutId);
  }, [messages.length]); // Only trigger on message count change, not content changes

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

      const chatHistoryItems: ChatHistoryItem[] = chats.map(chat => ({
        id: chat.id,
        title: chat.title,
        last_message: chat.last_message || 'No messages yet',
        updated_at: chat.last_activity || chat.updated_at,
        needs_decision: chat.has_decision,
        message_count: chat.message_count,
        has_decision: chat.has_decision,
      }));

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

    // Handle URL parameters for task-specific chats
    const threadParam = searchParams.get('thread');
    const taskParam = searchParams.get('task');
    
    if (threadParam && taskParam) {
      // Load the task information
      const fetchTaskInfo = async () => {
        try {
          const task = await apiRequest<{ id: string; title: string }>(`/api/tasks/${taskParam}`);
          setTaskInfo({ id: task.id, title: task.title });
        } catch (error) {
          console.error('Failed to fetch task info:', error);
          setTaskInfo({ id: taskParam, title: 'Unknown Task' });
        }
      };
      
      fetchTaskInfo();
      
      // Load the task chat with escalation support
      loadTaskChat(taskParam);
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

  const formatTimestamp = useCallback((timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  }, []);

  const formatDate = useCallback((timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
    
    if (diffInHours < 24) {
      return formatTimestamp(timestamp);
    } else if (diffInHours < 48) {
      return 'Yesterday';
    } else {
      return date.toLocaleDateString();
    }
  }, [formatTimestamp]);

  const handleChatSelect = useCallback(async (chatItem: ChatHistoryItem) => {
    try {
      // Check if this is a task chat
      if (chatItem.task_id) {
        console.log(`Loading task chat: ${chatItem.task_id}`);
        setTaskInfo({ id: chatItem.task_id, title: chatItem.title });
        await loadTaskChat(chatItem.task_id);
      } else {
        console.log(`Loading regular chat: ${chatItem.id}`);
        setTaskInfo(null); // Clear task info for regular chats
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
  }, [loadChat, loadTaskChat]);

  const renderMessage = useCallback((msg: ChatMessage) => (
    <div
      key={msg.id}
      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} mb-4`}
    >
      <div
        className={`max-w-[80%] min-w-[200px] ${
          msg.role === "user"
            ? "bg-primary text-primary-foreground"
            : "bg-muted border"
        } rounded-lg p-4`}
      >
        <div className="flex items-start space-x-3">
          <div className="flex-shrink-0">
            {msg.role === "assistant" ? (
              <div className="w-8 h-8 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center">
                <Bot className="h-4 w-4 text-white" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
                <User className="h-4 w-4 text-white" />
              </div>
            )}
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2 mb-1">
              <span className="text-sm font-medium">
                {msg.role === "assistant" ? "Nova" : "You"}
              </span>
              <span className="text-xs opacity-60">
                {formatTimestamp(msg.timestamp)}
              </span>
              {msg.isStreaming && (
                <Loader2 className="h-3 w-3 animate-spin opacity-60" />
              )}
            </div>
            
            <div className="text-sm whitespace-pre-wrap break-words min-h-[1.25rem]">
              {msg.content || (msg.isStreaming ? (
                <span className="opacity-60">Thinking...</span>
              ) : '')}
            </div>
          </div>
        </div>
      </div>
    </div>
  ), [formatTimestamp]);

  return (
    <div className="chat-page bg-background">
      <Navbar />

      <div className="flex h-[calc(100vh-4rem)]">
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
                onClick={clearChat}
                className="w-full"
                disabled={isLoading}
              >
                New Chat
              </Button>
              
              {isLoading && (
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
          <div className="flex-1 overflow-y-auto chat-container">
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
                      {memoizedPendingDecisions.map((decision) => (
                        <div
                          key={decision.id}
                          onClick={() => handleChatSelect({
                            id: `core_agent_task_${decision.id}`,
                            title: decision.title,
                            last_message: decision.description,
                            updated_at: decision.updated_at,
                            needs_decision: true,
                            task_id: decision.id,
                          })}
                          className="p-3 rounded-lg border border-orange-200 bg-orange-50 hover:bg-orange-100 cursor-pointer transition-colors"
                        >
                          <div className="flex items-start space-x-2">
                            <AlertTriangle className="h-4 w-4 text-orange-500 mt-0.5 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-medium text-orange-900 truncate">
                                {decision.title}
                              </h4>
                              <p className="text-xs text-orange-700 line-clamp-2 mt-1">
                                {decision.description}
                              </p>
                              <p className="text-xs text-orange-600 mt-2">
                                {formatDate(decision.updated_at)}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Regular Chat History */}
                <div className="p-4">
                  <h3 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wide">
                    Recent Chats
                  </h3>
                  {memoizedChatHistory.filter(chat => !chat.needs_decision).length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No chat history yet
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {memoizedChatHistory
                        .filter(chat => !chat.needs_decision)
                        .map((chatItem) => (
                        <div
                          key={chatItem.id}
                          onClick={() => handleChatSelect(chatItem)}
                          className="p-3 rounded-lg border hover:bg-muted cursor-pointer transition-colors"
                        >
                          <div className="flex items-start space-x-2">
                            <MessageSquare className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-medium truncate">
                                {chatItem.title}
                              </h4>
                              <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                                {chatItem.last_message}
                              </p>
                              <p className="text-xs text-muted-foreground mt-2">
                                {formatDate(chatItem.updated_at)}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* Load More Button */}
                  {hasMoreChats && memoizedChatHistory.filter(chat => !chat.needs_decision).length > 0 && (
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
          <div className="flex-1 overflow-y-auto chat-container p-4">
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
                {pendingEscalation && taskInfo && (
                  <EscalationBox
                    question={pendingEscalation.question}
                    instructions={pendingEscalation.instructions}
                    onSubmit={async (response) => {
                      await sendEscalationResponse(taskInfo.id, response);
                    }}
                    isSubmitting={isLoading}
                  />
                )}
                
                {error && (
                  <div className="flex justify-center">
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
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

// Export with React.memo to prevent unnecessary re-renders
export default ChatPage; 