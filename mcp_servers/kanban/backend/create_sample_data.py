#!/usr/bin/env python3

import asyncio
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from kanban_service import KanbanService

async def create_sample_data():
    """Create some sample kanban board data for testing"""
    
    # Initialize the service
    service = KanbanService("./tasks")
    
    print("🎯 Creating sample kanban board data...")
    
    # Create lanes
    lanes = ["Todo", "In Progress", "Review", "Done"]
    for lane in lanes:
        await service.create_lane(lane)
        print(f"✅ Created lane: {lane}")
    
    # Create sample tasks
    sample_tasks = [
        {
            "lane": "Todo", 
            "title": "Setup project structure", 
            "content": "Create the basic project structure with proper directories and files. #project #setup"
        },
        {
            "lane": "Todo", 
            "title": "Implement authentication", 
            "content": "Add user authentication and authorization features. #auth #security"
        },
        {
            "lane": "In Progress", 
            "title": "Build REST API", 
            "content": "Develop the REST API endpoints for the kanban board functionality. #backend #api"
        },
        {
            "lane": "In Progress", 
            "title": "Frontend development", 
            "content": "Create the user interface components for the kanban board. #frontend #ui"
        },
        {
            "lane": "Review", 
            "title": "Code review", 
            "content": "Review the implementation and ensure code quality standards. #review #quality"
        },
        {
            "lane": "Done", 
            "title": "Initial planning", 
            "content": "Complete the initial project planning and requirements gathering. #planning #complete"
        },
        {
            "lane": "Done", 
            "title": "Environment setup", 
            "content": "Set up development environment and tools. #environment #tools #complete"
        }
    ]
    
    for task_data in sample_tasks:
        task = await service.create_task(
            task_data["lane"], 
            task_data["title"], 
            task_data["content"]
        )
        print(f"✅ Created task '{task['title']}' in {task_data['lane']}")
    
    print("\n🎉 Sample data created successfully!")
    print("\n📊 Summary:")
    
    # Show summary
    all_tasks = await service.get_all_tasks()
    lanes_summary = {}
    for task in all_tasks:
        lane = task["lane"]
        if lane not in lanes_summary:
            lanes_summary[lane] = 0
        lanes_summary[lane] += 1
    
    for lane, count in lanes_summary.items():
        print(f"   {lane}: {count} tasks")
    
    print(f"\n📁 Tasks directory: {service.tasks_dir.absolute()}")

if __name__ == "__main__":
    asyncio.run(create_sample_data()) 