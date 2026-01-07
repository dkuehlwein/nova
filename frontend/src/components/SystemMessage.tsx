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
          bgColor: "bg-blue-50 dark:bg-blue-900/30",
          borderColor: "border-blue-200 dark:border-blue-700",
          iconBg: "bg-blue-500 dark:bg-blue-600",
          textColor: "text-blue-800 dark:text-blue-200",
          labelColor: "text-blue-900 dark:text-blue-100",
          timestampColor: "text-blue-600 dark:text-blue-400",
          buttonColor: "text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300",
          borderAccent: "border-blue-200 dark:border-blue-600",
          icon: Settings,
          label: title || "System Guidelines"
        };
      case "task_context":
        return {
          bgColor: "bg-amber-50 dark:bg-amber-900/30",
          borderColor: "border-amber-200 dark:border-amber-700",
          iconBg: "bg-amber-500 dark:bg-amber-600",
          textColor: "text-amber-800 dark:text-amber-200",
          labelColor: "text-amber-900 dark:text-amber-100",
          timestampColor: "text-amber-600 dark:text-amber-400",
          buttonColor: "text-amber-600 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300",
          borderAccent: "border-amber-200 dark:border-amber-600",
          icon: FileText,
          label: title || "Task Context"
        };
      default:
        return {
          bgColor: "bg-gray-50 dark:bg-gray-800/50",
          borderColor: "border-gray-200 dark:border-gray-700",
          iconBg: "bg-gray-500 dark:bg-gray-600",
          textColor: "text-gray-800 dark:text-gray-200",
          labelColor: "text-gray-900 dark:text-gray-100",
          timestampColor: "text-gray-600 dark:text-gray-400",
          buttonColor: "text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-300",
          borderAccent: "border-gray-200 dark:border-gray-600",
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