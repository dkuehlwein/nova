"""
Tests for configuration loader with hot-reload capabilities.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from backend.utils.config_loader import ConfigLoader, load_mcp_yaml, save_mcp_yaml


@pytest.fixture
def temp_config_file():
    """Create a temporary configuration file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config = {
            "test_server": {
                "url": "http://localhost:8000/mcp",
                "health_url": "http://localhost:8000/health",
                "description": "Test MCP Server",
                "enabled": True
            }
        }
        yaml.safe_dump(config, f)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


def test_config_loader_init(temp_config_file):
    """Test ConfigLoader initialization and basic loading."""
    loader = ConfigLoader(temp_config_file)
    config = loader.get_config()
    
    assert "test_server" in config
    assert config["test_server"]["enabled"] is True
    assert config["test_server"]["url"] == "http://localhost:8000/mcp"


def test_config_loader_missing_file():
    """Test ConfigLoader behavior with missing file."""
    non_existent_path = Path("/tmp/non_existent_config.yaml")
    loader = ConfigLoader(non_existent_path)
    config = loader.get_config()
    
    assert config == {}


def test_config_loader_invalid_yaml():
    """Test ConfigLoader behavior with invalid YAML."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("invalid: yaml: content: [\n")  # Invalid YAML
        temp_path = Path(f.name)
    
    try:
        loader = ConfigLoader(temp_path)
        config = loader.get_config()
        assert config == {}  # Should return empty dict on parse error
    finally:
        temp_path.unlink()


def test_config_loader_save():
    """Test saving configuration to file."""
    with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
        temp_path = Path(f.name)
    
    try:
        loader = ConfigLoader(temp_path)
        
        new_config = {
            "new_server": {
                "url": "http://localhost:9000/mcp",
                "health_url": "http://localhost:9000/health",
                "description": "New Test Server",
                "enabled": False
            }
        }
        
        loader.save_config(new_config)
        
        # Verify it was saved and loaded correctly
        config = loader.get_config()
        assert config == new_config
        
        # Verify file contents
        with open(temp_path, 'r') as f:
            file_config = yaml.safe_load(f)
        assert file_config == new_config
        
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_config_loader_reload(temp_config_file):
    """Test manual config reload."""
    loader = ConfigLoader(temp_config_file)
    initial_config = loader.get_config()
    initial_timestamp = loader.get_load_timestamp()
    
    # Modify the file
    time.sleep(0.1)  # Ensure timestamp difference
    new_config = {
        "modified_server": {
            "url": "http://localhost:8001/mcp",
            "health_url": "http://localhost:8001/health",
            "description": "Modified Server",
            "enabled": True
        }
    }
    
    with open(temp_config_file, 'w') as f:
        yaml.safe_dump(new_config, f)
    
    # Manually reload
    loader.reload_config()
    
    updated_config = loader.get_config()
    updated_timestamp = loader.get_load_timestamp()
    
    assert updated_config != initial_config
    assert "modified_server" in updated_config
    assert updated_timestamp > initial_timestamp


def test_config_loader_watching(temp_config_file):
    """Test file watching functionality."""
    loader = ConfigLoader(temp_config_file, debounce_seconds=0.1)
    
    # Start watching
    loader.start_watching()
    
    try:
        initial_config = loader.get_config()
        
        # Modify the file
        new_config = {
            "watched_server": {
                "url": "http://localhost:8002/mcp",
                "health_url": "http://localhost:8002/health",
                "description": "Watched Server",
                "enabled": True
            }
        }
        
        with open(temp_config_file, 'w') as f:
            yaml.safe_dump(new_config, f)
        
        # Wait for debounced reload
        time.sleep(0.2)
        
        updated_config = loader.get_config()
        assert updated_config != initial_config
        assert "watched_server" in updated_config
        
    finally:
        loader.stop_watching()


def test_config_loader_debouncing(temp_config_file):
    """Test that rapid file changes are debounced."""
    loader = ConfigLoader(temp_config_file, debounce_seconds=0.2)
    loader.start_watching()
    
    try:
        initial_timestamp = loader.get_load_timestamp()
        
        # Make multiple rapid changes
        for i in range(3):
            config = {
                f"server_{i}": {
                    "url": f"http://localhost:{8000+i}/mcp",
                    "health_url": f"http://localhost:{8000+i}/health",
                    "description": f"Server {i}",
                    "enabled": True
                }
            }
            
            with open(temp_config_file, 'w') as f:
                yaml.safe_dump(config, f)
            
            time.sleep(0.05)  # Rapid changes
        
        # Wait for debounced reload (should only happen once)
        time.sleep(0.3)
        
        final_config = loader.get_config()
        final_timestamp = loader.get_load_timestamp()
        
        # Should have the last config
        assert "server_2" in final_config
        assert final_timestamp > initial_timestamp
        
    finally:
        loader.stop_watching()


def test_load_mcp_yaml_integration():
    """Test the global MCP YAML loading function."""
    # Mock the config loader to avoid filesystem dependencies
    mock_config = {
        "gmail": {
            "url": "http://localhost:8002/mcp",
            "health_url": "http://localhost:8002/health",
            "description": "Gmail MCP Server",
            "enabled": True
        },
        "disabled_server": {
            "url": "http://localhost:8003/mcp",
            "health_url": "http://localhost:8003/health",
            "description": "Disabled Server",
            "enabled": False
        }
    }
    
    with patch('backend.utils.config_loader.get_mcp_config_loader') as mock_loader:
        mock_loader.return_value.get_config.return_value = mock_config
        
        config = load_mcp_yaml()
        assert config == mock_config


def test_save_mcp_yaml_integration():
    """Test the global MCP YAML saving function."""
    new_config = {
        "new_server": {
            "url": "http://localhost:8004/mcp",
            "health_url": "http://localhost:8004/health",
            "description": "New Server",
            "enabled": True
        }
    }
    
    with patch('backend.utils.config_loader.get_mcp_config_loader') as mock_loader:
        save_mcp_yaml(new_config)
        mock_loader.return_value.save_config.assert_called_once_with(new_config)


def test_config_yaml_toggle():
    """Test toggling enabled flag in YAML config."""
    initial_config = {
        "gmail": {
            "url": "http://localhost:8002/mcp",
            "health_url": "http://localhost:8002/health",
            "description": "Gmail MCP Server",
            "enabled": True
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.safe_dump(initial_config, f)
        temp_path = Path(f.name)
    
    try:
        loader = ConfigLoader(temp_path)
        
        # Toggle enabled flag
        config = loader.get_config()
        config["gmail"]["enabled"] = False
        loader.save_config(config)
        
        # Verify the change
        updated_config = loader.get_config()
        assert updated_config["gmail"]["enabled"] is False
        
        # Toggle back
        config["gmail"]["enabled"] = True
        loader.save_config(config)
        
        final_config = loader.get_config()
        assert final_config["gmail"]["enabled"] is True
        
    finally:
        if temp_path.exists():
            temp_path.unlink() 