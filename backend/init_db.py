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
from models.models import Task, TaskStatus, Chat, Artifact, AgentStatus, AgentStatusEnum

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
        
        # Create sample tasks with memory-based person/project references
        tasks = [
            Task(
                id=uuid4(),
                title="Complete Backend API",
                description="Implement all REST endpoints for the kanban board",
                status=TaskStatus.DONE,
                created_at=datetime.now(timezone.utc),
                tags=["backend", "api"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                id=uuid4(),
                title="Fix Database Integration",
                description="Resolve database connection and table creation issues",
                status=TaskStatus.IN_PROGRESS,
                created_at=datetime.now(timezone.utc),
                tags=["database", "integration"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                id=uuid4(),
                title="Implement Frontend UI",
                description="Build React components for the kanban board interface",
                status=TaskStatus.NEEDS_REVIEW,
                created_at=datetime.now(timezone.utc),
                tags=["frontend", "ui"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                id=uuid4(),
                title="Set Up Testing Framework",
                description="Configure pytest and write unit tests for all components",
                status=TaskStatus.NEW,
                created_at=datetime.now(timezone.utc),
                tags=["testing", "quality"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                id=uuid4(),
                title="Document API Endpoints",
                description="Create comprehensive API documentation using FastAPI docs",
                status=TaskStatus.NEW,
                created_at=datetime.now(timezone.utc),
                tags=["documentation", "api"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                id=uuid4(),
                title="User Authentication",
                description="Implement user login and session management",
                status=TaskStatus.USER_INPUT_RECEIVED,
                created_at=datetime.now(timezone.utc),
                tags=["auth", "security"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                id=uuid4(),
                title="Deploy to Production",
                description="Set up production environment and deployment pipeline",
                status=TaskStatus.WAITING,
                created_at=datetime.now(timezone.utc),
                tags=["deployment", "production"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            )
        ]
        
        session.add_all(tasks)
        await session.commit()
        logger.info(f"Added {len(tasks)} sample tasks")
        
        # Create initial agent status record
        agent_status = AgentStatus(
            id=uuid4(),
            status=AgentStatusEnum.IDLE,
            created_at=datetime.now(timezone.utc)
        )
        
        session.add(agent_status)
        await session.commit()
        logger.info("Added initial agent status record")


if __name__ == "__main__":
    asyncio.run(init_database()) 