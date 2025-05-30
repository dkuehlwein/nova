#!/usr/bin/env python3

import logging
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.requests import Request
from kanban_service import KanbanService

logger = logging.getLogger(__name__)

def add_cors_headers(response):
    """Add CORS headers to a response"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

def handle_options_request():
    """Handle CORS preflight requests"""
    response = JSONResponse({})
    return add_cors_headers(response)

def register_api_routes(mcp, kanban_service: KanbanService):
    """Register all REST API routes with the FastMCP instance"""
    
    @mcp.custom_route("/api/title", methods=["GET", "OPTIONS"])
    async def get_title(request: Request):
        """Get the application title"""
        if request.method == "OPTIONS":
            return handle_options_request()
        
        response = PlainTextResponse("Kanban Board")
        return add_cors_headers(response)

    @mcp.custom_route("/api/tags", methods=["GET", "OPTIONS"])
    async def get_tags(request: Request):
        """Get all available tags"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        try:
            tags = await kanban_service.get_all_tags()
            response = JSONResponse({"used": tags, "all": tags})
            return add_cors_headers(response)
        except Exception as e:
            logger.error(f"Error getting tags: {e}")
            response = JSONResponse({"error": str(e)}, status_code=500)
            return add_cors_headers(response)

    @mcp.custom_route("/api/tags/{tag_name}", methods=["PATCH", "OPTIONS"])
    async def update_tag(request: Request):
        """Update tag properties (like color)"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        # For now, just return success - the frontend will handle tag colors client-side
        response = JSONResponse({"success": True})
        return add_cors_headers(response)

    @mcp.custom_route("/api/cards", methods=["GET", "POST", "OPTIONS"])
    async def get_or_create_cards(request: Request):
        """Get all cards/tasks or create a new one"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        if request.method == "GET":
            try:
                tasks = await kanban_service.get_all_tasks()
                response = JSONResponse(tasks)
                return add_cors_headers(response)
            except Exception as e:
                logger.error(f"Error getting cards: {e}")
                response = JSONResponse({"error": str(e)}, status_code=500)
                return add_cors_headers(response)
        
        elif request.method == "POST":
            try:
                data = await request.json()
                lane = data.get("lane", "Todo")
                title = data.get("title", "New Task")
                content = data.get("content", "")
                
                task = await kanban_service.create_task(lane, title, content)
                response = PlainTextResponse(task["id"])
                return add_cors_headers(response)
            except Exception as e:
                logger.error(f"Error creating card: {e}")
                response = JSONResponse({"error": str(e)}, status_code=500)
                return add_cors_headers(response)

    @mcp.custom_route("/api/cards/sort", methods=["PUT", "OPTIONS"])
    async def update_cards_sort(request: Request):
        """Update card sort order"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        try:
            sort_data = await request.json()
            await kanban_service.save_sort_order("cards", sort_data)
            response = JSONResponse({"success": True})
            return add_cors_headers(response)
        except Exception as e:
            logger.error(f"Error updating cards sort: {e}")
            response = JSONResponse({"error": str(e)}, status_code=500)
            return add_cors_headers(response)

    @mcp.custom_route("/api/sort/cards", methods=["GET", "OPTIONS"])
    async def get_cards_sort(request: Request):
        """Get card sort order"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        try:
            sort_order = await kanban_service.get_sort_order("cards")
            response = JSONResponse(sort_order)
            return add_cors_headers(response)
        except Exception as e:
            logger.error(f"Error getting cards sort: {e}")
            response = JSONResponse({}, status_code=500)
            return add_cors_headers(response)

    @mcp.custom_route("/api/lanes", methods=["GET", "POST", "OPTIONS"])
    async def get_or_create_lanes(request: Request):
        """Get all lanes or create a new one"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        if request.method == "GET":
            try:
                lanes = await kanban_service.get_lanes()
                response = JSONResponse(lanes)
                return add_cors_headers(response)
            except Exception as e:
                logger.error(f"Error getting lanes: {e}")
                response = JSONResponse({"error": str(e)}, status_code=500)
                return add_cors_headers(response)
        
        elif request.method == "POST":
            try:
                lane_name = await kanban_service.create_lane()
                response = PlainTextResponse(lane_name)
                return add_cors_headers(response)
            except Exception as e:
                logger.error(f"Error creating lane: {e}")
                response = JSONResponse({"error": str(e)}, status_code=500)
                return add_cors_headers(response)

    @mcp.custom_route("/api/lanes/{lane_name}", methods=["DELETE", "PATCH", "OPTIONS"])
    async def manage_lane(request: Request):
        """Delete or rename a lane"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        lane_name = request.path_params["lane_name"]
        
        if request.method == "DELETE":
            try:
                await kanban_service.delete_lane(lane_name)
                response = JSONResponse({"success": True})
                return add_cors_headers(response)
            except Exception as e:
                logger.error(f"Error deleting lane: {e}")
                response = JSONResponse({"error": str(e)}, status_code=500)
                return add_cors_headers(response)
        
        elif request.method == "PATCH":
            try:
                data = await request.json()
                new_name = data.get("name")
                
                await kanban_service.rename_lane(lane_name, new_name)
                response = JSONResponse({"success": True})
                return add_cors_headers(response)
            except Exception as e:
                logger.error(f"Error renaming lane: {e}")
                response = JSONResponse({"error": str(e)}, status_code=500)
                return add_cors_headers(response)

    @mcp.custom_route("/api/lanes/sort", methods=["PUT", "OPTIONS"])
    async def update_lanes_sort(request: Request):
        """Update lane sort order"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        try:
            sort_data = await request.json()
            await kanban_service.save_sort_order("lanes", sort_data)
            response = JSONResponse({"success": True})
            return add_cors_headers(response)
        except Exception as e:
            logger.error(f"Error updating lanes sort: {e}")
            response = JSONResponse({"error": str(e)}, status_code=500)
            return add_cors_headers(response)

    @mcp.custom_route("/api/sort/lanes", methods=["GET", "OPTIONS"])
    async def get_lanes_sort(request: Request):
        """Get lane sort order"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        try:
            sort_order = await kanban_service.get_sort_order("lanes")
            response = JSONResponse(sort_order)
            return add_cors_headers(response)
        except Exception as e:
            logger.error(f"Error getting lanes sort: {e}")
            response = JSONResponse([], status_code=500)
            return add_cors_headers(response)

    @mcp.custom_route("/api/lanes/{lane_name}/cards/{card_id}", methods=["PUT", "PATCH", "DELETE", "OPTIONS"])
    async def manage_card(request: Request):
        """Update, delete, or modify a card"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        lane_name = request.path_params["lane_name"]
        card_id = request.path_params["card_id"]
        
        if request.method == "PUT":
            try:
                data = await request.json()
                content = data.get("content")
                
                await kanban_service.update_task(card_id, {"content": content, "lane": lane_name})
                response = JSONResponse({"success": True})
                return add_cors_headers(response)
            except Exception as e:
                logger.error(f"Error updating card content: {e}")
                response = JSONResponse({"error": str(e)}, status_code=500)
                return add_cors_headers(response)
        
        elif request.method == "PATCH":
            try:
                data = await request.json()
                
                updates = {"lane": lane_name}
                if "lane" in data:
                    updates["newLane"] = data["lane"]
                if "content" in data:
                    updates["content"] = data["content"]
                
                await kanban_service.update_task(card_id, updates)
                response = JSONResponse({"success": True})
                return add_cors_headers(response)
            except Exception as e:
                logger.error(f"Error updating card: {e}")
                response = JSONResponse({"error": str(e)}, status_code=500)
                return add_cors_headers(response)
        
        elif request.method == "DELETE":
            try:
                await kanban_service.delete_task(card_id, lane_name)
                response = JSONResponse({"success": True})
                return add_cors_headers(response)
            except Exception as e:
                logger.error(f"Error deleting card: {e}")
                response = JSONResponse({"error": str(e)}, status_code=500)
                return add_cors_headers(response)

    @mcp.custom_route("/api/lanes/{lane_name}/cards/{card_id}/rename", methods=["PATCH", "OPTIONS"])
    async def rename_card(request: Request):
        """Rename a card"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        try:
            lane_name = request.path_params["lane_name"]
            card_id = request.path_params["card_id"]
            data = await request.json()
            new_name = data.get("name")
            
            await kanban_service.update_task(card_id, {"name": new_name, "lane": lane_name})
            response = JSONResponse({"success": True})
            return add_cors_headers(response)
        except Exception as e:
            logger.error(f"Error renaming card: {e}")
            response = JSONResponse({"error": str(e)}, status_code=500)
            return add_cors_headers(response)

    @mcp.custom_route("/api/images", methods=["POST", "OPTIONS"])
    async def upload_image(request: Request):
        """Handle image uploads (placeholder)"""
        if request.method == "OPTIONS":
            return handle_options_request()
            
        # For now, just return success - full image support would need file handling
        response = JSONResponse({"message": "Image upload not implemented yet"})
        return add_cors_headers(response) 