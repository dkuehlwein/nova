"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useChat } from "./useChat";
import { useUserSettings } from "./useNovaQueries";
import { apiRequest, API_ENDPOINTS } from "@/lib/api";

// Types
export interface PendingDecision {
  id: string;
  title: string;
  description: string;
  status: string;
  needs_decision: boolean;
  decision_type?: string;
  updated_at: string;
}

export interface ChatHistoryItem {
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

export interface TaskInfo {
  id: string;
  title: string;
}

/**
 * Hook for managing chat page state and logic
 * Composes useChat with page-level state management
 */
export function useChatPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // Compose with useChat hook
  const chat = useChat();
  const { data: userSettings } = useUserSettings();

  // Page-level state
  const [pendingDecisions, setPendingDecisions] = useState<PendingDecision[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([]);
  const [loadingDecisions, setLoadingDecisions] = useState(true);
  const [loadingMoreChats, setLoadingMoreChats] = useState(false);
  const [hasMoreChats, setHasMoreChats] = useState(true);
  const [chatOffset, setChatOffset] = useState(0);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null);
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);

  // Load chats function
  const loadChats = useCallback(async (
    offset: number,
    isInitial: boolean = false,
    fallbackDecisions?: PendingDecision[]
  ) => {
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

      const chatHistoryItems: ChatHistoryItem[] = chats.map(c => {
        const taskId = c.id.startsWith('core_agent_task_')
          ? c.id.replace('core_agent_task_', '')
          : undefined;

        return {
          id: c.id,
          title: c.title,
          last_message: c.last_message || 'No messages yet',
          updated_at: c.updated_at,
          last_activity: c.last_activity,
          needs_decision: c.has_decision,
          message_count: c.message_count,
          has_decision: c.has_decision,
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

      setHasMoreChats(chats.length === 5);
    } catch (error) {
      console.error('Failed to load chats:', error);
      if (isInitial && fallbackDecisions) {
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
  }, []);

  // Load more chats
  const loadMoreChats = useCallback(async () => {
    if (!loadingMoreChats && hasMoreChats) {
      await loadChats(chatOffset);
    }
  }, [chatOffset, loadingMoreChats, hasMoreChats, loadChats]);

  // Handle chat selection
  const handleChatSelect = useCallback(async (chatItem: ChatHistoryItem) => {
    try {
      if (chatItem.task_id) {
        const threadId = `core_agent_task_${chatItem.task_id}`;
        const newUrl = `/chat?thread=${threadId}&task=${chatItem.task_id}`;
        router.push(newUrl);
        setTaskInfo({ id: chatItem.task_id, title: chatItem.title });
        await chat.loadTaskChat(chatItem.task_id);
      } else {
        const newUrl = `/chat?thread=${chatItem.id}`;
        router.push(newUrl);
        setTaskInfo(null);
        await chat.loadChat(chatItem.id);
      }
    } catch (error) {
      console.error('Failed to load chat:', error);
    }
  }, [chat.loadTaskChat, chat.loadChat, router]);

  // Handle delete chat
  const handleDeleteChat = useCallback(async (chatItem: ChatHistoryItem, e: React.MouseEvent) => {
    e.stopPropagation();

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
        setChatHistory(prev => prev.filter(c => c.id !== chatItem.id));

        if (chatItem.task_id) {
          setPendingDecisions(prev => prev.filter(d => d.id !== chatItem.task_id));
        }

        const currentThread = searchParams.get('thread');
        if (currentThread === chatItem.id) {
          router.push('/chat');
          chat.clearChat();
          setTaskInfo(null);
        }
      }
    } catch (error) {
      console.error('Failed to delete chat:', error);
      alert('Failed to delete chat. Please try again.');
    } finally {
      setDeletingChatId(null);
    }
  }, [searchParams, router, chat.clearChat]);

  // Handle new chat
  const handleNewChat = useCallback(() => {
    router.push('/chat');
    setTaskInfo(null);
    chat.clearChat();
  }, [router, chat.clearChat]);

  // Sort chat history by last message timestamp (newest first)
  const sortedChatHistory = useMemo(() => {
    return chatHistory
      .slice()
      .sort((a, b) => {
        const timeA = new Date(a.last_activity || a.updated_at).getTime();
        const timeB = new Date(b.last_activity || b.updated_at).getTime();
        return timeB - timeA;
      });
  }, [chatHistory]);

  // Extract stable function references from chat to avoid infinite loops
  const { loadTaskChat, loadChat } = chat;

  // Initial data loading
  useEffect(() => {
    if (dataLoaded) return;

    const threadParam = searchParams.get('thread');
    const taskParam = searchParams.get('task');

    if (threadParam) {
      if (taskParam) {
        const fetchTaskInfo = async () => {
          try {
            const task = await apiRequest<{ id: string; title: string }>(`/api/tasks/${taskParam}`);
            setTaskInfo({ id: task.id, title: task.title });
          } catch {
            console.error(`Task ${taskParam} not found in database.`);
            setTaskInfo({ id: taskParam, title: `Orphaned Task ${taskParam.substring(0, 8)}` });
          }
        };
        fetchTaskInfo();
        loadTaskChat(taskParam);
      } else {
        loadChat(threadParam);
      }
    }

    const loadData = async () => {
      try {
        setLoadingDecisions(true);
        const decisions = await apiRequest<PendingDecision[]>(API_ENDPOINTS.pendingDecisions);
        setPendingDecisions(decisions);
        await loadChats(0, true, decisions);
        setDataLoaded(true);
      } catch (error) {
        console.error('Failed to load chat data:', error);
      } finally {
        setLoadingDecisions(false);
      }
    };

    loadData();
  }, [dataLoaded, searchParams, loadTaskChat, loadChat, loadChats]);

  return {
    // From useChat
    messages: chat.messages,
    isLoading: chat.isLoading,
    error: chat.error,
    isConnected: chat.isConnected,
    pendingEscalation: chat.pendingEscalation,
    phoenixUrl: chat.phoenixUrl,
    threadId: chat.threadId,
    sendMessage: chat.sendMessage,
    clearChat: chat.clearChat,
    stopStreaming: chat.stopStreaming,
    loadChat: chat.loadChat,
    loadTaskChat: chat.loadTaskChat,
    sendEscalationResponse: chat.sendEscalationResponse,
    sendToolApprovalResponse: chat.sendToolApprovalResponse,

    // User settings
    userSettings,

    // Page-level state
    pendingDecisions,
    chatHistory: sortedChatHistory,
    loadingDecisions,
    loadingMoreChats,
    hasMoreChats,
    taskInfo,
    deletingChatId,

    // Page-level actions
    loadMoreChats,
    handleChatSelect,
    handleDeleteChat,
    handleNewChat,
  };
}
