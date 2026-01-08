"use client";

import Navbar from "@/components/Navbar";
import { Brain, FileText, ListChecks, ShieldCheck, User, Key, Cog, Zap, Database } from "lucide-react";
import { useState, Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import SystemPromptEditor from "@/components/SystemPromptEditor";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { TabContentLoader } from "./components";
import {
  MCPServersTab,
  SkillsTab,
  MemoryTab,
  SystemStatusTab,
  UserSettingsTab,
  APIKeysTab,
  AIModelsTab,
  AutomationTab
} from "./tabs";

function SettingsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [currentTab, setCurrentTab] = useState("ai-models");

  // Initialize current tab from URL or default
  useEffect(() => {
    const tabFromUrl = searchParams.get("tab");
    if (tabFromUrl) {
      setCurrentTab(tabFromUrl);
    }
  }, [searchParams]);

  // Handle tab change and update URL
  const handleTabChange = (newTab: string) => {
    setCurrentTab(newTab);
    const newUrl = `/settings?tab=${newTab}`;
    router.push(newUrl, { scroll: false });
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <Tabs value={currentTab} onValueChange={handleTabChange} orientation="vertical" className="flex h-[calc(100vh-4rem)]">
        {/* Left Sidebar */}
        <div className="w-64 border-r border-border bg-muted/30 flex-shrink-0">
          <div className="p-4 border-b border-border">
            <h1 className="font-semibold text-foreground">Settings</h1>
            <p className="text-sm text-muted-foreground">Manage your preferences</p>
          </div>
          <TabsList className="w-full h-auto flex-col bg-transparent space-y-1 p-2">
            <TabsTrigger
              value="user-profile"
              className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <User className="h-4 w-4 mr-2" />
              Personal
            </TabsTrigger>
            <TabsTrigger
              value="ai-models"
              className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <Brain className="h-4 w-4 mr-2" />
              AI Models
            </TabsTrigger>
            <TabsTrigger
              value="api-keys"
              className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <Key className="h-4 w-4 mr-2" />
              API Keys
            </TabsTrigger>
            <TabsTrigger
              value="automation"
              className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <Cog className="h-4 w-4 mr-2" />
              Automation
            </TabsTrigger>
            <TabsTrigger
              value="memory"
              className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <Database className="h-4 w-4 mr-2" />
              Memory
            </TabsTrigger>
            <TabsTrigger
              value="system-prompt"
              className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <FileText className="h-4 w-4 mr-2" />
              System Prompt
            </TabsTrigger>
            <TabsTrigger
              value="mcp-servers"
              className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <ListChecks className="h-4 w-4 mr-2" />
              MCP Servers
            </TabsTrigger>
            <TabsTrigger
              value="skills"
              className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <Zap className="h-4 w-4 mr-2" />
              Skills
            </TabsTrigger>
            <TabsTrigger
              value="system-status"
              className="w-full justify-start data-[state=active]:bg-background data-[state=active]:shadow-sm"
            >
              <ShieldCheck className="h-4 w-4 mr-2" />
              System Status
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-y-auto p-6">
          <TabsContent value="system-prompt" className="mt-0">
            <Suspense fallback={<TabContentLoader>System Prompt</TabContentLoader>}>
              <SystemPromptEditor />
            </Suspense>
          </TabsContent>

          <TabsContent value="mcp-servers" className="mt-0">
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">MCP Servers Management</h2>
              <MCPServersTab />
            </div>
          </TabsContent>

          <TabsContent value="skills" className="mt-0">
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">Available Skills</h2>
              <SkillsTab />
            </div>
          </TabsContent>

          <TabsContent value="system-status" className="mt-0">
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">System Status Overview</h2>
              <SystemStatusTab />
            </div>
          </TabsContent>

          <TabsContent value="user-profile" className="mt-0 max-w-4xl">
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">Personal Settings</h2>
              <Suspense fallback={<TabContentLoader>Personal Settings</TabContentLoader>}>
                <UserSettingsTab />
              </Suspense>
            </div>
          </TabsContent>

          <TabsContent value="ai-models" className="mt-0 max-w-4xl">
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">AI Models & Infrastructure</h2>
              <Suspense fallback={<TabContentLoader>AI Models</TabContentLoader>}>
                <AIModelsTab />
              </Suspense>
            </div>
          </TabsContent>

          <TabsContent value="api-keys" className="mt-0 max-w-4xl">
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">External API Keys</h2>
              <Suspense fallback={<TabContentLoader>API Keys</TabContentLoader>}>
                <APIKeysTab />
              </Suspense>
            </div>
          </TabsContent>

          <TabsContent value="automation" className="mt-0 max-w-4xl">
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">Automation & Processing</h2>
              <Suspense fallback={<TabContentLoader>Automation</TabContentLoader>}>
                <AutomationTab />
              </Suspense>
            </div>
          </TabsContent>

          <TabsContent value="memory" className="mt-0 max-w-4xl">
            <div className="bg-card border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">Memory Management</h2>
              <Suspense fallback={<TabContentLoader>Memory</TabContentLoader>}>
                <MemoryTab />
              </Suspense>
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
          <div className="text-muted-foreground">Loading settings...</div>
        </div>
      </div>
    }>
      <SettingsPageContent />
    </Suspense>
  );
}
