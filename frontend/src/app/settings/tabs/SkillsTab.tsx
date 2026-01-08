"use client";

import { Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useSkills } from "@/hooks/useNovaQueries";

export function SkillsTab() {
  const { data: skillsData, isLoading, error } = useSkills();

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
        <div key={skill.name} className="border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-3">
              <Zap className="h-5 w-5 text-primary" />
              <h3 className="font-medium text-foreground">{skill.name}</h3>
              <Badge variant="secondary" className="text-xs">v{skill.version}</Badge>
            </div>
            <Badge variant="outline" className="text-xs">
              Installed
            </Badge>
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
