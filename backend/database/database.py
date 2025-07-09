"""
Database configuration and session management for Nova Kanban MCP.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from models.models import Base
from config import settings


async def get_user_settings_dict() -> dict:
    """Get user settings from database as a dictionary."""
    from models.user_settings import UserSettings
    from sqlalchemy import select
    
    async with db_manager.get_session() as session:
        result = await session.execute(select(UserSettings).limit(1))
        settings = result.scalar_one_or_none()
        if settings:
            return {
                "llm_model": settings.llm_model,
                "llm_provider": settings.llm_provider,
                "llm_temperature": settings.llm_temperature,
                "llm_max_tokens": settings.llm_max_tokens,
            }
        return {}


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, database_url: str = None):
        if database_url is None:
            # Use the SQLAlchemy-specific URL with +asyncpg driver
            database_url = settings.SQLALCHEMY_DATABASE_URL
        
        self.engine = create_async_engine(
            database_url,
            poolclass=NullPool,  # For development simplicity
            echo=bool(os.getenv("SQL_DEBUG", "false").lower() == "true")
        )
        
        self.async_session_maker = async_sessionmaker(
            self.engine, 
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def create_tables(self):
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self):
        """Drop all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session."""
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close database connections."""
        await self.engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


# FastAPI dependency for database sessions
async def get_db_session():
    """Dependency to get database session for FastAPI endpoints."""
    async with db_manager.get_session() as session:
        yield session 