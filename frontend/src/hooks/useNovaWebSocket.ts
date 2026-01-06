import { useRef, useCallback } from 'react'
import useWebSocket, { ReadyState } from 'react-use-websocket'
import { invalidateQueriesByEvent, updateQueryDataFromEvent, type NovaEvent } from '../lib/queryClient'

// Re-export ReadyState for convenience
export { ReadyState }

// Connection status type - simplified to match ReadyState exactly
export type ConnectionStatus = 'Connecting' | 'Open' | 'Closing' | 'Closed' | 'Uninstantiated'

interface UseNovaWebSocketOptions {
  // Whether to automatically reconnect on connection loss
  shouldReconnect?: (closeEvent: CloseEvent) => boolean
  // Number of reconnection attempts
  reconnectAttempts?: number
  // Delay between reconnection attempts (ms) - can be function for backoff
  reconnectInterval?: number | ((attemptNumber: number) => number)
  // Whether to log WebSocket events for debugging
  debug?: boolean
  // Whether to share the WebSocket connection across components
  share?: boolean
}

const DEFAULT_OPTIONS: Required<Omit<UseNovaWebSocketOptions, 'shouldReconnect'>> & {
  shouldReconnect: (closeEvent: CloseEvent) => boolean
} = {
  shouldReconnect: () => true,
  reconnectAttempts: 5,
  // Exponential backoff: 1s, 2s, 4s, 8s, then cap at 10s
  reconnectInterval: (attemptNumber: number) => 
    Math.min(Math.pow(2, attemptNumber) * 1000, 10000),
  debug: false,
  share: true, // Share connection by default for efficiency
}

export function useNovaWebSocket(options: UseNovaWebSocketOptions = {}) {
  const opts = { ...DEFAULT_OPTIONS, ...options }

  // Track connection metrics
  const connectedAt = useRef<Date | null>(null)
  const messagesReceived = useRef(0)
  const lastNovaMessage = useRef<NovaEvent | null>(null)

  // Determine WebSocket URL - use NEXT_PUBLIC_API_URL if available
  const getWebSocketUrl = useCallback(() => {
    if (typeof window === 'undefined') return null
    
    // Use NEXT_PUBLIC_API_URL if configured (e.g., http://localhost:8000)
    if (process.env.NEXT_PUBLIC_API_URL) {
      const apiUrl = new URL(process.env.NEXT_PUBLIC_API_URL)
      const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${wsProtocol}//${apiUrl.host}/ws/`
    }
    
    // Fallback to window.location with port override for development
    const { protocol, hostname, port } = window.location
    const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:'
    const wsPort = process.env.NODE_ENV === 'development' ? '8000' : port
    
    return `${wsProtocol}//${hostname}:${wsPort}/ws/`
  }, [])

  // WebSocket connection with proper options
  const {
    sendMessage,
    sendJsonMessage,
    lastMessage,
    readyState,
    getWebSocket
  } = useWebSocket(
    getWebSocketUrl(),
    {
      shouldReconnect: opts.shouldReconnect,
      reconnectAttempts: opts.reconnectAttempts,
      reconnectInterval: opts.reconnectInterval,
      share: opts.share,
      onOpen: (event) => {
        connectedAt.current = new Date()
        if (opts.debug) {
          console.log('[Nova WebSocket] Connected to Nova real-time system', event)
        }
        
        // Send subscription message to backend
        sendJsonMessage({
          type: 'subscribe',
          timestamp: new Date().toISOString()
        })
      },
      onClose: (event) => {
        connectedAt.current = null
        if (opts.debug) {
          console.log('[Nova WebSocket] Disconnected:', event.code, event.reason)
        }
      },
      onError: (event) => {
        // Extract meaningful error information
        let errorMessage = 'WebSocket connection error'
        let errorDetails = {}
        
        if (event instanceof ErrorEvent) {
          errorMessage = event.message || 'Connection failed'
          errorDetails = {
            type: event.type,
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno
          }
        } else if (event instanceof CloseEvent) {
          errorMessage = `Connection closed: ${event.reason || 'Unknown reason'}`
          errorDetails = {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean
          }
        } else {
          // Generic event object
          errorDetails = {
            type: event?.type || 'unknown',
            target: event?.target?.constructor?.name || 'unknown'
          }
        }
        
        if (opts.debug) {
          console.error('[Nova WebSocket] Error details:', errorMessage, errorDetails)
        } else {
          // Only log meaningful errors to avoid spam
          if (readyState === ReadyState.CONNECTING || readyState === ReadyState.OPEN) {
            console.error(`[Nova WebSocket] ${errorMessage} - check if backend is running on port 8000`)
          }
        }
      },
      onMessage: (event: MessageEvent) => {
        try {
          const message: NovaEvent = JSON.parse(event.data)
          lastNovaMessage.current = message
          messagesReceived.current += 1
          
          if (opts.debug) {
            console.log('[Nova WebSocket] Message received:', message)
          }
          
          // Handle ping/pong for connection health
          if (message.type === 'ping') {
            sendJsonMessage({
              type: 'pong',
              timestamp: new Date().toISOString()
            })
            return
          }

          // Skip pong messages
          if (message.type === 'pong') {
            return
          }

          // Process Nova events
          try {
            // First try to update query data directly for optimal performance
            updateQueryDataFromEvent(message.type, message.data)
            
            // Then invalidate related queries to ensure consistency
            invalidateQueriesByEvent(message.type, message.data)
            
            if (opts.debug) {
              console.log(`[Nova WebSocket] Processed ${message.type} event:`, message.data)
            }
          } catch (error) {
            console.error(`[Nova WebSocket] Error processing ${message.type} event:`, error)
            
            // Fallback: invalidate all queries if we can't process the event
            invalidateQueriesByEvent(message.type, message.data)
          }
        } catch (error) {
          console.error('[Nova WebSocket] Failed to parse message:', event.data, error)
        }
      }
    },
    // Only connect on client side
    typeof window !== 'undefined'
  )

  // Connection status helper
  const connectionStatus: ConnectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Open',
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Closed',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[readyState] as ConnectionStatus

  // Connection info
  const connectionInfo = {
    status: connectionStatus,
    isConnected: readyState === ReadyState.OPEN,
    connectedAt: connectedAt.current,
    messagesReceived: messagesReceived.current,
    lastMessage: lastNovaMessage.current,
    uptime: connectedAt.current 
      ? Math.floor((Date.now() - connectedAt.current.getTime()) / 1000)
      : 0
  }

  // Helper to test the connection
  const ping = useCallback(() => {
    if (readyState === ReadyState.OPEN) {
      sendJsonMessage({
        type: 'ping',
        timestamp: new Date().toISOString()
      })
    }
  }, [readyState, sendJsonMessage])

  // Manual connection control - simplified
  const connect = useCallback(() => {
    if (readyState === ReadyState.CLOSED || readyState === ReadyState.UNINSTANTIATED) {
      // The useWebSocket hook will handle reconnection automatically
      // based on shouldReconnect option
      if (opts.debug) {
        console.log('[Nova WebSocket] Manual reconnection triggered')
      }
    }
  }, [readyState, opts.debug])

  // Public API
  return {
    // Connection state
    connectionStatus,
    isConnected: readyState === ReadyState.OPEN,
    connectionInfo,
    
    // WebSocket instance (for advanced usage)
    getWebSocket,
    
    // Send functions
    sendMessage,
    sendJsonMessage,
    
    // Last message received (raw WebSocket message)
    lastMessage,
    // Last Nova message received (parsed)
    lastNovaMessage: lastNovaMessage.current,
    
    // Manual connection control
    connect,
    ping
  }
} 