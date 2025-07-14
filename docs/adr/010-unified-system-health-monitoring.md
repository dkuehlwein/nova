# ADR 010: Unified System Health Monitoring & Status Design

**Status**: Proposed  
**Date**: 2025-07-14  
**Authors**: Development Team  
**Supersedes**: N/A  

## Context

Nova currently has multiple disconnected system status monitoring approaches that create inconsistency, performance issues, and false status indicators. The navbar shows green status when critical services are failing, and there's significant code duplication across status components.

### Current Problems

#### **False Green Status in Navbar**
The navbar shows green even when services are failing because:
1. **Chat agent health is assumed** - just checks endpoint availability, not functionality
2. **Core agent health is superficial** - only verifies health endpoint responds  
3. **MCP server health is limited** - only checks if tools list endpoint works
4. **No real-time monitoring** - status checks are point-in-time snapshots

#### **Multiple Disconnected Status Systems**
Currently we have **4 separate status systems**:
1. **Navbar indicator** (`useSystemHealthSummary` → `/api/system/system-health-summary`)
2. **Settings system status tab** (`useSystemHealthSummary` + custom status fetching)
3. **API key validation status** (cached in database)
4. **MCP server status** (`useMCPServers` → `/api/mcp/servers`)

This creates inconsistency and performance issues.

#### **Code Duplication Issues**
- **`getStatusIcon` function** - duplicated across settings page
- **Status color mapping** - repeated color logic
- **Status text mapping** - repeated text transformations
- **API request patterns** - similar fetch patterns
- **Loading state UI** - repeated loading placeholders

## Decision

We will implement a **Unified System Health Monitoring Architecture** with cached status monitoring, consistent component design, and optimized API key validation.

### **Service Categorization** (Binary Criticality Logic)
- **Core Services**: Chat Agent, Core Agent (any down = critical)
- **Essential Infrastructure**: Database, Redis, llama.cpp, LiteLLM, Neo4j (any down = critical)
- **External Services**: MCP servers, API keys (any down = degraded)

**Rationale**: Without any infrastructure service, agents cannot function:
- No database → No task/user data storage
- No Redis → No pub/sub, caching, or service coordination  
- No llama.cpp → No local AI inference capability
- No LiteLLM → No AI model gateway/routing
- No Neo4j → No agent memory system

### **Status Calculation Logic**
```typescript
// Critical: Any core service OR essential infrastructure down
if (core_services_down.length > 0) return "critical";
if (essential_infrastructure_down.length > 0) return "critical";

// Degraded: Only external services down
if (external_services_down.length > 0) return "degraded";

return "operational";
```

### **API Key Refresh Strategy**
- **Startup**: Check cached status, refresh if never validated
- **API Key Change**: Always refresh immediately when key updated
- **Manual Refresh**: User-triggered "Refresh Status" buttons
- **No Automatic**: Never refresh API keys automatically (saves tokens)

## Architecture

### **Backend: Service Health Caching System**

#### **New Database Model** (`backend/models/system_health.py`)

```python
class SystemHealthStatus(Base):
    """Cached system health status with historical data."""
    __tablename__ = 'system_health_status'
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False)  # "core_agent", "chat_agent", etc.
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "healthy", "degraded", "unhealthy"
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_service_checked_at', 'service_name', 'checked_at'),
        Index('idx_service_latest', 'service_name', 'created_at'),
    )
```

#### **Background Health Check Service** (`backend/services/health_monitor.py`)

```python
class HealthMonitorService:
    """Background service that periodically checks all system health."""
    
    SERVICES = {
        # Core Services (System fails if any of these are down)
        "chat_agent": {
            "type": "core",
            "endpoint": "http://localhost:8000/health",
            "functional_tests": ["create_chat_completion", "tool_calling"]
        },
        "core_agent": {
            "type": "core", 
            "endpoint": "http://localhost:8001/health",
            "functional_tests": ["task_processing", "agent_state"]
        },
        
        # Infrastructure Services (Essential for operation)
        "database": {
            "type": "infrastructure",
            "essential": True,  # Critical infrastructure
            "endpoint": "internal",
            "functional_tests": ["connection_pool", "query_performance"]
        },
        "redis": {
            "type": "infrastructure",
            "essential": True,  # Critical infrastructure
            "endpoint": "internal",
            "functional_tests": ["pub_sub", "caching"]
        },
        "llamacpp": {
            "type": "infrastructure",
            "essential": True,  # Required for local AI inference
            "endpoint": "http://localhost:8080/health", 
            "functional_tests": ["model_loading", "inference_test"]
        },
        "litellm": {
            "type": "infrastructure",
            "essential": True,  # Required for AI model gateway
            "endpoint": "http://localhost:4000/health/readiness",
            "functional_tests": ["gateway_routing", "model_access"]
        },
        "neo4j": {
            "type": "infrastructure", 
            "essential": True,  # Required for agent memory system
            "endpoint": "internal",
            "functional_tests": ["graph_queries", "memory_operations"]
        },
        
        # External Services (Optional, degrades functionality when down)
        "mcp_servers": {
            "type": "external",
            "endpoint": "dynamic",  # Loaded from MCP configuration
            "functional_tests": ["tool_availability", "tool_execution"]
        },
        "google_api": {
            "type": "external",
            "endpoint": "cached",  # Only refresh on startup/change/manual
            "functional_tests": ["api_key_validation"],
            "refresh_triggers": ["startup", "api_key_change", "manual_refresh"]
        },
        "langsmith_api": {
            "type": "external", 
            "endpoint": "cached",  # Only refresh on startup/change/manual
            "functional_tests": ["api_key_validation"],
            "refresh_triggers": ["startup", "api_key_change", "manual_refresh"]
        }
    }
    
    CHECK_INTERVAL = 180  # seconds
    CACHE_TTL = 300       # seconds
    
    async def monitor_all_services(self):
        """Run continuous health monitoring in background."""
        
    async def check_service_health(self, service_name: str, endpoint: str):
        """Check individual service and cache results."""
        
    async def get_cached_status(self, service_name: str, max_age_seconds: int = 60):
        """Get cached status or trigger fresh check if stale."""
        
    async def calculate_overall_status(self) -> str:
        """Calculate overall system status based on service criticality."""
        core_services_down = []
        infrastructure_services_down = []
        external_services_down = []
        
        for service_name, config in self.SERVICES.items():
            status = await self.get_cached_status(service_name)
            
            if status["status"] == "unhealthy":
                if config["type"] == "core":
                    core_services_down.append(service_name)
                elif config["type"] == "infrastructure":
                    infrastructure_services_down.append(service_name)
                elif config["type"] == "external":
                    external_services_down.append(service_name)
        
        # Critical: Any core service down
        if core_services_down:
            return "critical"
        
        # Critical: Essential infrastructure down (database, redis)
        for service_name, config in self.SERVICES.items():
            if (config["type"] == "infrastructure" and 
                config.get("essential", False) and 
                service_name in infrastructure_services_down):
                return "critical"
            
        # Degraded: Any infrastructure service down OR any external service down
        if infrastructure_services_down or external_services_down:
            return "degraded"
            
        return "operational"
```

