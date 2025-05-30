#!/usr/bin/env python3

import os
import uuid
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class KanbanService:
    """Core kanban task management functionality"""
    
    def __init__(self, tasks_dir: str = "./tasks"):
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.sort_file = self.tasks_dir / "sort_config.json"
        logger.info(f"Initialized KanbanService with tasks directory: {self.tasks_dir}")
    
    async def get_lanes(self) -> List[str]:
        """Get all available lanes (directories) in the kanban board"""
        try:
            lanes = []
            for item in self.tasks_dir.iterdir():
                if item.is_dir():
                    lanes.append(item.name)
            return sorted(lanes)
        except Exception as e:
            logger.error(f"Error getting lanes: {e}")
            return []
    
    def _extract_title_from_filename(self, filename: str) -> str:
        """Extract title from filename by removing UUID suffix"""
        name_without_ext = filename.replace('.md', '')
        
        # Use regex to find and remove UUID pattern
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        uuid_match = re.search(uuid_pattern, name_without_ext)
        
        if uuid_match:
            # Remove the UUID and the separator dash before it
            title_part = name_without_ext.replace(f'-{uuid_match.group(0)}', '')
            # Clean up the title
            if not title_part or title_part == '-' or title_part == '':
                return 'Untitled'
            # Convert dashes back to spaces and clean up
            return re.sub(r'^-+', '', re.sub(r'-+$', '', title_part.replace('-', ' ')))
        
        # Legacy format (UUID only) or unrecognized format
        return name_without_ext or 'Untitled'
    
    def _extract_uuid_from_filename(self, filename: str) -> str:
        """Extract UUID from filename"""
        name_without_ext = filename.replace('.md', '')
        
        # Use regex to find UUID pattern
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        uuid_match = re.search(uuid_pattern, name_without_ext)
        
        if uuid_match:
            return uuid_match.group(0)
        
        # Legacy format - assume whole filename is UUID
        return name_without_ext
    
    def _sanitize_title_for_filename(self, title: str) -> str:
        """Sanitize title for use in filename"""
        return re.sub(r'^-+|-+$', '', re.sub(r'-+', '-', title.replace(' ', '-')))
    
    def _create_task_filename(self, title: str, task_id: str) -> str:
        """Create filename with title and UUID"""
        sanitized_title = self._sanitize_title_for_filename(title)
        return f"{sanitized_title}-{task_id}.md"
    
    def _get_tags_from_content(self, content: str) -> List[str]:
        """Extract hashtags from content"""
        tags = re.findall(r'#[a-zA-Z0-9_]+', content)
        return [tag[1:] for tag in tags]  # Remove the # prefix
    
    async def get_tasks_from_lane(self, lane_name: str) -> List[Dict[str, Any]]:
        """Get all tasks from a specific lane"""
        try:
            lane_dir = self.tasks_dir / lane_name
            if not lane_dir.exists():
                return []
            
            tasks = []
            for file_path in lane_dir.glob("*.md"):
                content = file_path.read_text(encoding='utf-8')
                task_id = self._extract_uuid_from_filename(file_path.name)
                title = self._extract_title_from_filename(file_path.name)
                
                task = {
                    "id": task_id,
                    "name": title,  # Frontend expects 'name' field
                    "title": title,
                    "lane": lane_name,
                    "content": content,
                    "tags": self._get_tags_from_content(content),
                    "filePath": str(file_path)
                }
                tasks.append(task)
            
            return tasks
        except Exception as e:
            logger.error(f"Error getting tasks from lane {lane_name}: {e}")
            raise Exception(f"Failed to get tasks from lane {lane_name}: {str(e)}")
    
    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks across all lanes"""
        try:
            lanes = await self.get_lanes()
            all_tasks = []
            
            for lane in lanes:
                tasks = await self.get_tasks_from_lane(lane)
                all_tasks.extend(tasks)
            
            return all_tasks
        except Exception as e:
            logger.error(f"Error getting all tasks: {e}")
            raise Exception(f"Failed to get all tasks: {str(e)}")
    
    async def create_task(self, lane_name: str, title: str = None, content: str = "") -> Dict[str, Any]:
        """Create a new task in the specified lane"""
        try:
            # Default title if not provided
            if not title:
                title = "New Task"
                
            logger.info(f"Creating task: lane={lane_name}, title={title}, content={content}")
            
            # Ensure lane directory exists
            lane_dir = self.tasks_dir / lane_name
            lane_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique task ID
            task_id = str(uuid.uuid4())
            
            # Create filename with title and UUID
            filename = self._create_task_filename(title, task_id)
            file_path = lane_dir / filename
            
            # Write task content
            file_path.write_text(content, encoding='utf-8')
            
            result = {
                "id": task_id,
                "name": title,  # Frontend expects 'name' field
                "lane": lane_name,
                "title": title,
                "content": content,
                "tags": self._get_tags_from_content(content),
                "path": str(file_path),
                "filename": filename
            }
            
            logger.info(f"Task created successfully: {result}")
            return result
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            raise Exception(f"Failed to create task in lane {lane_name}: {str(e)}")
    
    async def _find_task_file(self, task_id: str, lane: Optional[str] = None) -> Optional[Path]:
        """Find a task file by UUID, optionally in a specific lane"""
        try:
            if lane:
                # Search in specific lane
                lane_dir = self.tasks_dir / lane
                if lane_dir.exists():
                    for file_path in lane_dir.glob("*.md"):
                        if file_path.name.endswith(f"-{task_id}.md"):
                            return file_path
            else:
                # Search across all lanes
                for lane_dir in self.tasks_dir.iterdir():
                    if lane_dir.is_dir():
                        for file_path in lane_dir.glob("*.md"):
                            if file_path.name.endswith(f"-{task_id}.md"):
                                return file_path
            return None
        except Exception as e:
            logger.error(f"Error finding task file: {e}")
            return None
    
    async def get_task(self, task_id: str, lane: Optional[str] = None) -> Dict[str, Any]:
        """Get a specific task by ID"""
        try:
            task_path = await self._find_task_file(task_id, lane)
            if not task_path:
                raise Exception(f"Task {task_id} not found")
            
            content = task_path.read_text(encoding='utf-8')
            title = self._extract_title_from_filename(task_path.name)
            actual_lane = task_path.parent.name
            
            return {
                "id": task_id,
                "name": title,  # Frontend expects 'name' field
                "title": title,
                "lane": actual_lane,
                "content": content,
                "tags": self._get_tags_from_content(content),
                "path": str(task_path)
            }
        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            raise Exception(f"Failed to get task {task_id}: {str(e)}")
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing task"""
        try:
            lane = updates.get('lane')
            content = updates.get('content')
            new_lane = updates.get('newLane')
            new_name = updates.get('name')
            
            # Find the current task file
            current_path = await self._find_task_file(task_id, lane)
            if not current_path:
                raise Exception(f"Task {task_id} not found")
            
            current_lane = current_path.parent.name
            
            # Update content if provided
            if content is not None:
                current_path.write_text(content, encoding='utf-8')
            
            # Rename task if new name provided
            if new_name:
                # Create new filename with new title
                new_filename = self._create_task_filename(new_name, task_id)
                new_path = current_path.parent / new_filename
                current_path.rename(new_path)
                current_path = new_path
            
            # Move to new lane if specified
            if new_lane and new_lane != current_lane:
                new_lane_dir = self.tasks_dir / new_lane
                new_lane_dir.mkdir(parents=True, exist_ok=True)
                
                filename = current_path.name
                new_path = new_lane_dir / filename
                current_path.rename(new_path)
                current_path = new_path
                current_lane = new_lane
            
            # Read final content and return updated task
            final_content = current_path.read_text(encoding='utf-8')
            title = self._extract_title_from_filename(current_path.name)
            
            return {
                "id": task_id,
                "name": title,  # Frontend expects 'name' field
                "title": title,
                "lane": current_lane,
                "content": final_content,
                "tags": self._get_tags_from_content(final_content),
                "path": str(current_path)
            }
        except Exception as e:
            logger.error(f"Error updating task {task_id}: {e}")
            raise Exception(f"Failed to update task {task_id}: {str(e)}")
    
    async def delete_task(self, task_id: str, lane: Optional[str] = None) -> Dict[str, Any]:
        """Delete a task"""
        try:
            task_path = await self._find_task_file(task_id, lane)
            if not task_path:
                raise Exception(f"Task {task_id} not found")
            
            task_path.unlink()
            return {"success": True, "id": task_id}
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            raise Exception(f"Failed to delete task {task_id}: {str(e)}")
    
    async def move_task(self, task_id: str, from_lane: str, to_lane: str) -> Dict[str, Any]:
        """Move a task between lanes"""
        try:
            # Find task in source lane
            task_path = await self._find_task_file(task_id, from_lane)
            if not task_path:
                raise Exception(f"Task {task_id} not found in lane {from_lane}")
            
            # Ensure destination lane exists
            to_lane_dir = self.tasks_dir / to_lane
            to_lane_dir.mkdir(parents=True, exist_ok=True)
            
            # Move the file
            filename = task_path.name
            new_path = to_lane_dir / filename
            task_path.rename(new_path)
            
            return {
                "success": True,
                "id": task_id,
                "fromLane": from_lane,
                "toLane": to_lane
            }
        except Exception as e:
            logger.error(f"Error moving task {task_id}: {e}")
            raise Exception(f"Failed to move task {task_id} from {from_lane} to {to_lane}: {str(e)}")
    
    async def create_lane(self, lane_name: str = None) -> str:
        """Create a new lane"""
        try:
            if not lane_name:
                # Generate default lane name
                existing_lanes = await self.get_lanes()
                counter = 1
                while f"New Lane {counter}" in existing_lanes:
                    counter += 1
                lane_name = f"New Lane {counter}"
                
            lane_dir = self.tasks_dir / lane_name
            lane_dir.mkdir(parents=True, exist_ok=True)
            
            return lane_name
        except Exception as e:
            logger.error(f"Error creating lane {lane_name}: {e}")
            raise Exception(f"Failed to create lane {lane_name}: {str(e)}")
    
    async def delete_lane(self, lane_name: str) -> Dict[str, Any]:
        """Delete a lane and all its tasks"""
        try:
            lane_dir = self.tasks_dir / lane_name
            if lane_dir.exists():
                # Remove directory and all its contents
                import shutil
                shutil.rmtree(lane_dir)
            
            return {"success": True, "id": lane_name}
        except Exception as e:
            logger.error(f"Error deleting lane {lane_name}: {e}")
            raise Exception(f"Failed to delete lane {lane_name}: {str(e)}")
    
    async def rename_lane(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """Rename a lane"""
        try:
            old_dir = self.tasks_dir / old_name
            new_dir = self.tasks_dir / new_name
            
            if not old_dir.exists():
                raise Exception(f"Lane {old_name} does not exist")
            
            if new_dir.exists():
                raise Exception(f"Lane {new_name} already exists")
            
            old_dir.rename(new_dir)
            return {"success": True, "oldName": old_name, "newName": new_name}
        except Exception as e:
            logger.error(f"Error renaming lane {old_name} to {new_name}: {e}")
            raise Exception(f"Failed to rename lane {old_name} to {new_name}: {str(e)}")
    
    async def get_all_tags(self) -> List[Dict[str, Any]]:
        """Get all unique tags from all tasks"""
        try:
            all_tasks = await self.get_all_tasks()
            tag_counts = {}
            
            for task in all_tasks:
                for tag in task.get('tags', []):
                    if tag in tag_counts:
                        tag_counts[tag] += 1
                    else:
                        tag_counts[tag] = 1
            
            # Return tags in the format the frontend expects
            tags = []
            for tag_name, count in tag_counts.items():
                tags.append({
                    "name": tag_name,
                    "count": count,
                    "backgroundColor": f"var(--color-alt-{(hash(tag_name) % 7) + 1})"
                })
            
            return tags
        except Exception as e:
            logger.error(f"Error getting tags: {e}")
            return []
    
    async def save_sort_order(self, sort_type: str, order: Any):
        """Save sort order to file"""
        try:
            sort_data = {}
            if self.sort_file.exists():
                sort_data = json.loads(self.sort_file.read_text())
            
            sort_data[sort_type] = order
            self.sort_file.write_text(json.dumps(sort_data, indent=2))
        except Exception as e:
            logger.error(f"Error saving sort order: {e}")
    
    async def get_sort_order(self, sort_type: str) -> Any:
        """Get sort order from file"""
        try:
            if not self.sort_file.exists():
                return []
            
            sort_data = json.loads(self.sort_file.read_text())
            return sort_data.get(sort_type, [])
        except Exception as e:
            logger.error(f"Error getting sort order: {e}")
            return [] 