"""
Project management LangChain tools.
"""

import json
from typing import List

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import select

from database.database import db_manager
from models.models import Project
from .helpers import find_project_by_name


class CreateProjectParams(BaseModel):
    """Parameters for creating a project."""
    name: str = Field(description="Project name")
    client: str = Field(description="Client name")
    booking_code: str = Field(None, description="Project booking code (optional)")
    summary: str = Field(None, description="Project summary (optional)")


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


def get_project_tools() -> List[StructuredTool]:
    """Get project management LangChain tools."""
    return [
        StructuredTool.from_function(
            func=create_project_tool,
            name="create_project",
            description="Create a new project with client and booking info",
            args_schema=CreateProjectParams,
            coroutine=create_project_tool
        ),
        StructuredTool.from_function(
            func=get_projects_tool,
            name="get_projects",
            description="Get all projects in the system",
            coroutine=get_projects_tool
        ),
    ] 