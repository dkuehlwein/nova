"""
Service Startup & Configuration Tests

Tests that both Nova service entry points (start_website.py and start_core_agent.py) 
use correct configuration values without actually starting servers or touching external resources.

This replaces the old tests/test_service_startup.py with updated logic that follows
Nova's testing conventions and avoids duplicating coverage from other test suites.
"""

import asyncio
import os
from datetime import datetime
from uuid import uuid4
from importlib import reload
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_pg_pool():
    """Mock PostgreSQL connection pool for tests."""
    mock_pool = AsyncMock()
    mock_pool.acquire = AsyncMock()
    mock_pool.release = AsyncMock()
    return mock_pool


def _make_dummy_server() -> MagicMock:
    """Return a dummy uvicorn server instance with an async serve method."""
    dummy_server = MagicMock(name="DummyUvicornServer")
    dummy_server.serve = AsyncMock(name="serve")
    return dummy_server


class TestSettings:
    """Basic settings sanity checks unique to this file."""

    def test_default_ports_are_loaded(self):
        """Test that default port configuration is loaded correctly."""
        from config import settings
        
        assert settings.CHAT_AGENT_PORT == 8000
        assert settings.CORE_AGENT_PORT == 8001

    def test_environment_variable_override(self, monkeypatch):
        """Test that environment variables can override config values."""
        monkeypatch.setenv("CHAT_AGENT_PORT", "9000")
        monkeypatch.setenv("CORE_AGENT_PORT", "9001")

        from config import Settings
        
        new_settings = Settings()
        assert new_settings.CHAT_AGENT_PORT == 9000
        assert new_settings.CORE_AGENT_PORT == 9001


class TestChatServiceStartup:
    """Test that start_website.py uses correct port configuration."""

    @pytest.mark.asyncio
    async def test_chat_agent_port_configuration(self):
        """Test chat agent uses correct port configuration."""
        with patch("uvicorn.Server", autospec=True) as mock_server_cls:
            mock_server_cls.return_value = _make_dummy_server()

            # Import after patching so the patched Server is used
            module = reload(__import__("start_website", fromlist=["main"]))

            # Run main (which awaits server.serve)
            await module.main()

            # Verify the server was configured with the right port
            passed_config = mock_server_cls.call_args.args[0]
            assert passed_config.port == 8000


class TestCoreServiceStartup:
    """Test that start_core_agent.py uses correct port configuration."""

    @pytest.mark.asyncio
    async def test_core_agent_port_configuration(self):
        """Test core agent uses correct port configuration."""
        with patch("uvicorn.Server", autospec=True) as mock_server_cls, \
             patch("start_core_agent.CoreAgent", autospec=True):
            
            mock_server_cls.return_value = _make_dummy_server()

            module = reload(__import__("start_core_agent", fromlist=["main"]))
            await module.main()

            passed_config = mock_server_cls.call_args.args[0]
            assert passed_config.port == 8001


class TestPromptIntegration:
    """Test that key prompt constants are importable and used by core agent."""

    def test_prompt_constants_exist(self):
        """Test that prompts can be imported correctly."""
        from agent.prompts import get_nova_system_prompt, TASK_CONTEXT_TEMPLATE, CURRENT_TASK_TEMPLATE
        
        # Get the system prompt (now dynamically loaded)
        system_prompt = get_nova_system_prompt()
        
        # Verify prompts exist and are strings
        assert isinstance(system_prompt, str)
        assert isinstance(TASK_CONTEXT_TEMPLATE, str)
        assert isinstance(CURRENT_TASK_TEMPLATE, str)
        assert len(system_prompt) > 0
        assert len(TASK_CONTEXT_TEMPLATE) > 0
        assert len(CURRENT_TASK_TEMPLATE) > 0
        
        # Verify templates have expected placeholders
        assert "{status}" in TASK_CONTEXT_TEMPLATE
        assert "{title}" in CURRENT_TASK_TEMPLATE
        assert "{description}" in CURRENT_TASK_TEMPLATE

    @pytest.mark.asyncio
    async def test_core_agent_creates_expected_task_messages(self, mock_pg_pool):
        """Test that core agent creates task messages with expected content."""
        # Mock AIMessage so we don't need langchain-core
        with patch("langchain_core.messages.AIMessage") as mock_ai_message:
            
            def _build_fake_message(content: str, **_):
                fake = MagicMock()
                fake.content = content
                return fake
            
            mock_ai_message.side_effect = _build_fake_message

            from agent.core_agent import CoreAgent
            from models.models import Task, TaskStatus

            # Create test task (SQLAlchemy instance in memory)
            task = Task(
                id=uuid4(),
                title="Test Task",
                description="Do something important",
                status=TaskStatus.NEW,
            )
            task.created_at = datetime.utcnow()
            task.updated_at = datetime.utcnow()

            context = {"memory_context": [], "comments": []}

            # Test the private method that creates task messages with required pg_pool
            agent = CoreAgent(pg_pool=mock_pg_pool)
            messages = await agent._create_task_messages(task, context)

            assert len(messages) == 2
            combined = "".join(m.content for m in messages)
            # Check that the expected current task template content is present
            assert "Current Task" in combined or "Test Task" in combined
            assert task.title in combined
            assert task.description in combined


class TestConfigurationIntegration:
    """Test configuration integration that isn't covered elsewhere."""

    def test_database_url_construction(self):
        """Test that DATABASE_URL is constructed properly."""
        from config import settings
        
        assert settings.DATABASE_URL is not None
        assert 'postgresql://' in settings.DATABASE_URL
        assert settings.POSTGRES_USER in settings.DATABASE_URL
        assert settings.POSTGRES_DB in settings.DATABASE_URL

    def test_mcp_server_configuration(self):
        """Test MCP server configuration."""
        from config import settings
        
        # Test MCP servers property
        mcp_servers = settings.MCP_SERVERS
        assert isinstance(mcp_servers, list)
        
        # If servers are configured, verify structure
        if mcp_servers:
            server = mcp_servers[0]
            assert 'url' in server
            assert 'description' in server


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 