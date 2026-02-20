"""
WebSocket manager for Nova's real-time system.
Handles WebSocket connections and broadcasting events to connected clients.
"""

import asyncio
import json
from typing import Dict, Set
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from models.events import NovaEvent, WebSocketMessage
from utils.logging import get_logger

logger = get_logger("websocket_manager")


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events to clients."""
    
    def __init__(self):
        # Store active connections with client IDs
        self.active_connections: Dict[str, WebSocket] = {}
        # Store client metadata
        self.client_metadata: Dict[str, Dict] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str = None) -> str:
        """
        Connect a new WebSocket client.
        
        Args:
            websocket: The WebSocket connection
            client_id: Optional client ID, will generate one if not provided
            
        Returns:
            str: The client ID for this connection
        """
        if client_id is None:
            client_id = str(uuid4())
        
        await websocket.accept()
        
        async with self._lock:
            self.active_connections[client_id] = websocket
            self.client_metadata[client_id] = {
                "connected_at": asyncio.get_event_loop().time(),
                "messages_sent": 0
            }
        
        logger.info(
            f"WebSocket client connected: {client_id}",
            extra={
                "data": {
                    "client_id": client_id,
                    "total_connections": len(self.active_connections)
                }
            }
        )
        
        return client_id
    
    async def disconnect(self, client_id: str):
        """Disconnect a WebSocket client."""
        async with self._lock:
            self._disconnect_internal(client_id)
        
        logger.info(
            f"WebSocket client disconnected: {client_id}",
            extra={
                "data": {
                    "client_id": client_id,
                    "total_connections": len(self.active_connections)
                }
            }
        )
    
    def _disconnect_internal(self, client_id: str):
        """Internal disconnect method that doesn't acquire the lock."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.client_metadata:
            del self.client_metadata[client_id]
    
    async def send_personal_message(self, message: dict, client_id: str):
        """Send a message to a specific client."""
        async with self._lock:
            if client_id in self.active_connections:
                websocket = self.active_connections[client_id]
                try:
                    await websocket.send_text(json.dumps(message))
                    self.client_metadata[client_id]["messages_sent"] += 1
                    
                    logger.debug(
                        f"Sent personal message to client: {client_id}",
                        extra={
                            "data": {
                                "client_id": client_id,
                                "message_type": message.get("type", "unknown")
                            }
                        }
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send message to client {client_id}",
                        exc_info=True,
                        extra={
                            "data": {
                                "client_id": client_id,
                                "error": str(e)
                            }
                        }
                    )
                    # Remove dead connection (already inside lock)
                    self._disconnect_internal(client_id)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            logger.debug("No active WebSocket connections for broadcast")
            return
        
        async with self._lock:
            # Create a copy of the connections dict to avoid modification during iteration
            connections = self.active_connections.copy()
        
        # Keep track of failed connections to remove them
        failed_connections = []
        successful_broadcasts = 0
        
        for client_id, websocket in connections.items():
            try:
                await websocket.send_text(json.dumps(message))
                async with self._lock:
                    if client_id in self.client_metadata:
                        self.client_metadata[client_id]["messages_sent"] += 1
                successful_broadcasts += 1
                
            except Exception as e:
                logger.warning(
                    f"Failed to broadcast to client {client_id}: {e}",
                    extra={
                        "data": {
                            "client_id": client_id,
                            "error": str(e)
                        }
                    }
                )
                failed_connections.append(client_id)
        
        # Remove failed connections
        for client_id in failed_connections:
            await self.disconnect(client_id)
        
        logger.info(
            f"Broadcast message to {successful_broadcasts} clients",
            extra={
                "data": {
                    "message_type": message.get("type", "unknown"),
                    "successful_broadcasts": successful_broadcasts,
                    "failed_connections": len(failed_connections),
                    "total_connections": len(self.active_connections)
                }
            }
        )
    
    async def broadcast_event(self, event: NovaEvent):
        """Broadcast a NovaEvent to all connected clients."""
        try:
            # Convert NovaEvent to WebSocket message format
            ws_message = WebSocketMessage.from_nova_event(event)
            await self.broadcast(ws_message.model_dump())
            
            logger.debug(
                f"Broadcast event: {event.type}",
                extra={
                    "data": {
                        "event_id": event.id,
                        "event_type": event.type,
                        "source": event.source
                    }
                }
            )
            
        except ValidationError as e:
            logger.error(
                f"Failed to convert event to WebSocket message: {event.id}",
                exc_info=True,
                extra={
                    "data": {
                        "event_id": event.id,
                        "event_type": event.type,
                        "error": str(e)
                    }
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to broadcast event: {event.id}",
                exc_info=True,
                extra={
                    "data": {
                        "event_id": event.id,
                        "event_type": event.type,
                        "error": str(e)
                    }
                }
            )
    
    async def send_ping(self, client_id: str):
        """Send a ping message to a specific client."""
        ping_message = {
            "type": "ping",
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.send_personal_message(ping_message, client_id)
    
    async def send_ping_to_all(self):
        """Send ping messages to all connected clients."""
        ping_message = {
            "type": "ping",
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast(ping_message)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)
    
    def get_client_ids(self) -> Set[str]:
        """Get all active client IDs."""
        return set(self.active_connections.keys())
    
    def get_client_metadata(self, client_id: str) -> Dict:
        """Get metadata for a specific client."""
        return self.client_metadata.get(client_id, {})
    
    def get_all_client_metadata(self) -> Dict[str, Dict]:
        """Get metadata for all clients."""
        return self.client_metadata.copy()


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


async def handle_websocket_connection(websocket: WebSocket, client_id: str = None):
    """
    Handle a WebSocket connection lifecycle.
    
    Args:
        websocket: The WebSocket connection
        client_id: Optional client ID
    """
    actual_client_id = await websocket_manager.connect(websocket, client_id)
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            
            # Parse incoming message
            try:
                message = json.loads(data)
                logger.debug(
                    f"Received message from client {actual_client_id}",
                    extra={
                        "data": {
                            "client_id": actual_client_id,
                            "message_type": message.get("type", "unknown")
                        }
                    }
                )
                
                # Handle different message types
                if message.get("type") == "pong":
                    # Client responded to ping
                    logger.debug("Received pong from client", extra={"data": {"actual_client_id": str(actual_client_id)}})
                elif message.get("type") == "subscribe":
                    # Client wants to subscribe to specific events
                    # This could be extended to support selective event filtering
                    logger.info("Client subscribed to events", extra={"data": {"actual_client_id": str(actual_client_id)}})
                
            except json.JSONDecodeError:
                logger.warning(
                    f"Invalid JSON from client {actual_client_id}: {data}",
                    extra={
                        "data": {
                            "client_id": actual_client_id,
                            "raw_data": data[:100]  # First 100 chars
                        }
                    }
                )
                
    except WebSocketDisconnect:
        logger.info("Client disconnected normally", extra={"data": {"actual_client_id": str(actual_client_id)}})
    except Exception as e:
        logger.error(
            f"Error in WebSocket connection for client {actual_client_id}",
            exc_info=True,
            extra={
                "data": {
                    "client_id": actual_client_id,
                    "error": str(e)
                }
            }
        )
    finally:
        await websocket_manager.disconnect(actual_client_id) 