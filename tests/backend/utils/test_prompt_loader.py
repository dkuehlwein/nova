"""
Tests for prompt loader functionality.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from backend.utils.prompt_loader import PromptLoader, load_nova_system_prompt


class TestPromptLoader:
    """Test PromptLoader functionality."""
    
    def test_load_existing_prompt(self):
        """Test loading an existing prompt file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Test prompt content")
            temp_path = Path(f.name)
        
        try:
            loader = PromptLoader(temp_path)
            assert loader.get_prompt() == "Test prompt content"
            assert loader.get_load_timestamp() is not None
        finally:
            temp_path.unlink()
    
    def test_load_nonexistent_prompt(self):
        """Test loading a non-existent prompt file."""
        nonexistent_path = Path("/tmp/nonexistent_prompt.md")
        loader = PromptLoader(nonexistent_path)
        
        assert loader.get_prompt() == ""
        assert loader.get_load_timestamp() is None
    
    def test_reload_prompt(self):
        """Test manually reloading a prompt file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Initial content")
            temp_path = Path(f.name)
        
        try:
            loader = PromptLoader(temp_path)
            assert loader.get_prompt() == "Initial content"
            
            # Modify the file
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write("Updated content")
            
            # Manually reload
            loader.reload_prompt()
            assert loader.get_prompt() == "Updated content"
        finally:
            temp_path.unlink()
    
    def test_debounced_reload_scheduling(self):
        """Test that debounced reload is scheduled correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            loader = PromptLoader(temp_path, debounce_seconds=0.1)
            
            # Mock the reload method to track calls
            with patch.object(loader, '_load_prompt') as mock_load:
                loader._debounced_reload()
                
                # Should not be called immediately
                mock_load.assert_not_called()
                
                # Wait for debounce
                time.sleep(0.15)
                mock_load.assert_called_once()
        finally:
            temp_path.unlink()
    
    def test_watching_lifecycle(self):
        """Test starting and stopping file watching."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            loader = PromptLoader(temp_path)
            
            # Start watching
            loader.start_watching()
            assert loader._observer is not None
            assert loader._observer.is_alive()
            
            # Stop watching
            loader.stop_watching()
            assert loader._observer is None
        finally:
            temp_path.unlink()
    
    def test_multiple_start_watching(self):
        """Test that starting watching multiple times doesn't create multiple observers."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            loader = PromptLoader(temp_path)
            
            loader.start_watching()
            first_observer = loader._observer
            
            # Start watching again
            loader.start_watching()
            assert loader._observer is first_observer  # Should be the same observer
            
            # Cleanup
            loader.stop_watching()
        finally:
            temp_path.unlink()
    
    def test_publish_event_creation(self):
        """Test that prompt updated events are created correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            loader = PromptLoader(temp_path)
            
            # Mock the Redis publish and event creation functions
            with patch('backend.utils.redis_manager.publish') as mock_publish:
                with patch('backend.utils.prompt_loader.create_prompt_updated_event') as mock_create_event:
                    mock_event = Mock()
                    mock_event.id = "test-event-id"
                    mock_create_event.return_value = mock_event
                    
                    loader._publish_prompt_updated_event()
                    
                    mock_create_event.assert_called_once_with(
                        prompt_file=temp_path.name,
                        change_type="modified",
                        source="prompt-loader"
                    )
        finally:
            temp_path.unlink()


class TestGlobalPromptLoader:
    """Test global prompt loader functions."""
    
    def test_load_nova_system_prompt(self):
        """Test loading the Nova system prompt."""
        prompt = load_nova_system_prompt()
        
        # Should contain key Nova prompt elements
        assert "Nova" in prompt
        assert "Communication Guidelines" in prompt
        assert "Core Capabilities" in prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0
    
    def test_global_loader_singleton(self):
        """Test that the global loader is a singleton."""
        from backend.utils.prompt_loader import get_nova_prompt_loader
        
        loader1 = get_nova_prompt_loader()
        loader2 = get_nova_prompt_loader()
        
        assert loader1 is loader2  # Should be the same instance 