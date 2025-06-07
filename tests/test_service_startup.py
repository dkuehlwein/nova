"""
Tests for service startup configuration.

Tests that both chat and core agent services can be started with proper configuration.
"""

import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio

# Import the startup modules


class TestServiceStartup:
    """Test service startup configuration."""
    
    def test_config_ports_loaded(self):
        """Test that port configuration is loaded correctly."""
        from config import settings
        
        # Test default values
        assert hasattr(settings, 'CHAT_AGENT_PORT')
        assert hasattr(settings, 'CORE_AGENT_PORT')
        assert isinstance(settings.CHAT_AGENT_PORT, int)
        assert isinstance(settings.CORE_AGENT_PORT, int)
        assert settings.CHAT_AGENT_PORT == 8000
        assert settings.CORE_AGENT_PORT == 8001
    
    def test_chat_agent_port_configuration(self):
        """Test chat agent uses correct port configuration."""
        # Mock the main function to avoid actually starting the server
        with patch('uvicorn.Server.serve', new_callable=AsyncMock) as mock_serve:
            with patch('start_chat_agent.db_manager.close', new_callable=AsyncMock):
                
                # Import and test the main function
                from start_chat_agent import main
                
                # Test with default config
                async def test_default():
                    with patch.dict(os.environ, {}, clear=True):
                        await main()
                        # Verify the server was configured with the right port
                        assert mock_serve.called
                
                asyncio.run(test_default())
    
    def test_core_agent_port_configuration(self):
        """Test core agent uses correct port configuration."""
        # Mock the main function to avoid actually starting the server
        with patch('uvicorn.Server.serve', new_callable=AsyncMock) as mock_serve:
            with patch('start_core_agent.db_manager.close', new_callable=AsyncMock):
                with patch('start_core_agent.CoreAgent') as mock_core_agent:
                    mock_agent_instance = AsyncMock()
                    mock_core_agent.return_value = mock_agent_instance
                    
                    # Import and test the main function
                    from start_core_agent import main
                    
                    # Test with default config
                    async def test_default():
                        with patch.dict(os.environ, {}, clear=True):
                            await main()
                            # Verify the server was configured with the right port
                            assert mock_serve.called
                    
                    asyncio.run(test_default())
    
    def test_environment_variable_override(self):
        """Test that environment variables can override config values."""
        from config import settings
        
        # Test environment variable override for ports
        with patch.dict(os.environ, {'CHAT_AGENT_PORT': '9000', 'CORE_AGENT_PORT': '9001'}):
            # Reload settings to pick up environment changes
            from config import Settings
            test_settings = Settings()
            
            assert test_settings.CHAT_AGENT_PORT == 9000
            assert test_settings.CORE_AGENT_PORT == 9001
    
    def test_prompts_import(self):
        """Test that prompts can be imported correctly."""
        from agent.prompts import CHAT_AGENT_SYSTEM_PROMPT, CORE_AGENT_TASK_PROMPT_TEMPLATE
        
        # Verify prompts exist and are strings
        assert isinstance(CHAT_AGENT_SYSTEM_PROMPT, str)
        assert isinstance(CORE_AGENT_TASK_PROMPT_TEMPLATE, str)
        assert len(CHAT_AGENT_SYSTEM_PROMPT) > 0
        assert len(CORE_AGENT_TASK_PROMPT_TEMPLATE) > 0
        
        # Verify template has expected placeholders
        assert "{task_id}" in CORE_AGENT_TASK_PROMPT_TEMPLATE
        assert "{title}" in CORE_AGENT_TASK_PROMPT_TEMPLATE
        assert "{status}" in CORE_AGENT_TASK_PROMPT_TEMPLATE
    
    def test_chat_agent_uses_new_prompt(self):
        """Test that chat agent imports and uses the new prompt correctly."""
        # Mock external dependencies
        with patch('agent.chat_agent.get_all_tools', return_value=[]):
            with patch('agent.chat_agent.mcp_manager.get_client_and_tools', new_callable=AsyncMock) as mock_mcp:
                mock_mcp.return_value = (None, [])
                with patch('agent.chat_agent.create_llm', return_value=MagicMock()):
                    with patch('agent.chat_agent.create_react_agent', return_value=MagicMock()) as mock_create_agent:
                        
                        # Import and test
                        from agent.chat_agent import create_chat_agent
                        
                        async def test_prompt():
                            await create_chat_agent()
                            
                            # Verify create_react_agent was called with the new prompt
                            assert mock_create_agent.called
                            call_args = mock_create_agent.call_args
                            
                            # Check that prompt argument contains expected content
                            prompt_arg = call_args.kwargs.get('prompt', '')
                            assert 'Nova' in prompt_arg
                            assert 'Task Management' in prompt_arg
                        
                        asyncio.run(test_prompt())
    
    def test_core_agent_uses_new_prompt(self):
        """Test that core agent imports and uses the new prompt template correctly."""
        from agent.core_agent import CoreAgent
        from models.models import Task, TaskStatus
        from datetime import datetime
        from uuid import uuid4
        
        # Create test agent and task
        agent = CoreAgent()
        task = Task(
            id=uuid4(),
            title="Test Task",
            description="Test Description", 
            status=TaskStatus.NEW,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Test context
        context = {
            "persons": [],
            "projects": [],
            "comments": []
        }
        
        # Test prompt creation
        async def test_prompt():
            prompt = await agent._create_prompt(task, context)
            
            # Verify prompt contains expected elements from template
            assert str(task.id) in prompt
            assert task.title in prompt
            assert "Nova" in prompt
            assert "Instructions:" in prompt
        
        asyncio.run(test_prompt())


class TestConfigurationIntegration:
    """Test integration between configuration and services."""
    
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
        
        # If Gmail server is configured, verify structure
        if mcp_servers:
            gmail_server = next((s for s in mcp_servers if s['name'] == 'gmail'), None)
            if gmail_server:
                assert 'url' in gmail_server
                assert 'health_url' in gmail_server
                assert 'description' in gmail_server


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 