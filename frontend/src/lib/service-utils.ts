/**
 * Service Display Utilities
 * 
 * Utility functions for handling service display names and metadata.
 */

/**
 * Get user-friendly display name for services
 */
export function getServiceDisplayName(serviceName: string): string {
  const displayNames: Record<string, string> = {
    "ai_models": "AI Models",
    "chat_agent": "Chat Agent", 
    "core_agent": "Core Agent",
    "litellm": "LiteLLM Gateway",
    "database": "Database",
    "redis": "Redis Cache",
    "neo4j": "Neo4j Graph DB",
    "mcp_servers": "MCP Servers"
  };
  
  return displayNames[serviceName] || serviceName;
}

/**
 * Extract AI model features from service metadata
 */
export function getAIModelFeatures(metadata: any): string[] | null {
  if (!metadata) return null;
  
  const chatCount = metadata.chat_models_count || 0;
  const embeddingCount = metadata.embedding_models_count || 0;
  
  return [
    `${chatCount} chat model${chatCount !== 1 ? 's' : ''}`,
    `${embeddingCount} embedding model${embeddingCount !== 1 ? 's' : ''}`
  ];
}

/**
 * Get AI model status message from metadata
 */
export function getAIModelMessage(metadata: any): string | null {
  return metadata?.message || null;
}