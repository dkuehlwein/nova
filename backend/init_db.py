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
    """Add minimal required data for system startup."""
    async with db_manager.get_session() as session:
        # Note: No sample tasks added - keeping the database clean
        
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