"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, Save, RotateCcw, Clock, FileText, Loader2, Trash2 } from "lucide-react";
import { 
  useSystemPrompt, 
  useUpdateSystemPrompt, 
  useSystemPromptBackups, 
  useRestorePromptBackup,
  useDeletePromptBackup
} from "@/hooks/useNovaQueries";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export default function SystemPromptEditor() {
  const { data: promptData, isLoading: promptLoading, error: promptError } = useSystemPrompt();
  const { data: backupsData } = useSystemPromptBackups();
  const updateMutation = useUpdateSystemPrompt();
  const restoreMutation = useRestorePromptBackup();
  const deleteMutation = useDeletePromptBackup();
  
  const [content, setContent] = useState("");
  const [hasChanges, setHasChanges] = useState(false);
  const [showBackups, setShowBackups] = useState(false);

  // Update local content when prompt data loads
  useEffect(() => {
    if (promptData?.content) {
      setContent(promptData.content);
      setHasChanges(false);
    }
  }, [promptData?.content]);

  // Track changes
  useEffect(() => {
    if (promptData?.content) {
      setHasChanges(content !== promptData.content);
    }
  }, [content, promptData?.content]);

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync(content);
      setHasChanges(false);
    } catch (error) {
      console.error('Failed to save prompt:', error);
    }
  };

  const handleRevert = () => {
    if (promptData?.content) {
      setContent(promptData.content);
      setHasChanges(false);
    }
  };

  const handleRestoreBackup = async (backupFilename: string) => {
    try {
      await restoreMutation.mutateAsync(backupFilename);
      setShowBackups(false);
    } catch (error) {
      console.error('Failed to restore backup:', error);
    }
  };

  const handleDeleteBackup = async (backupFilename: string) => {
    try {
      await deleteMutation.mutateAsync(backupFilename);
    } catch (error) {
      console.error('Failed to delete backup:', error);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (promptLoading) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-center h-32">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-muted-foreground">Loading system prompt...</span>
        </div>
      </div>
    );
  }

  if (promptError) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center space-x-2 text-red-600 mb-4">
          <AlertCircle className="h-5 w-5" />
          <h3 className="font-medium">Failed to load system prompt</h3>
        </div>
        <p className="text-sm text-muted-foreground">
          Unable to load the system prompt. Please check if the backend is running.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center space-x-2">
            <FileText className="h-5 w-5 text-primary" />
            <span>System Prompt</span>
          </h2>
          <p className="text-sm text-muted-foreground">
            Configure Nova&apos;s AI behavior and capabilities
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {hasChanges && (
            <Badge variant="secondary" className="text-yellow-600">
              Unsaved changes
            </Badge>
          )}
          <Dialog open={showBackups} onOpenChange={setShowBackups}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Clock className="h-4 w-4 mr-1" />
                Backups
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>System Prompt Backups</DialogTitle>
                <p className="text-sm text-muted-foreground">
                  Restore from a previous version of the system prompt
                </p>
              </DialogHeader>
              <div className="max-h-96 overflow-y-auto">
                {backupsData?.backups?.length ? (
                  <div className="space-y-2">
                    {backupsData.backups.map((backup) => (
                      <div 
                        key={backup.filename} 
                        className="flex items-center justify-between p-3 border border-border rounded-lg"
                      >
                        <div>
                          <p className="font-medium">{backup.filename}</p>
                          <p className="text-sm text-muted-foreground">
                            {formatDate(backup.created)} • {formatFileSize(backup.size_bytes)}
                          </p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRestoreBackup(backup.filename)}
                            disabled={restoreMutation.isPending || deleteMutation.isPending}
                          >
                            {restoreMutation.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <RotateCcw className="h-4 w-4" />
                            )}
                            Restore
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDeleteBackup(backup.filename)}
                            disabled={restoreMutation.isPending || deleteMutation.isPending}
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                          >
                            {deleteMutation.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                            Delete
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Clock className="h-8 w-8 mx-auto mb-2" />
                    <p>No backups available</p>
                  </div>
                )}
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="space-y-4">
        <Textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Enter system prompt content..."
          className="min-h-[400px] font-mono text-sm"
          disabled={updateMutation.isPending}
        />
        
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            {promptData && (
              <span>
                Last modified: {formatDate(promptData.last_modified)} • 
                Size: {formatFileSize(promptData.size_bytes)}
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              onClick={handleRevert}
              disabled={!hasChanges || updateMutation.isPending}
            >
              <RotateCcw className="h-4 w-4 mr-1" />
              Revert
            </Button>
            <Button
              onClick={handleSave}
              disabled={!hasChanges || updateMutation.isPending}
            >
              {updateMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <Save className="h-4 w-4 mr-1" />
              )}
              Save Changes
            </Button>
          </div>
        </div>
        
        {updateMutation.error && (
          <div className="flex items-center space-x-2 text-red-600 text-sm">
            <AlertCircle className="h-4 w-4" />
            <span>Failed to save prompt. Please try again.</span>
          </div>
        )}
        
        {updateMutation.isSuccess && !hasChanges && (
          <div className="text-green-600 text-sm">
            ✓ System prompt saved successfully
          </div>
        )}
      </div>
    </div>
  );
} 