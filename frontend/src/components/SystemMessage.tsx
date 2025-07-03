"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Settings, FileText } from "lucide-react";
import { MarkdownMessage } from "./MarkdownMessage";

interface SystemMessageProps {
  content: string;
  collapsibleContent?: string;
  isCollapsible?: boolean;
  timestamp: string;
  messageType?: string;
  title?: string;
}

export function SystemMessage({ 
  content, 
  collapsibleContent, 
  isCollapsible = false,
  timestamp,
  messageType = "system_prompt",
  title
}: SystemMessageProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const formatTimestamp = (timestamp: string) => {
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
  };

  // Get styling and icon based on message type
  const getMessageStyle = () => {
    switch (messageType) {
      case "system_prompt":
        return {
          bgColor: "bg-blue-50",
          borderColor: "border-blue-200",
          iconBg: "bg-blue-500",
          textColor: "text-blue-800",
          labelColor: "text-blue-900",
          timestampColor: "text-blue-600",
          buttonColor: "text-blue-600 hover:text-blue-800",
          borderAccent: "border-blue-200",
          icon: Settings,
          label: title || "System Guidelines"
        };
      case "task_context":
        return {
          bgColor: "bg-amber-50",
          borderColor: "border-amber-200",
          iconBg: "bg-amber-500",
          textColor: "text-amber-800",
          labelColor: "text-amber-900",
          timestampColor: "text-amber-600",
          buttonColor: "text-amber-600 hover:text-amber-800",
          borderAccent: "border-amber-200",
          icon: FileText,
          label: title || "Task Context"
        };
      case "memory_context":
        return {
          bgColor: "bg-amber-50",
          borderColor: "border-amber-200",
          iconBg: "bg-amber-500",
          textColor: "text-amber-800",
          labelColor: "text-amber-900",
          timestampColor: "text-amber-600",
          buttonColor: "text-amber-600 hover:text-amber-800",
          borderAccent: "border-amber-200",
          icon: FileText,
          label: title || "Context from Memory"
        };
      default:
        return {
          bgColor: "bg-gray-50",
          borderColor: "border-gray-200",
          iconBg: "bg-gray-500",
          textColor: "text-gray-800",
          labelColor: "text-gray-900",
          timestampColor: "text-gray-600",
          buttonColor: "text-gray-600 hover:text-gray-800",
          borderAccent: "border-gray-200",
          icon: Settings,
          label: title || "System"
        };
    }
  };

  const style = getMessageStyle();
  const IconComponent = style.icon;

  const getExpandButtonText = () => {
    switch (messageType) {
      case "system_prompt":
        return isExpanded ? 'Hide guidelines' : 'Show guidelines & capabilities';
      case "task_context":
        return isExpanded ? 'Hide context' : 'Show task details';
      case "memory_context":
        return isExpanded ? 'Hide context' : 'Show memory details';
      default:
        return isExpanded ? 'Hide details' : 'Show details';
    }
  };

  return (
    <div className="mb-4">
      <div className={`max-w-[80%] min-w-[200px] ${style.bgColor} ${style.borderColor} border rounded-lg p-4`}>
        <div className="flex items-start space-x-3">
          <div className="flex-shrink-0">
            <div className={`w-8 h-8 rounded-full ${style.iconBg} flex items-center justify-center`}>
              <IconComponent className="h-4 w-4 text-white" />
            </div>
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2 mb-1">
              <span className={`text-sm font-medium ${style.labelColor}`}>
                {style.label}
              </span>
              <span className={`text-xs ${style.timestampColor}`}>
                {formatTimestamp(timestamp)}
              </span>
            </div>
            
            <div className={`text-sm ${style.textColor} break-words`}>
              <MarkdownMessage content={content} />
              
              {isCollapsible && collapsibleContent && (
                <div className="mt-3">
                  <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className={`flex items-center space-x-1 ${style.buttonColor} transition-colors text-xs font-medium`}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                    <span>
                      {getExpandButtonText()}
                    </span>
                  </button>
                  
                  {isExpanded && (
                    <div className={`mt-2 pl-4 border-l-2 ${style.borderAccent}`}>
                      <MarkdownMessage content={collapsibleContent} />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 