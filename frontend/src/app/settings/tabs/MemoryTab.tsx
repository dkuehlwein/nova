"use client";

import { useState, useEffect } from "react";
import { AlertCircle, Database, Search, Trash2, Plus, Loader2, FileText, Link2, ChevronDown, ChevronUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useMemorySearch, useMemoryHealth, useAddMemory, useDeleteMemoryFact, useRecentMemories, useRecentEpisodes, useDeleteEpisode } from "@/hooks/useNovaQueries";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

export function MemoryTab() {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [newMemoryContent, setNewMemoryContent] = useState("");
  const [newMemorySource, setNewMemorySource] = useState("");
  const [addFormOpen, setAddFormOpen] = useState(false);

  // Use search when there's a query, otherwise show recent memories
  const isSearching = debouncedQuery.trim().length > 0;
  const { data: searchData, isLoading: searchLoading, error: searchError, refetch: refetchSearch } = useMemorySearch(debouncedQuery);
  const { data: recentData, isLoading: recentLoading, error: recentError, refetch: refetchRecent } = useRecentMemories(20);

  // Select appropriate data source
  const memoryData = isSearching ? searchData : recentData;
  const memoryLoading = isSearching ? searchLoading : recentLoading;
  const memoryError = isSearching ? searchError : recentError;
  const refetch = isSearching ? refetchSearch : refetchRecent;

  const { data: healthData } = useMemoryHealth();
  const { data: episodesData, isLoading: episodesLoading, error: episodesError, refetch: refetchEpisodes } = useRecentEpisodes(20);
  const addMemoryMutation = useAddMemory();
  const deleteFactMutation = useDeleteMemoryFact();
  const deleteEpisodeMutation = useDeleteEpisode();

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleAddMemory = async () => {
    if (!newMemoryContent.trim() || !newMemorySource.trim()) return;

    try {
      await addMemoryMutation.mutateAsync({
        content: newMemoryContent.trim(),
        source_description: newMemorySource.trim()
      });
      setNewMemoryContent("");
      setNewMemorySource("");
      setAddFormOpen(false);
    } catch (error) {
      console.error("Failed to add memory:", error);
    }
  };

  const handleDeleteFact = async (factUuid: string) => {
    try {
      await deleteFactMutation.mutateAsync(factUuid);
    } catch (error) {
      console.error("Failed to delete fact:", error);
    }
  };

  const handleDeleteEpisode = async (episodeUuid: string) => {
    try {
      await deleteEpisodeMutation.mutateAsync(episodeUuid);
    } catch (error) {
      console.error("Failed to delete episode:", error);
    }
  };

  const handleClearAllFacts = async () => {
    if (!memoryData?.results) return;

    for (const fact of memoryData.results) {
      try {
        await deleteFactMutation.mutateAsync(fact.uuid);
      } catch (error) {
        console.error("Failed to delete fact:", fact.uuid, error);
      }
    }
    refetch();
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "Unknown";
    try {
      return new Date(dateStr).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header with Health Status */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-foreground">Memory System</h3>
          <p className="text-sm text-muted-foreground">
            Manage Nova&apos;s knowledge graph - facts extracted from episodes
          </p>
        </div>
        <Badge
          variant={healthData?.status === "healthy" ? "default" : "destructive"}
          className={healthData?.status === "healthy" ? "bg-green-500" : ""}
        >
          {healthData?.status === "healthy" ? "Connected" : healthData?.status || "Unknown"}
        </Badge>
      </div>

      {/* Collapsible Add Memory Form */}
      <Collapsible open={addFormOpen} onOpenChange={setAddFormOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="outline" className="w-full justify-between">
            <span className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              Add New Memory
            </span>
            {addFormOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-3">
          <div className="space-y-3 border border-muted rounded-lg p-4">
            <div className="space-y-2">
              <Label htmlFor="memory-content">Content</Label>
              <Textarea
                id="memory-content"
                placeholder="Enter information to remember (e.g., 'Daniel prefers dark mode')"
                value={newMemoryContent}
                onChange={(e) => setNewMemoryContent(e.target.value)}
                className="min-h-[60px]"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="memory-source">Source Description</Label>
              <Input
                id="memory-source"
                placeholder="Where this came from (e.g., 'User preference')"
                value={newMemorySource}
                onChange={(e) => setNewMemorySource(e.target.value)}
              />
            </div>
            <Button
              onClick={handleAddMemory}
              disabled={!newMemoryContent.trim() || !newMemorySource.trim() || addMemoryMutation.isPending}
              className="w-full"
            >
              {addMemoryMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Memory
                </>
              )}
            </Button>
            {addMemoryMutation.isSuccess && (
              <p className="text-sm text-green-600">Memory added successfully!</p>
            )}
            {addMemoryMutation.isError && (
              <p className="text-sm text-red-600">Failed to add memory.</p>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* Two Column Layout: Facts and Episodes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Facts Column */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Link2 className="h-4 w-4 text-muted-foreground" />
            <h4 className="font-medium text-foreground">Facts</h4>
            <span className="text-xs text-muted-foreground">
              ({memoryData?.count ?? 0})
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Extracted knowledge relationships from conversations and documents.
          </p>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search facts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 h-9"
            />
          </div>

          {/* Facts List */}
          <div className="border border-border rounded-lg">
            {memoryLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">Loading...</span>
              </div>
            )}

            {memoryError && (
              <div className="text-center py-6 text-red-500">
                <AlertCircle className="h-6 w-6 mx-auto mb-2" />
                <p className="text-sm">Failed to load</p>
                <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
                  Retry
                </Button>
              </div>
            )}

            {!memoryLoading && !memoryError && memoryData?.results && (
              <>
                {memoryData.results.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <Database className="h-6 w-6 mx-auto mb-2" />
                    <p className="text-sm">{isSearching ? "No facts found" : "No facts yet"}</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
                    {memoryData.results.map((fact) => (
                      <div
                        key={fact.uuid}
                        className="flex items-start justify-between p-3 hover:bg-muted/50 transition-colors group"
                      >
                        <div className="flex-1 min-w-0 pr-2">
                          <p className="text-sm text-foreground break-words leading-relaxed">{fact.fact}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {formatDate(fact.created_at)}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteFact(fact.uuid)}
                          disabled={deleteFactMutation.isPending}
                          className="opacity-0 group-hover:opacity-100 transition-opacity text-red-600 hover:text-red-700 hover:bg-red-50 shrink-0 h-7 w-7 p-0"
                        >
                          {deleteFactMutation.isPending ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Clear All Facts */}
          {memoryData?.results && memoryData.results.length > 0 && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm" className="w-full text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200">
                  <Trash2 className="h-3.5 w-3.5 mr-2" />
                  Clear All Facts
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Clear All Facts?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will permanently delete all {memoryData.count} facts. This cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleClearAllFacts} className="bg-red-600 hover:bg-red-700">
                    Yes, Clear All
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>

        {/* Episodes Column */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <h4 className="font-medium text-foreground">Episodes</h4>
            <span className="text-xs text-muted-foreground">
              ({episodesData?.count ?? 0})
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Raw input events (conversations, documents) that facts are extracted from.
          </p>

          {/* Spacer to align with search box */}
          <div className="h-9" />

          {/* Episodes List */}
          <div className="border border-border rounded-lg">
            {episodesLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">Loading...</span>
              </div>
            )}

            {episodesError && (
              <div className="text-center py-6 text-red-500">
                <AlertCircle className="h-6 w-6 mx-auto mb-2" />
                <p className="text-sm">Failed to load</p>
                <Button variant="outline" size="sm" className="mt-2" onClick={() => refetchEpisodes()}>
                  Retry
                </Button>
              </div>
            )}

            {!episodesLoading && !episodesError && episodesData?.episodes && (
              <>
                {episodesData.episodes.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <FileText className="h-6 w-6 mx-auto mb-2" />
                    <p className="text-sm">No episodes yet</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
                    {episodesData.episodes.map((episode) => (
                      <div
                        key={episode.uuid}
                        className="flex items-start justify-between p-3 hover:bg-muted/50 transition-colors group"
                      >
                        <div className="flex-1 min-w-0 pr-2">
                          <p className="text-sm font-medium text-foreground break-words">{episode.name}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {episode.source_description}
                          </p>
                          <p className="text-xs text-muted-foreground/70 mt-0.5 line-clamp-2">
                            {episode.content_preview}
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {formatDate(episode.created_at)}
                          </p>
                        </div>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={deleteEpisodeMutation.isPending}
                              className="opacity-0 group-hover:opacity-100 transition-opacity text-red-600 hover:text-red-700 hover:bg-red-50 shrink-0 h-7 w-7 p-0"
                            >
                              {deleteEpisodeMutation.isPending ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Trash2 className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete Episode?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This will permanently delete &quot;{episode.name}&quot; and may affect related facts.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => handleDeleteEpisode(episode.uuid)}
                                className="bg-red-600 hover:bg-red-700"
                              >
                                Yes, Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
