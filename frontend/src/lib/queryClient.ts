import { 
  QueryClient, 
  isServer,
  defaultShouldDehydrateQuery 
} from '@tanstack/react-query'

// Type definitions for Nova events
export interface NovaEvent {
  id: string
  type: string
  timestamp: string
  data: Record<string, unknown>
  source: string
}

export interface EventData {
  server_name?: string
  enabled?: boolean
  prompt_file?: string
  change_type?: string
  status_change?: boolean
  [key: string]: unknown
}

export interface MCPServer {
  name: string
  enabled: boolean
  [key: string]: unknown
}

export interface TaskCountsData {
  last_updated?: string
  [key: string]: unknown
}

// Factory function for creating query client
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // With SSR, we usually want to set some default staleTime
        // above 0 to avoid refetching immediately on the client
        // But for Nova's real-time system, we want immediate updates
        staleTime: 0, // Always consider data stale for real-time updates
        gcTime: 1000 * 60 * 5, // Keep data in cache for 5 minutes
        retry: 2,
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
      },
      mutations: {
        retry: 1,
      },
      dehydrate: {
        // include pending queries in dehydration for streaming
        shouldDehydrateQuery: (query) =>
          defaultShouldDehydrateQuery(query) ||
          query.state.status === 'pending',
      },
    },
  })
}

let browserQueryClient: QueryClient | undefined = undefined

export function getQueryClient() {
  if (isServer) {
    // Server: always make a new query client
    return makeQueryClient()
  } else {
    // Browser: make a new query client if we don't already have one
    // This is very important, so we don't re-make a new client if React
    // suspends during the initial render. This may not be needed if we
    // have a suspense boundary BELOW the creation of the query client
    if (!browserQueryClient) browserQueryClient = makeQueryClient()
    return browserQueryClient
  }
}

// Export the query client for backwards compatibility
export const queryClient = getQueryClient()

// Helper function to invalidate queries when WebSocket events are received
export const invalidateQueriesByEvent = (eventType: string, data: EventData) => {
  const client = getQueryClient()
  
  switch (eventType) {
    case 'mcp_toggled':
      // Invalidate MCP server queries when a server is toggled
      client.invalidateQueries({ queryKey: ['mcp-servers'] })
      // Also invalidate system health since MCP server status affects overall health
      client.invalidateQueries({ queryKey: ['system-health-summary'] })
      break
    case 'prompt_updated':
      // Invalidate system prompt queries when prompt is updated
      client.invalidateQueries({ queryKey: ['system-prompt'] })
      client.invalidateQueries({ queryKey: ['system-prompt-backups'] })
      // Also invalidate agent-related queries since prompt affects agent behavior
      client.invalidateQueries({ queryKey: ['agent-status'] })
      break
    case 'task_updated':
      // Invalidate task-related queries
      client.invalidateQueries({ queryKey: ['tasks'] })
      client.invalidateQueries({ queryKey: ['task-counts'] })
      // Also invalidate overview data that includes task counts
      client.invalidateQueries({ queryKey: ['overview'] })
      break
    case 'system_health':
      // Invalidate health-related queries
      client.invalidateQueries({ queryKey: ['system-health'] })
      client.invalidateQueries({ queryKey: ['system-health-summary'] })
      client.invalidateQueries({ queryKey: ['mcp-servers'] })
      break
    case 'config_validated':
      // Invalidate configuration queries
      client.invalidateQueries({ queryKey: ['config'] })
      client.invalidateQueries({ queryKey: ['config-validation'] })
      break
    default:
      // For unknown events, invalidate all queries to be safe
      console.log(`Unknown event type: ${eventType}`, data)
  }
}

// Helper to update specific query data from WebSocket events
export const updateQueryDataFromEvent = (eventType: string, data: EventData) => {
  const client = getQueryClient()
  
  switch (eventType) {
    case 'mcp_toggled':
      // Update MCP server data in cache directly
      client.setQueryData(['mcp-servers'], (oldData: unknown) => {
        // Generic typing approach to handle MCP server data
        const typedOldData = oldData as { servers?: MCPServer[] } | undefined
        if (!typedOldData?.servers) return oldData
        
        return {
          ...typedOldData,
          servers: typedOldData.servers.map((server: MCPServer) => 
            server.name === data.server_name 
              ? { ...server, enabled: data.enabled }
              : server
          )
        }
      })
      break
    case 'task_updated':
      // Update overview and task counts cache for real-time updates
      const timestamp = new Date().toISOString()
      
      // Update overview data (used by Navbar)
      client.setQueryData(['overview'], (oldData: unknown) => {
        const typedOldData = oldData as TaskCountsData | undefined
        if (!typedOldData) return oldData
        
        return { 
          ...typedOldData, 
          last_updated: timestamp
        }
      })
      
      // Update task-counts cache
      client.setQueryData(['task-counts'], (oldData: unknown) => {
        const typedOldData = oldData as TaskCountsData | undefined
        if (!typedOldData) return oldData
        
        return { 
          ...typedOldData, 
          last_updated: timestamp 
        }
      })
      break
  }
}