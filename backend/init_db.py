#!/usr/bin/env python3
"""
Database initialization script for Nova Kanban.

This script creates all tables and populates them with sample data for development.
Updated to work with the current system architecture including graphiti memory.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from database.database import db_manager
from models.models import Task, TaskStatus, Chat, Artifact, AgentStatus, AgentStatusEnum
from models.user_settings import UserSettings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
        
        logger.info("✅ Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await db_manager.close()


async def add_sample_data():
    """Add sample data for development and testing."""
    async with db_manager.get_session() as session:
        
        # Create sample tasks with memory-based person/project references
        tasks = [
            Task(
                title="Complete Backend API",
                description="Implement all REST endpoints for the kanban board",
                status=TaskStatus.DONE,
                tags=["backend", "api"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                title="Fix Database Integration", 
                description="Resolve database connection and table creation issues",
                status=TaskStatus.IN_PROGRESS,
                tags=["database", "integration"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                title="Implement Frontend UI",
                description="Build React components for the kanban board interface",
                status=TaskStatus.NEEDS_REVIEW,
                tags=["frontend", "ui"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                title="Set Up Testing Framework",
                description="Configure pytest and write unit tests for all components",
                status=TaskStatus.NEW,
                tags=["testing", "quality"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                title="Document API Endpoints",
                description="Create comprehensive API documentation using FastAPI docs",
                status=TaskStatus.NEW,
                tags=["documentation", "api"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                title="User Authentication",
                description="Implement user login and session management",
                status=TaskStatus.USER_INPUT_RECEIVED,
                tags=["auth", "security"],
                person_emails=["daniel@nova.dev"],
                project_names=["Nova Kanban System"]
            ),
            Task(
                title="Deploy to Production",
                description="Set up production environment and deployment pipeline",
                status=TaskStatus.WAITING,
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
            status=AgentStatusEnum.IDLE
        )
        
        session.add(agent_status)
        await session.commit()
        logger.info("Added initial agent status record")
        
        # Create default user settings if they don't exist
        from sqlalchemy import select
        result = await session.execute(select(UserSettings).limit(1))
        existing_settings = result.scalar_one_or_none()
        
        if not existing_settings:
            user_settings = UserSettings(
                full_name="Nova User",
                email="user@nova.dev",
                timezone="UTC",
                notes="Default user settings created during database initialization"
            )
            session.add(user_settings)
            await session.commit()
            logger.info("Added default user settings")


if __name__ == "__main__":
    asyncio.run(init_database()) 