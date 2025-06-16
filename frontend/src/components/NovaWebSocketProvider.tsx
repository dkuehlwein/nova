'use client'

import React, { createContext, useContext, ReactNode } from 'react'
import { useNovaWebSocket, ConnectionStatus } from '../hooks/useNovaWebSocket'

// Context for WebSocket connection
interface NovaWebSocketContextType {
  connectionStatus: ConnectionStatus
  isConnected: boolean
  connectionInfo: {
    status: ConnectionStatus
    isConnected: boolean
    connectedAt: Date | null
    messagesReceived: number
    lastMessage: unknown
    uptime: number
  }
  ping: () => void
  connect: () => void
}

const NovaWebSocketContext = createContext<NovaWebSocketContextType | null>(null)

interface NovaWebSocketProviderProps {
  children: ReactNode
  debug?: boolean
}

export function NovaWebSocketProvider({ children, debug = false }: NovaWebSocketProviderProps) {
  const webSocket = useNovaWebSocket({
    debug,
    shouldReconnect: (closeEvent) => {
      // Don't reconnect on intentional closures (1000 = normal closure)
      return closeEvent.code !== 1000
    },
    reconnectAttempts: 10,
    // Exponential backoff with jitter
    reconnectInterval: (attemptNumber) => {
      const baseDelay = Math.min(Math.pow(2, attemptNumber) * 1000, 10000)
      // Add jitter (±25%) to prevent thundering herd
      const jitter = baseDelay * 0.25 * (Math.random() - 0.5)
      return baseDelay + jitter
    },
    share: true
  })

  const contextValue: NovaWebSocketContextType = {
    connectionStatus: webSocket.connectionStatus,
    isConnected: webSocket.isConnected,
    connectionInfo: webSocket.connectionInfo,
    ping: webSocket.ping,
    connect: webSocket.connect
  }

  // Log connection status changes for debugging
  React.useEffect(() => {
    if (debug) {
      console.log('[Nova WebSocket Provider] Connection status:', webSocket.connectionStatus)
    }
  }, [webSocket.connectionStatus, debug])

  return (
    <NovaWebSocketContext.Provider value={contextValue}>
      {children}
    </NovaWebSocketContext.Provider>
  )
}

// Hook to use the WebSocket context - throws error if used outside provider
export function useNovaWebSocketContext() {
  const context = useContext(NovaWebSocketContext)
  if (!context) {
    throw new Error('useNovaWebSocketContext must be used within a NovaWebSocketProvider')
  }
  return context
}

// Hook to use the WebSocket context - returns null if used outside provider (for optional usage)
export function useOptionalNovaWebSocketContext() {
  return useContext(NovaWebSocketContext)
} 