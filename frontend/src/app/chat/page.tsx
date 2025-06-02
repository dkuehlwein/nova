"use client";

import Navbar from "@/components/Navbar";
import { Send, AlertCircle, CheckCircle, MessageSquare, Bot, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useState } from "react";

export default function ChatPage() {
  const [message, setMessage] = useState("");

  // Mock conversation history
  const conversations = [
    {
      id: "chat-123",
      title: "Email draft for John Smith",
      lastMessage: "Please review the draft before sending",
      lastActivity: "2 hours ago",
      hasDecision: true,
      isActive: true
    },
    {
      id: "chat-124",
      title: "Task assignment strategy",
      lastMessage: "I've identified 3 team members who could...",
      lastActivity: "4 hours ago", 
      hasDecision: true,
      isActive: false
    },
    {
      id: "chat-125",
      title: "Quarterly report review",
      lastMessage: "Task created and moved to TODO",
      lastActivity: "1 day ago",
      hasDecision: false,
      isActive: false
    },
    {
      id: "chat-126",
      title: "Client presentation updates",
      lastMessage: "Presentation has been updated successfully",
      lastActivity: "2 days ago",
      hasDecision: false,
      isActive: false
    }
  ];

  // Mock current conversation messages
  const currentMessages = [
    {
      id: 1,
      sender: "user",
      content: "I need to respond to John Smith's email about the project timeline",
      timestamp: "3 hours ago"
    },
    {
      id: 2,
      sender: "assistant",
      content: "I've reviewed John's email and can help you draft a response. Based on the project timeline you shared with me last week, I can see there might be some delays due to the resource constraints. Would you like me to draft a response that acknowledges the delay and proposes a revised timeline?",
      timestamp: "3 hours ago"
    },
    {
      id: 3,
      sender: "user", 
      content: "Yes, please draft something professional but honest about the situation",
      timestamp: "2 hours ago"
    },
    {
      id: 4,
      sender: "assistant",
      content: `I've drafted the following response for your review:

---

Hi John,

Thank you for your email regarding the project timeline. I wanted to provide you with an honest update on our progress.

Due to some resource allocation challenges we've encountered, we're looking at a revised timeline that extends our original delivery date by approximately 2 weeks. I understand this may impact your planning, and I want to be transparent about this as early as possible.

Here's what we're doing to minimize the delay:
- Reallocating senior developers to critical path items
- Implementing daily stand-ups to track progress more closely
- Identifying opportunities to parallelize certain tasks

I'm confident we can deliver a high-quality solution with this adjusted timeline. Could we schedule a brief call this week to discuss this in more detail and address any concerns you might have?

Best regards,
[Your name]

---

Would you like me to send this email, or would you prefer to make any changes first?`,
      timestamp: "2 hours ago",
      needsDecision: true,
      decisionType: "email_approval"
    }
  ];

  const handleSendMessage = () => {
    if (message.trim()) {
      // Handle sending message logic here
      setMessage("");
    }
  };

  const activeConversation = conversations.find(c => c.isActive);

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <div className="flex h-[calc(100vh-4rem)]">
        {/* Sidebar - Conversation History */}
        <div className="w-80 border-r border-border bg-card flex flex-col">
          <div className="p-4 border-b border-border">
            <h2 className="text-lg font-semibold text-foreground mb-2">Conversations</h2>
            <Button className="w-full" size="sm">
              <MessageSquare className="h-4 w-4 mr-2" />
              New Conversation
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto">
            <div className="p-2">
              {/* Pending Decisions Section */}
              <div className="mb-4">
                <h3 className="text-sm font-medium text-muted-foreground mb-2 px-2">
                  Pending Decisions ({conversations.filter(c => c.hasDecision).length})
                </h3>
                {conversations
                  .filter(c => c.hasDecision)
                  .map((conversation) => (
                    <div
                      key={conversation.id}
                      className={`p-3 rounded-lg mb-2 cursor-pointer transition-colors ${
                        conversation.isActive 
                          ? "bg-red-500/10 border border-red-500/20" 
                          : "bg-red-500/5 border border-red-500/10 hover:bg-red-500/10"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
                            <h4 className="text-sm font-medium text-foreground truncate">
                              {conversation.title}
                            </h4>
                          </div>
                          <p className="text-xs text-muted-foreground truncate">
                            {conversation.lastMessage}
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {conversation.lastActivity}
                          </p>
                        </div>
                        <Badge variant="destructive" className="text-xs">
                          Decision
                        </Badge>
                      </div>
                    </div>
                  ))}
              </div>

              {/* Regular Conversations */}
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-2 px-2">
                  Recent Conversations
                </h3>
                {conversations
                  .filter(c => !c.hasDecision)
                  .map((conversation) => (
                    <div
                      key={conversation.id}
                      className={`p-3 rounded-lg mb-2 cursor-pointer transition-colors ${
                        conversation.isActive 
                          ? "bg-muted" 
                          : "hover:bg-muted/50"
                      }`}
                    >
                      <div className="flex items-center space-x-2 mb-1">
                        <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                        <h4 className="text-sm font-medium text-foreground truncate">
                          {conversation.title}
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground truncate">
                        {conversation.lastMessage}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {conversation.lastActivity}
                      </p>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Chat Header */}
          {activeConversation && (
            <div className="p-4 border-b border-border bg-card">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="flex items-center space-x-2">
                    {activeConversation.hasDecision ? (
                      <AlertCircle className="h-5 w-5 text-red-500" />
                    ) : (
                      <CheckCircle className="h-5 w-5 text-green-500" />
                    )}
                    <h2 className="text-lg font-semibold text-foreground">
                      {activeConversation.title}
                    </h2>
                  </div>
                  {activeConversation.hasDecision && (
                    <Badge variant="destructive">Decision Required</Badge>
                  )}
                </div>
                <div className="text-sm text-muted-foreground">
                  Last activity: {activeConversation.lastActivity}
                </div>
              </div>
            </div>
          )}

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {currentMessages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[70%] ${
                    msg.sender === "user"
                      ? "bg-primary text-primary-foreground"
                      : msg.needsDecision
                      ? "bg-red-500/10 border border-red-500/20"
                      : "bg-muted"
                  } rounded-lg p-4`}
                >
                  <div className="flex items-start space-x-2 mb-2">
                    {msg.sender === "assistant" ? (
                      <Bot className="h-4 w-4 mt-1 flex-shrink-0" />
                    ) : (
                      <User className="h-4 w-4 mt-1 flex-shrink-0" />
                    )}
                    <div className="flex-1">
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                      {msg.needsDecision && (
                        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                          <div className="flex items-center space-x-2 mb-2">
                            <AlertCircle className="h-4 w-4 text-red-500" />
                            <span className="text-sm font-medium text-red-500">
                              Decision Required
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground mb-3">
                            Please review the email draft above and choose an action:
                          </p>
                          <div className="flex space-x-2">
                            <Button size="sm" variant="default">
                              Send as-is
                            </Button>
                            <Button size="sm" variant="outline">
                              Request changes
                            </Button>
                            <Button size="sm" variant="ghost">
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="text-xs opacity-70 text-right">
                    {msg.timestamp}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Message Input */}
          <div className="p-4 border-t border-border bg-card">
            <div className="flex space-x-2">
              <Textarea
                value={message}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setMessage(e.target.value)}
                placeholder="Type your message..."
                className="flex-1 min-h-[40px] max-h-[120px]"
                onKeyDown={(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
              />
              <Button 
                onClick={handleSendMessage}
                disabled={!message.trim()}
                size="icon"
                className="h-[40px] w-[40px]"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Press Enter to send, Shift+Enter for new line
            </p>
          </div>
        </div>
      </div>
    </div>
  );
} 