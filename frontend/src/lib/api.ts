// API Configuration for Nova Frontend
// Handles different environments including WSL2 development

/**
 * Get the current WSL2 IP dynamically (if possible)
 */
function getWSL2IPRanges(): string[] {
  // Common WSL2 IP ranges based on typical configurations
  const commonRanges = [
    '172.29.172.59', // Current known IP
    '172.20.16.1',
    '172.29.0.1', 
    '172.20.0.1',
    '172.21.0.1',
    '172.22.0.1',
    '172.23.0.1',
    '172.24.0.1',
    '172.25.0.1',
    '172.26.0.1',
    '172.27.0.1',
    '172.28.0.1',
    '172.29.0.1',
    '172.30.0.1',
  ];
  
  return commonRanges.map(ip => `http://${ip}:8000`);
}

/**
 * Try to detect the WSL2 backend IP by attempting connections
 */
async function detectBackendUrl(): Promise<string> {
  const candidateUrls = [
    'http://localhost:8000',  // Standard localhost
    'http://127.0.0.1:8000',  // Explicit localhost
    ...getWSL2IPRanges(),     // Dynamic WSL2 IP ranges
  ];

  // If we have an environment variable, use that first
  if (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) {
    console.log(`🔧 Using configured API URL: ${process.env.NEXT_PUBLIC_API_URL}`);
    return process.env.NEXT_PUBLIC_API_URL;
  }

  console.log('🔍 Auto-detecting backend URL...');

  // Try each URL to see which one responds
  for (const url of candidateUrls) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 1500); // 1.5 second timeout
      
      const response = await fetch(`${url}/health`, {
        method: 'GET',
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        console.log(`✅ Backend detected at: ${url}`);
        return url;
      }
    } catch {
      // URL didn't work, try next one
      continue;
    }
  }

  // If all else fails, provide helpful guidance
  console.warn('⚠️ Could not auto-detect backend URL');
  console.log('');
  console.log('🔧 To fix this issue:');
  console.log('');
  console.log('1. For WSL2 users:');
  console.log('   - Find your WSL2 IP: hostname -I');
  console.log('   - Create frontend/.env.local with:');
  console.log('     NEXT_PUBLIC_API_URL=http://YOUR_WSL2_IP:8000');
  console.log('');
  console.log('2. Check if backend is running:');
  console.log('   - Backend should be running on port 8000');
  console.log('   - Test: curl http://localhost:8000/health');
  console.log('');
  console.log('3. Verify CORS configuration:');
  console.log('   - Backend should allow your frontend origin');
  console.log('');
  
  // Default to localhost as last resort
  return 'http://localhost:8000';
}

/**
 * Get the API base URL based on environment
 */
let cachedApiUrl: string | null = null;

async function getApiBaseUrl(): Promise<string> {
  if (cachedApiUrl) {
    return cachedApiUrl;
  }

  cachedApiUrl = await detectBackendUrl();
  return cachedApiUrl;
}

/**
 * Synchronous version for immediate use (uses cached value or default)
 */
export function getApiBaseUrlSync(): string {
  // Check environment variable first
  if (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }

  // Use cached value if available
  if (cachedApiUrl) {
    return cachedApiUrl;
  }

  // Default fallback
  return 'http://localhost:8000';
}

export const API_BASE_URL = getApiBaseUrlSync();

/**
 * Initialize the API configuration (call this on app startup)
 */
export async function initializeApiConfig(): Promise<string> {
  const url = await getApiBaseUrl();
  console.log(`🚀 Nova Frontend initialized with API: ${url}`);
  return url;
}

/**
 * Make an API request with proper error handling and auto-retry
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  let baseUrl = cachedApiUrl || getApiBaseUrlSync();
  let url = `${baseUrl}${endpoint}`;
  
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    // Only try to detect backend URL if we truly haven't cached one yet
    // and this isn't a health check endpoint (to prevent loops)
    if (!cachedApiUrl && !endpoint.includes('/health')) {
      console.log('🔄 API request failed, attempting one-time backend URL detection...');
      try {
        baseUrl = await detectBackendUrl();
        url = `${baseUrl}${endpoint}`;
        
        // Single retry with detected URL
        const response = await fetch(url, {
          headers: {
            'Content-Type': 'application/json',
            ...options.headers,
          },
          ...options,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
      } catch (retryError) {
        console.error(`API request failed for ${endpoint} (after retry):`, retryError);
        throw retryError;
      }
    }
    
    // Don't log errors for health checks to reduce noise
    if (!endpoint.includes('/health')) {
      console.error(`API request failed for ${endpoint}:`, error);
    }
    throw error;
  }
}

/**
 * Common API endpoints
 */
export const API_ENDPOINTS = {
  overview: '/api/overview',
  pendingDecisions: '/api/pending-decisions',
  tasksByStatus: '/api/tasks/by-status',
  tasks: '/api/tasks',
  taskById: (id: string) => `/api/tasks/${id}`,
  taskComments: (id: string) => `/api/tasks/${id}/comments`,
  health: '/health',
  // Chat endpoints
  chat: '/chat',
  chatStream: '/chat/stream',
  chatHealth: '/chat/health',
  chatTools: '/chat/tools',
  chatTest: '/chat/test',
  // Chat management endpoints
  chats: '/api/chats',
  chatById: (id: string) => `/api/chats/${id}`,
  chatMessages: (id: string) => `/api/chats/${id}/messages`,
  createChat: '/api/chats',
  addChatMessage: (id: string) => `/api/chats/${id}/messages`,
} as const; 