"""
Markdown configuration manager implementation.
Handles markdown-based configuration files (primarily for prompts).
"""

from pathlib import Path
from typing import Dict, Any

from utils.base_config_manager import BaseConfigManager, ValidationResult
from utils.logging import get_logger

logger = get_logger("markdown_config_manager")


class MarkdownConfigManager(BaseConfigManager[str]):
    """
    Markdown-based configuration manager.
    Handles text-based configuration files like system prompts.
    """
    
    def __init__(self, config_path: Path, config_name: str, 
                 default_config: str = None, debounce_seconds: float = 0.5):
        self.default_config = default_config
        super().__init__(config_path, config_name, debounce_seconds)
    
    def _load_config_data(self) -> str:
        """Load raw text data from file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(
                f"Failed to load markdown data: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            raise
    
    def _save_config_data(self, data: str) -> None:
        """Save text data to file."""
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as file:
                file.write(data)
                
        except Exception as e:
            logger.error(
                f"Failed to save markdown data: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "path": str(self.config_path),
                        "error": str(e)
                    }
                }
            )
            raise
    
    def _create_config_instance(self, data: str) -> str:
        """Return the raw text data."""
        return data or ""
    
    def _serialize_config(self, config: str) -> str:
        """Return the raw text data."""
        return config or ""
    
    def _validate_config_data(self, data: str) -> ValidationResult:
        """Validate markdown configuration data."""
        errors = []
        warnings = []
        details = {}
        
        try:
            # Basic validation checks
            if not isinstance(data, str):
                errors.append("Configuration must be a string")
                return ValidationResult(
                    valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )
            
            # Calculate statistics
            lines = data.split('\n')
            details.update({
                'character_count': len(data),
                'line_count': len(lines),
                'word_count': len(data.split()),
                'non_empty_lines': len([line for line in lines if line.strip()])
            })
            
            # Check for common issues
            if len(data.strip()) == 0:
                warnings.append("Configuration is empty")
            
            if len(data) > 50000:  # 50KB
                warnings.append(f"Large configuration file ({len(data)} characters)")
            
            # Check for potential template variables
            template_vars = []
            for line_num, line in enumerate(lines, 1):
                if '$' in line:
                    # Find template variables like $variable_name
                    import re
                    matches = re.findall(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', line)
                    for match in matches:
                        template_vars.append(f"${match} (line {line_num})")
            
            if template_vars:
                details['template_variables'] = template_vars
                details['template_variable_count'] = len(template_vars)
            
            # Check for common markdown issues
            if '{{' in data and '}}' in data:
                warnings.append("Found old-style template syntax {{}} - consider using $ syntax")
            
            # Check for extremely long lines
            long_lines = [i+1 for i, line in enumerate(lines) if len(line) > 200]
            if long_lines:
                warnings.append(f"Found {len(long_lines)} long lines (>200 chars)")
                details['long_lines'] = long_lines[:10]  # Show first 10
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            details['validation_error'] = str(e)
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def _create_default_config(self) -> None:
        """Create default configuration file."""
        if self.default_config is not None:
            logger.info(
                f"Creating default markdown config: {self.config_name}",
                extra={"data": {"path": str(self.config_path)}}
            )
            
            # Save default config
            self._save_config_data(self.default_config)
        else:
            # Create empty markdown file
            logger.info(
                f"Creating empty markdown config: {self.config_name}",
                extra={"data": {"path": str(self.config_path)}}
            )
            
            self._save_config_data("")
    
    def get_processed_config(self, **template_vars) -> str:
        """
        Get configuration with template variables substituted.
        Uses Python's string.Template for safe substitution.
        """
        from string import Template
        
        try:
            content = self.get_config()
            
            if template_vars:
                template = Template(content)
                content = template.safe_substitute(**template_vars)
            
            return content
            
        except Exception as e:
            logger.error(
                f"Failed to process template variables: {self.config_name}",
                exc_info=True,
                extra={
                    "data": {
                        "template_vars": list(template_vars.keys()),
                        "error": str(e)
                    }
                }
            )
            # Return unprocessed content as fallback
            return self.get_config()
    
    def get_template_variables(self) -> list[str]:
        """Get list of template variables found in the configuration."""
        import re
        
        content = self.get_config()
        matches = re.findall(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', content)
        return list(set(matches))  # Remove duplicates 