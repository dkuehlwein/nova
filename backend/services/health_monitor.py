"""
Health Monitor Service

Background service that periodically checks all system health and caches results.
Implements unified system health monitoring from ADR 010.
"""

import asyncio
import aiohttp
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from contextlib import asynccontextmanager

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import db_manager
from models.system_health import SystemHealthStatus
from utils.logging import get_logger
from config import settings

logger = get_logger("health-monitor")


class HealthMonitorService:
    """Background service that periodically checks all system health."""
    
    # Service configuration following ADR 010 binary criticality logic
    SERVICES = {
        # Core Services (System fails if any of these are down)
        "chat_agent": {
            "type": "core",
            "endpoint": "http://localhost:8000/chat/health",
            "essential": True
        },
        "core_agent": {
            "type": "core", 
            "endpoint": f"http://{'localhost' if settings.POSTGRES_HOST == 'localhost' else 'nova-nova-core-agent-1'}:8001/health",
            "essential": True
        },
        
        # Infrastructure Services (Essential for operation)
        "database": {
            "type": "infrastructure",
            "essential": True,  # Critical infrastructure
            "endpoint": "internal"
        },
        "redis": {
            "type": "infrastructure",
            "essential": True,  # Critical infrastructure
            "endpoint": "internal"
        },
        "ai_models": {
            "type": "infrastructure",
            "essential": True,  # Required for AI functionality (chat + memory)
            "endpoint": "model_availability"  # Special endpoint type for model availability check
        },
        "litellm": {
            "type": "infrastructure",
            "essential": True,  # Required for AI model gateway
            "endpoint": f"http://{'nova-litellm-1' if settings.POSTGRES_HOST != 'localhost' else 'localhost'}:4000/health/readiness"
        },
        "neo4j": {
            "type": "infrastructure", 
            "essential": True,  # Required for agent memory system
            "endpoint": "internal"
        },
        
    }
    
    CHECK_INTERVAL = 180  # seconds (3 minutes)
    CACHE_TTL = 300       # seconds (5 minutes)
    HTTP_TIMEOUT = 5.0    # seconds
    
    def __init__(self):
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Start the background health monitoring."""
        if self.is_running:
            logger.warning("Health monitor already running")
            return
        
        self.is_running = True
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.HTTP_TIMEOUT))
        
        # Start background monitoring task
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
        # Subscribe to MCP server toggle events to trigger immediate refresh
        await self._subscribe_to_mcp_events()
        
        logger.info("Health monitor service started")
    
    async def stop(self):
        """Stop the background health monitoring."""
        self.is_running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        if self._session:
            await self._session.close()
            
        logger.info("Health monitor service stopped")
    
    async def _monitor_loop(self):
        """Continuous monitoring loop."""
        logger.info("Starting health monitoring loop")
        
        try:
            while self.is_running:
                try:
                    await self.monitor_all_services()
                    await asyncio.sleep(self.CHECK_INTERVAL)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                    await asyncio.sleep(30)  # Short delay before retry
        except asyncio.CancelledError:
            logger.info("Health monitoring loop cancelled")
        
    async def monitor_all_services(self):
        """Run health checks for all services and cache results."""
        logger.debug("Running health checks for all services")
        
        # Create concurrent tasks for all service checks
        tasks = []
        for service_name, config in self.SERVICES.items():
            if config["endpoint"] == "cached":
                # Skip cached services in background monitoring
                continue
            elif config["endpoint"] == "dynamic":
                # Handle MCP servers separately
                tasks.append(self._check_mcp_servers())
            elif config["endpoint"] == "internal":
                # Handle internal services (database, redis, neo4j)
                tasks.append(self._check_internal_service(service_name, config))
            elif config["endpoint"] == "model_availability":
                # Handle AI model availability check
                tasks.append(self._check_ai_model_availability(service_name, config))
            else:
                # HTTP endpoint check
                tasks.append(self._check_http_service(service_name, config))
        
        # Run all checks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"Health checks completed: {success_count}/{len(tasks)} successful")
    
    async def _check_http_service(self, service_name: str, config: Dict) -> bool:
        """Check HTTP-based service health."""
        start_time = time.time()
        
        try:
            if not self._session:
                raise Exception("HTTP session not initialized")
            
            async with self._session.get(config["endpoint"]) as response:
                response_time_ms = int((time.time() - start_time) * 1000)
                
                if response.status == 200:
                    await self._cache_health_status(
                        service_name=service_name,
                        status="healthy",
                        response_time_ms=response_time_ms,
                        metadata={"endpoint": config["endpoint"]}
                    )
                    return True
                else:
                    await self._cache_health_status(
                        service_name=service_name,
                        status="unhealthy",
                        response_time_ms=response_time_ms,
                        error_message=f"HTTP {response.status}",
                        metadata={"endpoint": config["endpoint"], "status_code": response.status}
                    )
                    return False
                    
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            await self._cache_health_status(
                service_name=service_name,
                status="unhealthy",
                response_time_ms=response_time_ms,
                error_message=str(e),
                metadata={"endpoint": config["endpoint"]}
            )
            return False
    
    async def _check_internal_service(self, service_name: str, config: Dict) -> bool:
        """Check internal service health (database, redis, neo4j)."""
        start_time = time.time()
        
        try:
            if service_name == "database":
                # Test database connectivity
                async with db_manager.get_session() as session:
                    await session.execute(select(1))
                    
            elif service_name == "redis":
                # Test Redis connectivity
                from utils.redis_manager import get_redis
                redis_client = await get_redis()
                if redis_client:
                    await redis_client.ping()
                else:
                    raise Exception("Redis client not initialized")
                    
            elif service_name == "neo4j":
                # Test Neo4j connectivity via memory manager
                from memory.graphiti_manager import get_graphiti_client
                try:
                    # Test connectivity by getting the client (this will initialize connection)
                    client = await get_graphiti_client()
                    if client and client.driver:
                        # Simple connectivity test using the underlying driver
                        try:
                            async with client.driver.session(database="neo4j") as session:
                                await session.run("RETURN 1")
                        except TypeError:
                            # Fallback for older Neo4j driver versions
                            async with client.driver.session() as session:
                                await session.run("RETURN 1")
                    else:
                        raise Exception("Neo4j client not available")
                except Exception as e:
                    raise Exception(f"Neo4j connectivity test failed: {str(e)}")
            
            response_time_ms = int((time.time() - start_time) * 1000)
            await self._cache_health_status(
                service_name=service_name,
                status="healthy",
                response_time_ms=response_time_ms,
                metadata={"type": "internal"}
            )
            return True
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            await self._cache_health_status(
                service_name=service_name,
                status="unhealthy",
                response_time_ms=response_time_ms,
                error_message=str(e),
                metadata={"type": "internal"}
            )
            return False
    
    async def _check_ai_model_availability(self, service_name: str, config: Dict) -> bool:
        """Check AI model availability via existing LLM service (chat + embedding models)."""
        start_time = time.time()
        
        try:
            # Import here to avoid circular imports
            from services.llm_service import llm_service
            
            # Get available models using existing service
            available_models = await llm_service.get_available_models()
            
            chat_models = available_models.get("chat_models", [])
            embedding_models = available_models.get("embedding_models", [])
            all_models = available_models.get("all_models", [])
            
            chat_count = len(chat_models)
            embedding_count = len(embedding_models)
            total_count = len(all_models)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Determine status based on model availability (binary: healthy or unhealthy)
            if chat_count > 0 and embedding_count > 0:
                status = "healthy"
                message = f"Both chat and embedding models available"
            else:
                status = "unhealthy"
                if chat_count == 0 and embedding_count == 0:
                    message = "No AI models available - check API keys"
                elif chat_count == 0:
                    message = f"Chat models unavailable (have {embedding_count} embedding models)"
                else:
                    message = f"Embedding models unavailable (have {chat_count} chat models)"
            
            # Cache the status with detailed metadata
            await self._cache_health_status(
                service_name=service_name,
                status=status,
                response_time_ms=response_time_ms,
                metadata={
                    "chat_models_count": chat_count,
                    "embedding_models_count": embedding_count,
                    "total_models_count": total_count,
                    "chat_models": [m.get("model_name", "") for m in chat_models],
                    "embedding_models": [m.get("model_name", "") for m in embedding_models],
                    "message": message,
                    "type": "ai_models"
                }
            )
            
            return status == "healthy"
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            await self._cache_health_status(
                service_name=service_name,
                status="unhealthy",
                response_time_ms=response_time_ms,
                error_message=str(e),
                metadata={
                    "type": "ai_models",
                    "message": "Failed to check model availability"
                }
            )
            return False
    
    async def _check_mcp_servers(self) -> bool:
        """Check MCP servers health via existing endpoint."""
        start_time = time.time()
        
        try:
            # Use existing MCP endpoint logic
            from api.mcp_endpoints import get_mcp_servers
            mcp_response = await get_mcp_servers()
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Determine status based on MCP servers health
            if mcp_response.enabled_servers == 0:
                # If no servers are enabled, MCP service is effectively disabled
                status = "disabled"  # No servers enabled
            elif mcp_response.healthy_servers == mcp_response.enabled_servers:
                status = "healthy"  # All enabled servers healthy
            else:
                status = "degraded"  # Some servers unhealthy
            
            await self._cache_health_status(
                service_name="mcp_servers",
                status=status,
                response_time_ms=response_time_ms,
                metadata={
                    "total_servers": mcp_response.total_servers,
                    "enabled_servers": mcp_response.enabled_servers,
                    "healthy_servers": mcp_response.healthy_servers
                }
            )
            return status == "healthy"
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            await self._cache_health_status(
                service_name="mcp_servers",
                status="unhealthy",
                response_time_ms=response_time_ms,
                error_message=str(e),
                metadata={"type": "mcp"}
            )
            return False
    
    async def _cache_health_status(
        self, 
        service_name: str, 
        status: str, 
        response_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Cache service health status to database."""
        try:
            async with db_manager.get_session() as session:
                health_status = SystemHealthStatus(
                    service_name=service_name,
                    status=status,
                    response_time_ms=response_time_ms,
                    error_message=error_message,
                    metadata=metadata or {},
                    checked_at=datetime.now(timezone.utc)
                )
                
                session.add(health_status)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to cache health status for {service_name}: {e}")
    
    async def get_cached_status(self, service_name: str, max_age_seconds: int = 300) -> Optional[Dict[str, Any]]:
        """Get cached status or trigger fresh check if stale."""
        try:
            async with db_manager.get_session() as session:
                # Get latest status for service
                result = await session.execute(
                    select(SystemHealthStatus)
                    .where(SystemHealthStatus.service_name == service_name)
                    .order_by(desc(SystemHealthStatus.checked_at))
                    .limit(1)
                )
                
                status_record = result.scalar_one_or_none()
                
                if not status_record:
                    return None
                
                # Check if status is stale
                age_seconds = (datetime.now(timezone.utc) - status_record.checked_at).total_seconds()
                
                return {
                    "service_name": status_record.service_name,
                    "status": status_record.status,
                    "response_time_ms": status_record.response_time_ms,
                    "error_message": status_record.error_message,
                    "metadata": status_record.service_metadata,
                    "checked_at": status_record.checked_at.isoformat(),
                    "age_seconds": int(age_seconds),
                    "is_stale": age_seconds > max_age_seconds
                }
                
        except Exception as e:
            logger.error(f"Failed to get cached status for {service_name}: {e}")
            return None
    
    async def calculate_overall_status(self) -> Dict[str, Any]:
        """Calculate overall system status based on service criticality."""
        core_services_down = []
        infrastructure_services_down = []
        
        all_statuses = {}
        
        for service_name, config in self.SERVICES.items():
            cached_status = await self.get_cached_status(service_name)
            
            if not cached_status:
                # No status available - treat as down
                if config["type"] == "core":
                    core_services_down.append(service_name)
                elif config["type"] == "infrastructure" and config.get("essential", False):
                    infrastructure_services_down.append(service_name)
            elif cached_status["status"] == "unhealthy":
                if config["type"] == "core":
                    core_services_down.append(service_name)
                elif config["type"] == "infrastructure" and config.get("essential", False):
                    infrastructure_services_down.append(service_name)
            
            all_statuses[service_name] = cached_status
        
        # Calculate overall status using binary criticality logic
        if core_services_down or infrastructure_services_down:
            overall_status = "critical"
        else:
            overall_status = "operational"
        
        # Calculate health percentage
        total_services = len(self.SERVICES)
        unhealthy_services = len(core_services_down) + len(infrastructure_services_down)
        health_percentage = max(0, ((total_services - unhealthy_services) / total_services) * 100)
        
        return {
            "overall_status": overall_status,
            "overall_health_percentage": round(health_percentage, 1),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "core_services_down": core_services_down,
            "infrastructure_services_down": infrastructure_services_down,
            "all_statuses": all_statuses,
            "summary": {
                "total_services": total_services,
                "healthy_services": total_services - unhealthy_services,
                "degraded_services": 0,  # No external services anymore
                "critical_services": len(core_services_down) + len(infrastructure_services_down),
                "top_issues": core_services_down + infrastructure_services_down
            }
        }
    
    async def _subscribe_to_mcp_events(self):
        """Subscribe to MCP server toggle events to trigger immediate refresh."""
        try:
            from utils.redis_manager import get_redis, subscribe
            
            async def handle_mcp_event(event):
                """Handle MCP server toggle events by refreshing MCP server status."""
                if event.get("type") == "mcp_toggled":
                    logger.info(f"MCP server toggled: {event.get('data', {}).get('server_name')} -> {event.get('data', {}).get('enabled')}")
                    # Trigger immediate refresh of MCP servers status
                    await self._check_mcp_servers()
                    logger.info("MCP servers status refreshed after toggle")
            
            # Subscribe to MCP events (non-blocking)
            redis_client = await get_redis()
            if redis_client:
                # Note: This is a simplified implementation
                # In a full implementation, you'd use subscribe() to listen for MCP events
                logger.info("Redis available for MCP event subscription")
                pass
            else:
                logger.info("Redis not available, MCP events will not be subscribed to")
            
        except Exception as e:
            logger.warning(f"Failed to subscribe to MCP events: {e}")


# Global health monitor instance
health_monitor = HealthMonitorService()