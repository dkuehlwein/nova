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


class UserSettingsService:
    """Centralized service for all user settings operations."""
    
    @staticmethod
    async def get_user_settings(session: AsyncSession = None):
        """Get user settings object from database.
        
        Args:
            session: Optional database session. If not provided, creates a new one.
        """
        from models.user_settings import UserSettings
        from sqlalchemy import select
        
        if session:
            # Use provided session
            result = await session.execute(select(UserSettings).limit(1))
            return result.scalar_one_or_none()
        else:
            # Create new session
            async with db_manager.get_session() as new_session:
                result = await new_session.execute(select(UserSettings).limit(1))
                return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_settings_dict() -> dict:
        """Get user settings from database as a dictionary with all fields."""
        settings = await UserSettingsService.get_user_settings()
        if not settings:
            return {}
        
        return {
            "id": str(settings.id),
            "created_at": settings.created_at,
            "updated_at": settings.updated_at,
            "onboarding_complete": settings.onboarding_complete,
            "full_name": settings.full_name,
            "email": settings.email,
            "timezone": settings.timezone,
            "notes": settings.notes,
            "email_polling_enabled": settings.email_polling_enabled,
            "email_polling_interval": settings.email_polling_interval,
            "email_create_tasks": settings.email_create_tasks,
            "email_max_per_fetch": settings.email_max_per_fetch,
            "email_label_filter": settings.email_label_filter,
            "notification_preferences": settings.notification_preferences,
            "task_defaults": settings.task_defaults,
            "agent_polling_interval": settings.agent_polling_interval,
            "agent_error_retry_interval": settings.agent_error_retry_interval,
            "memory_search_limit": settings.memory_search_limit,
            "memory_token_limit": settings.memory_token_limit,
            "mcp_server_preferences": settings.mcp_server_preferences,
            "llm_model": settings.llm_model,
            "llm_provider": settings.llm_provider,
            "llm_temperature": settings.llm_temperature,
            "llm_max_tokens": settings.llm_max_tokens,
        }
    
    @staticmethod
    async def get_llm_settings() -> dict:
        """Get only LLM-related settings from database."""
        settings = await UserSettingsService.get_user_settings()
        if not settings:
            return {}
        
        return {
            "llm_model": settings.llm_model,
            "llm_provider": settings.llm_provider,
            "llm_temperature": settings.llm_temperature,
            "llm_max_tokens": settings.llm_max_tokens,
        }
    
    @staticmethod
    async def get_email_settings() -> dict:
        """Get only email-related settings from database."""
        settings = await UserSettingsService.get_user_settings()
        if not settings:
            return {}
        
        return {
            "email_polling_enabled": settings.email_polling_enabled,
            "email_polling_interval": settings.email_polling_interval,
            "email_create_tasks": settings.email_create_tasks,
            "email_max_per_fetch": settings.email_max_per_fetch,
            "email_label_filter": settings.email_label_filter,
        }
    
    @staticmethod
    async def get_memory_settings() -> dict:
        """Get only memory-related settings from database."""
        settings = await UserSettingsService.get_user_settings()
        if not settings:
            return {}
        
        return {
            "memory_search_limit": settings.memory_search_limit,
            "memory_token_limit": settings.memory_token_limit,
        }
    
    @staticmethod
    def get_user_settings_sync():
        """Get user settings object from database synchronously."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we need to use a new event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, UserSettingsService.get_user_settings())
                    return future.result()
            else:
                return asyncio.run(UserSettingsService.get_user_settings())
        except Exception as e:
            print(f"Warning: Could not get user settings, using None: {e}")
            return None
    
    @staticmethod
    def get_llm_settings_sync() -> dict:
        """Get LLM settings from database synchronously."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we need to use a new event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, UserSettingsService.get_llm_settings())
                    return future.result()
            else:
                return asyncio.run(UserSettingsService.get_llm_settings())
        except Exception as e:
            print(f"Warning: Could not get user settings, using defaults: {e}")
            return {}
    
    @staticmethod
    def get_memory_settings_sync() -> dict:
        """Get memory settings from database synchronously."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we need to use a new event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, UserSettingsService.get_memory_settings())
                    return future.result()
            else:
                return asyncio.run(UserSettingsService.get_memory_settings())
        except Exception as e:
            print(f"Warning: Could not get memory settings, using defaults: {e}")
            return {"memory_search_limit": 10, "memory_token_limit": 32000}  # Database defaults


# Global user settings service instance
user_settings_service = UserSettingsService()



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