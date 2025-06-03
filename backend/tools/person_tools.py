"""
Person management LangChain tools.
"""

import json
from typing import List

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import select

from database.database import db_manager
from models.models import Person
from .helpers import find_person_by_email


class CreatePersonParams(BaseModel):
    """Parameters for creating a person."""
    name: str = Field(description="Person's full name")
    email: str = Field(description="Person's email address")
    role: str = Field(None, description="Person's role or job title (optional)")
    description: str = Field(None, description="Description of the person (optional)")
    current_focus: str = Field(None, description="Person's current focus or priority (optional)")


async def create_person_tool(params: CreatePersonParams) -> str:
    """Create a new person."""
    async with db_manager.get_session() as session:
        # Check if person already exists
        existing = await find_person_by_email(session, params.email)
        if existing:
            return f"Error: Person with email '{params.email}' already exists: {existing.name}"
        
        person = Person(
            name=params.name,
            email=params.email,
            role=params.role,
            description=params.description,
            current_focus=params.current_focus
        )
        
        session.add(person)
        await session.commit()
        await session.refresh(person)
        
        return f"Person created successfully: {params.name} ({params.email})"


async def get_persons_tool() -> str:
    """Get all persons."""
    async with db_manager.get_session() as session:
        result = await session.execute(select(Person).order_by(Person.name))
        persons = result.scalars().all()
        
        person_list = []
        for person in persons:
            person_list.append({
                "id": str(person.id),
                "name": person.name,
                "email": person.email,
                "role": person.role,
                "description": person.description,
                "current_focus": person.current_focus
            })
        
        return f"Found {len(person_list)} persons: {json.dumps(person_list, indent=2)}"


def get_person_tools() -> List[StructuredTool]:
    """Get person management LangChain tools."""
    return [
        StructuredTool.from_function(
            func=create_person_tool,
            name="create_person",
            description="Create a new person with contact info and role",
            args_schema=CreatePersonParams,
            coroutine=create_person_tool
        ),
        StructuredTool.from_function(
            func=get_persons_tool,
            name="get_persons",
            description="Get all persons in the system",
            coroutine=get_persons_tool
        ),
    ] 