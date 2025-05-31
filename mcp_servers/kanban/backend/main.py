#!/usr/bin/env python3

import argparse
import logging
from datetime import datetime

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from kanban_service import KanbanService
from mcp_tools import register_mcp_tools
from api_routes import register_api_routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP(name="KanbanTaskManager")

# Global kanban service instance
kanban_service = None

# Health endpoint for server monitoring
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for monitoring server status."""
    return JSONResponse({
        "status": "healthy",
        "service": "kanban-mcp-server", 
        "version": "1.0.0",
        "timestamp": str(datetime.now()),
        "mcp_endpoint": "/mcp/",
        "api_endpoints": "/api/",
        "tasks_dir": str(kanban_service.tasks_dir) if kanban_service else None
    })

def setup_server(tasks_dir: str):
    """Setup the server with all routes and tools"""
    global kanban_service
    
    # Initialize the kanban service
    kanban_service = KanbanService(tasks_dir)
    
    # Register MCP tools (for agent integration)
    register_mcp_tools(mcp, kanban_service)
    
    # Register REST API routes (for frontend integration)
    register_api_routes(mcp, kanban_service)
    
    logger.info("✅ Server setup complete")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Kanban MCP Server')
    parser.add_argument('--tasks-dir', default='./tasks', 
                       help='Directory containing task files (default: ./tasks)')
    parser.add_argument('--port', type=int, default=8002,
                       help='Port to run the server on (default: 8002)')
    
    args = parser.parse_args()
    
    # Setup the server
    setup_server(args.tasks_dir)
    
    logger.info(f"🚀 Starting Kanban MCP Server")
    logger.info(f"📁 Tasks directory: {args.tasks_dir}")
    logger.info(f"🔌 Server port: {args.port}")
    logger.info(f"🌐 MCP endpoint: http://0.0.0.0:{args.port}/mcp/")
    logger.info(f"🔗 REST API: http://0.0.0.0:{args.port}/api/")
    logger.info(f"🏥 Health check: http://0.0.0.0:{args.port}/health")
    
    mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port) 