#!/usr/bin/env python3

import json
import logging
from typing import List
from kanban_service import KanbanService

logger = logging.getLogger(__name__)

def register_mcp_tools(mcp, kanban_service: KanbanService):
    """Register all MCP tools with the FastMCP instance"""
    
    @mcp.tool()
    async def list_lanes() -> str:
        """Get all available lanes (columns) in the kanban board"""
        try:
            lanes = await kanban_service.get_lanes()
            return json.dumps({"lanes": lanes}, indent=2)
        except Exception as e:
            return f"Error listing lanes: {str(e)}"

    @mcp.tool()
    async def list_all_tasks() -> str:
        """Get all tasks from all lanes in the kanban board"""
        try:
            tasks = await kanban_service.get_all_tasks()
            return json.dumps(tasks, indent=2)
        except Exception as e:
            return f"Error listing tasks: {str(e)}"

    @mcp.tool()
    async def get_lane_tasks(lane: str) -> str:
        """Get all tasks from a specific lane
        
        Args:
            lane: Name of the lane to get tasks from
        """
        try:
            tasks = await kanban_service.get_tasks_from_lane(lane)
            return json.dumps({"lane": lane, "tasks": tasks}, indent=2)
        except Exception as e:
            return f"Error getting tasks from lane {lane}: {str(e)}"

    @mcp.tool()
    async def add_task(title: str, lane: str, content: str = "", tags: List[str] = None) -> str:
        """Add a new task to a kanban board lane
        
        Args:
            title: Title of the new task
            lane: Lane to add the task to (e.g., Backlog, Todo, In Progress, Done)
            content: Optional content/description for the task
            tags: Optional list of tags for the task
        """
        try:
            logger.info(f"add_task called with: title={title}, lane={lane}, content={content}, tags={tags}")
            
            # Add tags to content if provided
            task_content = content
            if tags:
                tag_string = " ".join(f"#{tag}" for tag in tags)
                task_content = f"{content}\n\n{tag_string}" if content else tag_string
            
            task = await kanban_service.create_task(lane, title, task_content)
            
            return f"Task added successfully to {lane} lane:\n{json.dumps(task, indent=2)}"
        except Exception as e:
            logger.error(f"Error in add_task: {e}")
            return f"Error adding task: {str(e)}"

    @mcp.tool()
    async def get_task(task_id: str, lane: str = None) -> str:
        """Get details of a specific task by ID
        
        Args:
            task_id: Unique identifier of the task
            lane: Optional lane name to search in (searches all lanes if not provided)
        """
        try:
            task = await kanban_service.get_task(task_id, lane)
            return json.dumps(task, indent=2)
        except Exception as e:
            return f"Error getting task {task_id}: {str(e)}"

    @mcp.tool()
    async def update_task(task_id: str, content: str = None, new_lane: str = None, lane: str = None) -> str:
        """Update an existing task's content or move it to a different lane
        
        Args:
            task_id: Unique identifier of the task
            content: New content for the task (optional)
            new_lane: New lane to move the task to (optional)
            lane: Current lane of the task (optional, will search all lanes if not provided)
        """
        try:
            updates = {}
            if content is not None:
                updates['content'] = content
            if new_lane is not None:
                updates['newLane'] = new_lane
            if lane is not None:
                updates['lane'] = lane
            
            task = await kanban_service.update_task(task_id, updates)
            return f"Task updated successfully:\n{json.dumps(task, indent=2)}"
        except Exception as e:
            return f"Error updating task {task_id}: {str(e)}"

    @mcp.tool()
    async def delete_task(task_id: str, lane: str = None) -> str:
        """Delete a task from the kanban board
        
        Args:
            task_id: Unique identifier of the task
            lane: Optional lane name to search in (searches all lanes if not provided)
        """
        try:
            result = await kanban_service.delete_task(task_id, lane)
            return f"Task deleted successfully: {json.dumps(result, indent=2)}"
        except Exception as e:
            return f"Error deleting task {task_id}: {str(e)}"

    @mcp.tool()
    async def move_task(task_id: str, from_lane: str, to_lane: str) -> str:
        """Move a task between lanes
        
        Args:
            task_id: Unique identifier of the task
            from_lane: Source lane name
            to_lane: Destination lane name
        """
        try:
            result = await kanban_service.move_task(task_id, from_lane, to_lane)
            return f"Task moved successfully: {json.dumps(result, indent=2)}"
        except Exception as e:
            return f"Error moving task {task_id}: {str(e)}"

    @mcp.tool()
    async def create_lane(lane_name: str) -> str:
        """Create a new lane in the kanban board
        
        Args:
            lane_name: Name of the new lane to create
        """
        try:
            result = await kanban_service.create_lane(lane_name)
            return f"Lane created successfully: {json.dumps({'id': result}, indent=2)}"
        except Exception as e:
            return f"Error creating lane {lane_name}: {str(e)}"

    @mcp.tool()
    async def delete_lane(lane_name: str) -> str:
        """Delete a lane and all its tasks from the kanban board
        
        Args:
            lane_name: Name of the lane to delete
        """
        try:
            result = await kanban_service.delete_lane(lane_name)
            return f"Lane deleted successfully: {json.dumps(result, indent=2)}"
        except Exception as e:
            return f"Error deleting lane {lane_name}: {str(e)}" 