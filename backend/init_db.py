#!/usr/bin/env python3
"""
Database initialization script for Nova Kanban.

This script creates all tables and populates them with sample data for development.
Updated to work with the current system architecture including graphiti memory.
"""

import asyncio

from database.database import db_manager, UserSettingsService
from models.models import AgentStatus, AgentStatusEnum
from models.user_settings import UserSettings
from sqlalchemy import select

# Import all model modules to ensure tables are registered with Base.metadata
from models import system_health  # noqa: F401 - Required for table creation

from utils.logging import configure_logging, get_logger

configure_logging(service_name="nova-init-db")
logger = get_logger(__name__)


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
        logger.error("Database initialization failed", extra={"data": {"error": str(e)}})
        logger.exception("Database initialization failed with full traceback")
        raise
    finally:
        await db_manager.close()


async def add_sample_data():
    """Add minimal required data for system startup."""
    async with db_manager.get_session() as session:
        await _ensure_agent_status_exists(session)
        await _ensure_user_settings_exist(session)


async def _ensure_agent_status_exists(session):
    """Create initial agent status record if it doesn't exist."""
    result = await session.execute(select(AgentStatus))
    existing_status = result.scalar_one_or_none()
    
    if not existing_status:
        agent_status = AgentStatus(status=AgentStatusEnum.IDLE)
        session.add(agent_status)
        await session.commit()
        logger.info("Added initial agent status record")
    else:
        logger.info("Agent status record already exists, skipping creation")


async def _ensure_user_settings_exist(session):
    """Create default user settings if they don't exist."""
    existing_settings = await UserSettingsService.get_user_settings(session)
    
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