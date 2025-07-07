import os
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any, Dict, List
from pydantic import SecretStr

from utils.config_registry import get_config


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"], env_file_encoding="utf-8", extra="ignore"
    )

    # Redis Configuration (for Celery and caching)
    REDIS_URL: str = "redis://localhost:6379"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # Google Generative AI Settings (using API Key)
    GOOGLE_API_KEY: Optional[SecretStr] = None
    GOOGLE_MODEL_NAME: Optional[str] = None  # e.g., gemini-pro, gemini-1.5-flash

    # PostgreSQL Database Configuration
    POSTGRES_DB: str = "nova_kanban"
    POSTGRES_USER: str = "nova"
    POSTGRES_PASSWORD: str = "nova_dev_password"
    POSTGRES_PORT: int = 5432
    POSTGRES_HOST: str = "localhost"
    
    # Database Configuration (constructed from PostgreSQL variables)
    DATABASE_URL: Optional[str] = None  # PostgreSQL connection string for checkpointer
    
    # Neo4j Configuration (for Graphiti Memory)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"
    
    # Memory Configuration
    MEMORY_GROUP_ID: str = "nova"
    MEMORY_SEARCH_LIMIT: int = 10
    
    # LangSmith Configuration
    LANGCHAIN_TRACING_V2: Optional[str] = "true"
    LANGCHAIN_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[SecretStr] = None
    LANGCHAIN_PROJECT: Optional[str] = None

    # Agent Loop Settings
    AGENT_POLLING_INTERVAL_SECONDS: int = 30
    AGENT_ERROR_RETRY_INTERVAL_SECONDS: int = 60
    
    # Service Ports
    CHAT_AGENT_PORT: int = 8000
    CORE_AGENT_PORT: int = 8001
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True  # Set to False for human-readable console output during development
    
    # File Logging Configuration
    LOG_FILE_ENABLED: bool = False  # Set to True to enable file logging with rotation
    LOG_FILE_PATH: Optional[str] = None  # Path to log file (defaults to ./logs/{service_name}.log)
    LOG_FILE_MAX_SIZE_MB: int = 10  # Maximum size in MB before rotation
    LOG_FILE_BACKUP_COUNT: int = 5  # Number of backup files to keep

    # Email Integration Configuration
    EMAIL_ENABLED: bool = True  # Master toggle for email processing
    EMAIL_CREATE_TASKS: bool = True  # Whether to create tasks from emails
    EMAIL_MAX_PER_FETCH: int = 10  # Maximum emails to process per batch
    EMAIL_LABEL_FILTER: str = "INBOX"  # Email label to filter emails
    EMAIL_POLL_INTERVAL: int = 300  # Email polling interval in seconds (5 minutes)
    EMAIL_MCP_SERVER: str = "google-workspace"  # MCP server name for email operations

    @model_validator(mode="after")
    def compute_urls(self):
        """Compute DATABASE_URL and Celery URLs if not explicitly provided"""
        # Construct DATABASE_URL from PostgreSQL components if not explicitly set
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
        # Construct Celery URLs from REDIS_URL (already loaded from environment by pydantic-settings)
        self.CELERY_BROKER_URL = f"{self.REDIS_URL}/0"
        self.CELERY_RESULT_BACKEND = f"{self.REDIS_URL}/1"
        
        return self

    def _is_running_in_docker(self) -> bool:
        """Detect if running inside Docker container."""
        try:
            # Check if we're in the Docker environment by looking for specific indicators
            return (
                # Check if we're in the /app directory (Docker working directory)
                os.getcwd().startswith('/app') or
                # Check for Docker-specific environment variables
                os.path.exists('/.dockerenv') or
                # Check if running as the expected Docker user
                os.getenv('USER') == 'root'
            )
        except:
            return False

    def _adapt_mcp_url_for_environment(self, url: str) -> str:
        """Adapt MCP server URL based on runtime environment."""
        if self._is_running_in_docker():
            # In Docker: use internal network names
            return url
        else:
            # In WSL/host: convert Docker internal URLs to localhost
            url_mappings = {
                "http://nova-google-workspace-1:8000/mcp": "http://localhost:8002/mcp",
                "http://nova-feature-request-1:8000/mcp": "http://localhost:8003/mcp"
            }
            return url_mappings.get(url, url)

    @property
    def MCP_SERVERS(self) -> List[Dict[str, Any]]:
        """List of enabled MCP servers from YAML configuration with environment-aware URLs"""
        servers = []
        
        try:
            mcp_config = get_config("mcp_servers")
            
            for server_name, server_config in mcp_config.items():
                # Only include enabled servers
                if server_config.get("enabled", True):
                    original_url = server_config["url"]
                    adapted_url = self._adapt_mcp_url_for_environment(original_url)
                    
                    servers.append({
                        "name": server_name,
                        "url": adapted_url,
                        "description": server_config.get("description", f"{server_name} MCP Server")
                    })
        
        except Exception as e:
            # Log error but don't crash the application
            print(f"Warning: Failed to load MCP configuration: {e}")
        
        return servers


settings = Settings()