### **Frontend: Unified Status System**

#### **Single Source of Truth Interface**

```typescript
interface UnifiedSystemStatus {
  overall_status: "operational" | "degraded" | "critical";
  overall_health_percentage: number;
  last_updated: string;
  cached: boolean;
  
  // Service Categories
  core_services: ServiceStatus[];
  infrastructure_services: ServiceStatus[];
  external_services: ServiceStatus[];
  mcp_servers: MCPServerStatus[];
  
  // Quick Summary for Navbar
  summary: {
    total_services: number;
    healthy_services: number;
    degraded_services: number;
    critical_services: number;
    top_issues: string[];  // Most critical problems
  };
}
```

#### **Unified Status Components** (`src/components/status/`)

```typescript
// StatusIndicator.tsx - Universal status display component
export function StatusIndicator({ 
  status, 
  service, 
  responseTime, 
  features, 
  lastCheck,
  showDetails = true,
  size = "md" 
}: StatusIndicatorProps) {
  const theme = getStatusTheme(status);
  const StatusIcon = theme.icon;
  
  return (
    <div className={cn(
      "flex items-center justify-between p-4 rounded-lg border transition-colors",
      theme.bgColor,
      theme.borderColor
    )}>
      <div className="flex items-center space-x-3">
        <StatusIcon className={cn("h-5 w-5", theme.color)} />
        {service && (
          <div>
            <h3 className="font-medium">{service}</h3>
            {showDetails && lastCheck && (
              <p className="text-xs text-muted-foreground">{lastCheck}</p>
            )}
          </div>
        )}
      </div>
      
      {showDetails && (
        <div className="flex items-center space-x-2">
          {responseTime && (
            <Badge variant="outline" className="text-xs">
              {responseTime}ms
            </Badge>
          )}
          {features && features.length > 0 && (
            <Badge variant="secondary" className="text-xs">
              {features.length} features
            </Badge>
          )}
        </div>
      )}
    </div>
  );
}
```

## Implementation Plan

### **Phase 1: Backend Caching Infrastructure** (High Priority)
1. Create `SystemHealthStatus` model
2. Implement `HealthMonitorService` background monitor
3. Update system status API endpoints with caching
4. Add database migration for health status table

### **Phase 2: Frontend UX Improvements** (High Priority) 
1. Redesign system status page layout
2. Implement unified status components
3. Add refresh controls and manual actions
4. Improve mobile responsiveness

### **Phase 3: Code Deduplication** (Medium Priority)
1. Extract shared status utilities and components
2. Replace all duplicated status code with unified components
3. Implement unified status hooks
4. Create shared loading and error states

### **Phase 4: API Key Refresh Optimization** (Medium Priority)
1. Implement smart refresh triggers
2. Add startup/change detection logic
3. Optimize token usage with cached validation

## Expected Benefits

### **Performance**
- **95% fewer API calls** for external service validation
- **Consistent 200ms response times** for status pages
- **Background monitoring** doesn't block user interactions

### **Reliability**
- **Accurate status calculation** based on actual service criticality
- **Historical data** for troubleshooting and trends
- **Proactive monitoring** catches issues faster

### **User Experience**
- **Accurate navbar status** (no more false greens)
- **Instant page loads** (cached data)
- **Clear criticality** (core vs external service failures)
- **80% less duplicate code** across status components

### **Maintainability** 
- **Single source of truth** for all status logic
- **Consistent styling** and behavior everywhere
- **Centralized status theme system**

## Consequences

### **Positive**
- Eliminates false green status indicators in navbar
- Significantly reduces code duplication across status components
- Provides fast, cached status monitoring with accurate criticality logic
- Optimizes API token usage for external service validation
- Creates consistent user experience across all status displays

### **Negative**
- Requires database migration for new health status table
- Initial implementation effort to extract and unify existing components
- Background monitoring service adds slight system complexity

### **Risks**
- Background monitoring could impact system performance if not properly tuned
- Cached status might briefly show stale data during service transitions
- Migration effort required to update all existing status components

## Alternatives Considered

1. **Keep existing separate status systems** - Rejected due to inconsistency and performance issues
2. **Real-time status checks only** - Rejected due to poor performance and expensive API calls
3. **Weighted status calculation** - Rejected in favor of simpler binary criticality logic

This ADR establishes Nova's unified approach to system health monitoring, following the same successful caching pattern implemented for API key validation.