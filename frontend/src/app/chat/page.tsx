"use client";

import Navbar from "@/components/Navbar";
import { Send, AlertTriangle, CheckCircle, MessageSquare, Bot, User, Clock, Loader2, StopCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useState, useEffect, useRef } from "react";
import { useChat } from "@/hooks/useChat";

export default function ChatPage() {
  const [message, setMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const {
    messages,
    isLoading,
    error,
    isConnected,
    sendMessage,
    clearChat,
    stopStreaming,
    checkHealth,
  } = useChat();

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Check health on component mount
  useEffect(() => {
    checkHealth().catch(console.error);
  }, [checkHealth]);

  const handleSendMessage = async () => {
    if (message.trim() && !isLoading) {
      const messageToSend = message;
      setMessage("");
      await sendMessage(messageToSend, true); // Use streaming by default
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const renderMessage = (msg: any, index: number) => (
    <div
      key={msg.id}
      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} mb-4`}
    >
      <div
        className={`max-w-[80%] ${
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
            
            <div className="text-sm whitespace-pre-wrap break-words">
              {msg.content}
              {msg.isStreaming && !msg.content && (
                <span className="opacity-60">Thinking...</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <div className="flex h-[calc(100vh-4rem)]">
        {/* Sidebar */}
        <div className="w-80 border-r border-border bg-card">
          <div className="p-4 border-b border-border">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-foreground">Nova Chat</h2>
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
            
            <div className="text-sm text-muted-foreground mb-4">
              Chat with Nova, your AI assistant for managing tasks, people, and projects.
            </div>

            <div className="space-y-2">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={clearChat}
                className="w-full"
                disabled={isLoading}
              >
                Clear Chat
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

          {/* Quick Actions */}
          <div className="p-4">
            <h3 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wide">
              Quick Actions
            </h3>
            <div className="space-y-2">
              <Button 
                variant="ghost" 
                size="sm" 
                className="w-full justify-start text-left"
                onClick={() => setMessage("Create a new task for reviewing quarterly reports")}
                disabled={isLoading}
              >
                📝 Create a task
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                className="w-full justify-start text-left"
                onClick={() => setMessage("Show me all tasks that need my attention")}
                disabled={isLoading}
              >
                👀 Check pending tasks
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                className="w-full justify-start text-left"
                onClick={() => setMessage("Add a new team member to the system")}
                disabled={isLoading}
              >
                👥 Add team member
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                className="w-full justify-start text-left"
                onClick={() => setMessage("What can you help me with?")}
                disabled={isLoading}
              >
                ❓ Get help
              </Button>
            </div>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Chat Header */}
          <div className="p-4 border-b border-border bg-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center">
                  <Bot className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Nova Assistant</h2>
                  <p className="text-sm text-muted-foreground">
                    {isConnected ? "Ready to help with your tasks" : "Connecting..."}
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {error && (
                  <Badge variant="destructive" className="text-xs">
                    Error
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="w-16 h-16 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center mb-4">
                  <Bot className="h-8 w-8 text-white" />
                </div>
                <h3 className="text-lg font-semibold mb-2">Welcome to Nova Chat</h3>
                <p className="text-muted-foreground max-w-md mb-6">
                  I'm Nova, your AI assistant. I can help you manage tasks, organize your team, 
                  track projects, and much more. Try asking me to create a task or show you what I can do!
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
                    onClick={() => setMessage("Show me my current tasks")}
                    disabled={isLoading}
                  >
                    Show Tasks
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((msg, index) => renderMessage(msg, index))}
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
            <div className="flex space-x-3">
              <div className="flex-1">
                <Textarea
                  placeholder="Ask Nova anything... (Shift+Enter for new line, Enter to send)"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={handleKeyPress}
                  className="min-h-[60px] resize-none"
                  rows={2}
                  disabled={isLoading}
                />
              </div>
              <Button 
                onClick={handleSendMessage}
                disabled={!message.trim() || isLoading}
                className="self-end h-[60px] px-6"
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