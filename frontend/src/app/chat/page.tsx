'use client';

import { Suspense, useState, useRef, useEffect, useCallback } from 'react';
import Navbar from '@/components/Navbar';
import { ChatSidebar, ChatHeader, ChatMessageList, ChatInput } from '@/components/chat';
import { useChatPage } from '@/hooks/useChatPage';
import { useChatMessage } from '@/hooks/useChatMessage';
import { ChatContextProvider } from '@/contexts/ChatContext';
import { useSearchParams } from 'next/navigation';

function ChatPage() {
  const searchParams = useSearchParams();

  // Page-level state and logic
  const {
    // From useChat
    messages,
    isLoading,
    error,
    isConnected,
    pendingEscalation,
    phoenixUrl,
    sendMessage,
    stopStreaming,
    sendEscalationResponse,
    sendToolApprovalResponse,
    approveToolOnce,
    alwaysAllowTool,
    denyTool,

    // User settings
    userSettings,

    // Page-level state
    pendingDecisions,
    chatHistory,
    loadingDecisions,
    loadingMoreChats,
    hasMoreChats,
    taskInfo,
    deletingChatId,
    loadingChatId,

    // Page-level actions
    loadMoreChats,
    handleChatSelect,
    handleDeleteChat,
    handleNewChat,
    generateChatTitle,
    renameChat,

    // Thread info
    threadId,
  } = useChatPage();

  // Message interaction state
  const { copiedMessageId, ratedMessages, handleCopyMessage, handleRateMessage } = useChatMessage();

  // Local UI state
  const [message, setMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Handle send message
  const handleSendMessage = useCallback(async () => {
    if (message.trim() && !isLoading) {
      const messageToSend = message;
      const wasFirstMessage = messages.length === 0;
      setMessage('');
      await sendMessage(messageToSend, true);

      // Generate title after first exchange
      if (wasFirstMessage && threadId) {
        generateChatTitle(threadId).catch(() => {});
      }
    }
  }, [message, isLoading, sendMessage, messages.length, threadId, generateChatTitle]);

  // Handle regenerate message
  const handleRegenerateMessage = useCallback(
    async (messageIndex: number) => {
      if (messageIndex === 0) return;
      const userMessage = messages[messageIndex - 1];
      if (userMessage && userMessage.role === 'user') {
        await sendMessage(userMessage.content, true);
      }
    },
    [messages, sendMessage],
  );

  // Escalation handlers
  const handleEscalationSubmit = useCallback(
    async (response: string) => {
      const taskId = taskInfo?.id || searchParams.get('task');
      if (taskId) {
        await sendEscalationResponse(taskId, response);
      } else {
        await sendToolApprovalResponse(response);
      }
    },
    [taskInfo, searchParams, sendEscalationResponse, sendToolApprovalResponse],
  );

  const handleEscalationApprove = useCallback(async () => {
    const taskId = taskInfo?.id || searchParams.get('task');
    if (taskId) {
      await sendEscalationResponse(taskId, 'approve');
    } else {
      await approveToolOnce();
    }
  }, [taskInfo, searchParams, sendEscalationResponse, approveToolOnce]);

  const handleEscalationDeny = useCallback(async () => {
    const taskId = taskInfo?.id || searchParams.get('task');
    if (taskId) {
      await sendEscalationResponse(taskId, 'deny');
    } else {
      await denyTool();
    }
  }, [taskInfo, searchParams, sendEscalationResponse, denyTool]);

  const handleEscalationAlwaysAllow = useCallback(async () => {
    const taskId = taskInfo?.id || searchParams.get('task');
    if (taskId) {
      await sendEscalationResponse(taskId, 'always_allow');
    } else {
      await alwaysAllowTool();
    }
  }, [taskInfo, searchParams, sendEscalationResponse, alwaysAllowTool]);

  // Auto-scroll effect
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  // Check if currently streaming
  const isStreaming = messages.length > 0 && messages[messages.length - 1]?.isStreaming;

  return (
    <div className="chat-page bg-background">
      <Navbar />

      <div className="flex h-[calc(100vh-var(--navbar-height))]">
        <ChatSidebar
          isConnected={isConnected}
          isLoading={isLoading}
          isStreaming={isStreaming || false}
          loadingDecisions={loadingDecisions}
          hasMoreChats={hasMoreChats}
          loadingMoreChats={loadingMoreChats}
          deletingChatId={deletingChatId}
          loadingChatId={loadingChatId}
          pendingDecisions={pendingDecisions}
          chatHistory={chatHistory}
          onNewChat={handleNewChat}
          onStopStreaming={stopStreaming}
          onChatSelect={handleChatSelect}
          onDeleteChat={handleDeleteChat}
          onLoadMore={loadMoreChats}
          onRenameChat={renameChat}
        />

        <div className="flex-1 flex flex-col min-w-0">
          <ChatHeader
            taskInfo={taskInfo}
            isConnected={isConnected}
            phoenixUrl={phoenixUrl}
            error={error}
            userSettings={userSettings}
          />

          <ChatContextProvider
            value={{
              copiedMessageId,
              ratedMessages,
              onCopyMessage: handleCopyMessage,
              onRegenerateMessage: handleRegenerateMessage,
              onRateMessage: handleRateMessage,
              onEscalationSubmit: handleEscalationSubmit,
              onEscalationApprove: handleEscalationApprove,
              onEscalationDeny: handleEscalationDeny,
              onEscalationAlwaysAllow: handleEscalationAlwaysAllow,
              onSetMessage: setMessage,
              isLoading,
            }}
          >
            <ChatMessageList
              ref={messagesEndRef}
              messages={messages}
              pendingEscalation={pendingEscalation}
              pendingDecisionsCount={pendingDecisions.length}
              error={error}
              isLoadingChat={!!loadingChatId}
            />
          </ChatContextProvider>

          <ChatInput
            message={message}
            isLoading={isLoading}
            isConnected={isConnected}
            onMessageChange={setMessage}
            onSend={handleSendMessage}
          />
        </div>
      </div>
    </div>
  );
}

export default function ChatPageWithSuspense() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background">
          <Navbar />
          <div className="flex items-center justify-center h-96">
            <div className="text-muted-foreground">Loading chat...</div>
          </div>
        </div>
      }
    >
      <ChatPage />
    </Suspense>
  );
}
