#!/usr/bin/env python3
"""
Database initialization script for Nova Kanban.

This script creates all tables and populates them with sample data for development.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from database.database import db_manager
from models.models import Person, Project, Task, TaskStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """Initialize database with tables and sample data."""
    try:
        logger.info("Creating database tables...")
        await db_manager.create_tables()
        logger.info("✅ Database tables created successfully")
        
        logger.info("Adding sample data...")
        await add_sample_data()
        logger.info("✅ Sample data added successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    finally:
        await db_manager.close()


async def add_sample_data():
    """Add sample data for development and testing."""
    async with db_manager.get_session() as session:
        # Create sample persons first
        nova_ai_id = uuid4()
        daniel_id = uuid4()
        
        nova_ai = Person(
            id=nova_ai_id,
            name="Nova AI",
            email="nova@ai.assistant",
            role="AI Assistant"
        )
        
        daniel = Person(
            id=daniel_id,
            name="Daniel",
            email="daniel@nova.dev",
            role="Product Manager"
        )
        
        session.add_all([nova_ai, daniel])
        await session.commit()
        logger.info(f"Added 2 sample persons")
        
        # Create sample project
        project_id = uuid4()
        kanban_project = Project(
            id=project_id,
            name="Nova Kanban System",
            client="Internal",
            summary="Complete task management system for Nova AI Assistant"
        )
        
        session.add(kanban_project)
        await session.commit()
        logger.info(f"Added 1 sample project")
        
        # Create sample tasks without many-to-many relationships for now
        tasks = [
            Task(
                id=uuid4(),
                title="Complete Backend API",
                description="Implement all REST endpoints for the kanban board",
                status=TaskStatus.DONE,
                created_at=datetime.now(timezone.utc),
                tags=["backend", "api"]
            ),
            Task(
                id=uuid4(),
                title="Fix Database Integration",
                description="Resolve database connection and table creation issues",
                status=TaskStatus.IN_PROGRESS,
                created_at=datetime.now(timezone.utc),
                tags=["database", "integration"]
            ),
            Task(
                id=uuid4(),
                title="Implement Frontend UI",
                description="Build React components for the kanban board interface",
                status=TaskStatus.NEEDS_REVIEW,
                created_at=datetime.now(timezone.utc),
                tags=["frontend", "ui"]
            ),
            Task(
                id=uuid4(),
                title="Set Up Testing Framework",
                description="Configure pytest and write unit tests for all components",
                status=TaskStatus.NEW,
                created_at=datetime.now(timezone.utc),
                tags=["testing", "quality"]
            ),
            Task(
                id=uuid4(),
                title="Document API Endpoints",
                description="Create comprehensive API documentation using FastAPI docs",
                status=TaskStatus.NEW,
                created_at=datetime.now(timezone.utc),
                tags=["documentation", "api"]
            ),
            Task(
                id=uuid4(),
                title="User Authentication",
                description="Implement user login and session management",
                status=TaskStatus.USER_INPUT_RECEIVED,
                created_at=datetime.now(timezone.utc),
                tags=["auth", "security"]
            ),
            Task(
                id=uuid4(),
                title="Deploy to Production",
                description="Set up production environment and deployment pipeline",
                status=TaskStatus.WAITING,
                created_at=datetime.now(timezone.utc),
                tags=["deployment", "production"]
            )
        ]
        
        session.add_all(tasks)
        await session.commit()
        
        logger.info(f"Added {len(tasks)} sample tasks")


if __name__ == "__main__":
    asyncio.run(init_database()) 