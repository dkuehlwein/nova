"use client";

import { useState, useEffect } from "react";
import { Zap, Settings, ChevronDown, ChevronUp, Save, RotateCcw, Loader2, AlertCircle, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useSkills, useSkillConfig, useUpdateSkillConfig } from "@/hooks/useNovaQueries";

interface SkillInfo {
  name: string;
  version: string;
  description: string;
  author: string;
  tags: string[];
  has_config: boolean;
}

function SkillConfigEditor({ skillName }: { skillName: string }) {
  const { data: configData, isLoading, error } = useSkillConfig(skillName);
  const updateMutation = useUpdateSkillConfig();

  const [content, setContent] = useState("");
  const [hasChanges, setHasChanges] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // Sync content with fetched data
  useEffect(() => {
    if (configData?.content) {
      setContent(configData.content);
      setHasChanges(false);
    }
  }, [configData?.content]);

  // Track changes
  useEffect(() => {
    if (configData?.content) {
      setHasChanges(content !== configData.content);
    }
  }, [content, configData?.content]);

  // Clear success message after delay
  useEffect(() => {
    if (showSuccess) {
      const timer = setTimeout(() => setShowSuccess(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [showSuccess]);

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({ skillName, content });
      setHasChanges(false);
      setShowSuccess(true);
    } catch {
      // Error is handled by mutation state
    }
  };

  const handleRevert = () => {
    if (configData?.content) {
      setContent(configData.content);
      setHasChanges(false);
    }
  };

  if (isLoading) {
    return (
      <div className="border-t border-border p-4 bg-muted/30">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Loading configuration...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-t border-border p-4 bg-muted/30">
        <div className="flex items-center space-x-2 text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm">Failed to load configuration</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border-t border-border p-4 bg-muted/30">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm text-muted-foreground">
          <code className="bg-muted px-2 py-0.5 rounded text-xs">{configData?.file_path}</code>
        </div>
        {hasChanges && (
          <Badge variant="outline" className="text-yellow-600 border-yellow-600/50">
            Unsaved changes
          </Badge>
        )}
      </div>

      <Textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="min-h-[300px] font-mono text-sm bg-background"
        placeholder="# YAML configuration..."
        disabled={updateMutation.isPending}
      />

      {updateMutation.isError && (
        <div className="flex items-center space-x-2 text-destructive text-sm mt-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>
            {updateMutation.error instanceof Error
              ? updateMutation.error.message
              : "Failed to save configuration. Check YAML syntax."}
          </span>
        </div>
      )}

      {showSuccess && (
        <div className="flex items-center space-x-2 text-green-600 text-sm mt-2">
          <Check className="h-4 w-4" />
          <span>Configuration saved successfully. Hot-reload applied.</span>
        </div>
      )}

      <div className="flex items-center justify-between mt-3">
        <div className="text-xs text-muted-foreground">
          Last modified: {configData?.last_modified ? new Date(configData.last_modified).toLocaleString() : "Unknown"}
          {" | "}
          Size: {configData?.size_bytes ?? 0} bytes
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRevert}
            disabled={!hasChanges || updateMutation.isPending}
          >
            <RotateCcw className="h-4 w-4 mr-1" />
            Revert
          </Button>
          <Button
            size="sm"
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
    </div>
  );
}

function SkillCard({ skill, isExpanded, onToggle }: {
  skill: SkillInfo;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <Collapsible open={isExpanded} onOpenChange={onToggle}>
      <div className="border border-border rounded-lg overflow-hidden">
        {/* Skill header - always visible */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-3">
              <Zap className="h-5 w-5 text-primary" />
              <h3 className="font-medium text-foreground">{skill.name}</h3>
              <Badge variant="secondary" className="text-xs">v{skill.version}</Badge>
              {skill.has_config && (
                <Badge variant="outline" className="text-xs">
                  <Settings className="h-3 w-3 mr-1" />
                  Configurable
                </Badge>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="text-xs">
                Installed
              </Badge>
              {skill.has_config && (
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" size="sm">
                    {isExpanded ? (
                      <>
                        <ChevronUp className="h-4 w-4 mr-1" />
                        Hide Config
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-4 w-4 mr-1" />
                        Edit Config
                      </>
                    )}
                  </Button>
                </CollapsibleTrigger>
              )}
            </div>
          </div>
          <p className="text-sm text-muted-foreground mb-3">{skill.description}</p>
          <div className="flex flex-wrap gap-2">
            {skill.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-2">Author: {skill.author}</p>
        </div>

        {/* Expandable config editor */}
        {skill.has_config && (
          <CollapsibleContent>
            <SkillConfigEditor skillName={skill.name} />
          </CollapsibleContent>
        )}
      </div>
    </Collapsible>
  );
}

export function SkillsTab() {
  const { data: skillsData, isLoading, error } = useSkills();
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);

  if (error) {
    return (
      <div className="space-y-4">
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
          <p className="text-sm text-destructive">Failed to load skills</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2].map((i) => (
          <div key={i} className="border border-border rounded-lg p-4 animate-pulse">
            <div className="flex items-center space-x-3 mb-2">
              <div className="h-5 w-5 bg-muted rounded" />
              <div className="h-4 w-32 bg-muted rounded" />
              <div className="h-4 w-16 bg-muted rounded" />
            </div>
            <div className="h-4 w-full bg-muted rounded mb-2" />
            <div className="flex gap-2">
              <div className="h-5 w-12 bg-muted rounded" />
              <div className="h-5 w-16 bg-muted rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground mb-4">
        Skills are specialized capabilities that Nova can activate on-demand.
        When you ask Nova to do something that matches a skill, it will automatically load the relevant tools and instructions.
      </p>

      {skillsData?.skills?.map((skill) => (
        <SkillCard
          key={skill.name}
          skill={skill}
          isExpanded={expandedSkill === skill.name}
          onToggle={() => setExpandedSkill(
            expandedSkill === skill.name ? null : skill.name
          )}
        />
      ))}

      {(!skillsData?.skills || skillsData.skills.length === 0) && (
        <div className="text-center py-8 text-muted-foreground">
          <Zap className="h-8 w-8 mx-auto mb-2" />
          <p className="text-sm">No skills installed</p>
          <p className="text-xs mt-1">Add skills to backend/skills/ to see them here</p>
        </div>
      )}
    </div>
  );
}
