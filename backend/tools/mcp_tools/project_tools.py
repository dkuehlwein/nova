"""
Project management MCP tools.
"""

import json
from typing import List

from fastmcp.tools import Tool
from sqlalchemy import select

from database import db_manager
from models import Project
from .helpers import find_project_by_name
from .schemas import CreateProjectParams


async def create_project_tool(params: CreateProjectParams) -> str:
    """Create a new project."""
    async with db_manager.get_session() as session:
        # Check if project already exists
        existing = await find_project_by_name(session, params.name)
        if existing:
            return f"Error: Project with name '{params.name}' already exists"
        
        project = Project(
            name=params.name,
            client=params.client,
            booking_code=params.booking_code,
            summary=params.summary
        )
        
        session.add(project)
        await session.commit()
        await session.refresh(project)
        
        return f"Project created successfully: {params.name} for {params.client}"


async def get_projects_tool() -> str:
    """Get all projects."""
    async with db_manager.get_session() as session:
        result = await session.execute(select(Project).order_by(Project.name))
        projects = result.scalars().all()
        
        project_list = []
        for project in projects:
            project_list.append({
                "id": str(project.id),
                "name": project.name,
                "client": project.client,
                "booking_code": project.booking_code,
                "summary": project.summary
            })
        
        return f"Found {len(project_list)} projects: {json.dumps(project_list, indent=2)}"


def get_project_tools() -> List[Tool]:
    """Get project management MCP tools."""
    return [
        Tool(
            name="create_project",
            description="Create a new project with client and booking info",
            func=create_project_tool,
            args_schema=CreateProjectParams
        ),
        Tool(
            name="get_projects",
            description="Get all projects in the system",
            func=get_projects_tool,
            args_schema=None
        ),
    ] 