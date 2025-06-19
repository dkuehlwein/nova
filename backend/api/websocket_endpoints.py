"""
WebSocket endpoints for Nova's real-time system.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, Query
from fastapi.responses import JSONResponse

from utils.websocket_manager import websocket_manager, handle_websocket_connection
from utils.logging import get_logger

logger = get_logger("websocket_endpoints")

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = Query(None)):
    """
    Main WebSocket endpoint for real-time communication.
    
    Clients can connect to receive real-time events from the Nova system.
    Events include:
    - MCP server toggles
    - System prompt updates  
    - Task status changes
    - System health updates
    - Configuration validation results
    
    The connection will receive periodic ping messages to keep the connection alive.
    
    Args:
        websocket: The WebSocket connection
        client_id: Optional client identifier for tracking connections
    """
    await handle_websocket_connection(websocket, client_id)


@router.get("/connections")
async def get_websocket_connections():
    """Get information about active WebSocket connections."""
    return {
        "active_connections": websocket_manager.get_connection_count(),
        "client_ids": list(websocket_manager.get_client_ids()),
        "client_metadata": websocket_manager.get_all_client_metadata()
    }


@router.post("/broadcast")  
async def broadcast_test_message(message: dict):
    """
    Broadcast a test message to all connected WebSocket clients.
    
    This endpoint is primarily for testing and debugging purposes.
    
    Args:
        message: The message to broadcast to all clients
    """
    try:
        await websocket_manager.broadcast(message)
        return {
            "success": True,
            "message": "Broadcast sent successfully",
            "recipients": websocket_manager.get_connection_count()
        }
    except Exception as e:
        logger.error(f"Failed to broadcast test message: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )


@router.post("/ping")
async def ping_all_clients():
    """Send a ping message to all connected WebSocket clients."""
    try:
        await websocket_manager.send_ping_to_all()
        return {
            "success": True,
            "message": "Ping sent to all clients",
            "recipients": websocket_manager.get_connection_count()
        }
    except Exception as e:
        logger.error(f"Failed to ping clients: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )


@router.get("/metrics")
async def get_websocket_metrics():
    """Get WebSocket connection metrics."""
    client_metadata = websocket_manager.get_all_client_metadata()
    
    total_messages_sent = sum(
        metadata.get("messages_sent", 0) 
        for metadata in client_metadata.values()
    )
    
    # Calculate average connection time
    current_time = asyncio.get_event_loop().time()
    connection_times = [
        current_time - metadata.get("connected_at", current_time)
        for metadata in client_metadata.values()
    ]
    avg_connection_time = sum(connection_times) / len(connection_times) if connection_times else 0
    
    return {
        "active_connections": websocket_manager.get_connection_count(),
        "total_messages_sent": total_messages_sent,
        "average_connection_time_seconds": avg_connection_time,
        "clients": [
            {
                "client_id": client_id,
                "connected_at": metadata.get("connected_at"),
                "messages_sent": metadata.get("messages_sent", 0),
                "connection_duration": current_time - metadata.get("connected_at", current_time)
            }
            for client_id, metadata in client_metadata.items()
        ]
    } 