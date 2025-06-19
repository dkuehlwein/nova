'use client'

import { QueryClientProvider } from '@tanstack/react-query'
import { getQueryClient } from '../lib/queryClient'

export function NovaQueryClientProvider({ children }: { children: React.ReactNode }) {
  // This gets the query client and only runs on client side
  const queryClient = getQueryClient()

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
} 