import os
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import SecretStr


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

    # HuggingFace API Token
    HF_TOKEN: Optional[SecretStr] = None

    # OpenRouter API Key
    OPENROUTER_API_KEY: Optional[SecretStr] = None

    # PostgreSQL Database Configuration
    POSTGRES_DB: str = "nova_kanban"
    POSTGRES_USER: str = "nova"
    POSTGRES_PASSWORD: str = "nova_dev_password"
    POSTGRES_PORT: int = 5432
    POSTGRES_HOST: str = "localhost"  # Default to localhost, Docker compose overrides this

    # Database Configuration (constructed from PostgreSQL variables)
    DATABASE_URL: Optional[str] = None  # PostgreSQL connection string for LangChain checkpointer (no driver)
    SQLALCHEMY_DATABASE_URL: Optional[str] = None  # PostgreSQL connection string for SQLAlchemy (+asyncpg)

    # Neo4j Configuration (for Graphiti Memory)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"

    # Memory Configuration
    MEMORY_GROUP_ID: str = "nova"
    MEMORY_SEARCH_LIMIT: int = 10

    # Phoenix Observability Configuration (Self-Hosted)
    # Arize Phoenix for LLM tracing and observability
    PHOENIX_ENABLED: bool = True
    PHOENIX_HOST: str = "http://localhost:6006"
    PHOENIX_GRPC_PORT: int = 4317

    # Service Ports
    CHAT_AGENT_PORT: int = 8000
    CORE_AGENT_PORT: int = 8001

    # Frontend Configuration
    FRONTEND_BASE_URL: str = "http://localhost:3000"  # Base URL for Nova frontend chat links

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True  # Set to False for human-readable console output during development

    # File Logging Configuration
    LOG_FILE_ENABLED: bool = False  # Set to True to enable file logging with rotation
    LOG_FILE_PATH: Optional[str] = None  # Path to log file (defaults to ./logs/{service_name}.log)
    LOG_FILE_MAX_SIZE_MB: int = 10  # Maximum size in MB before rotation
    LOG_FILE_BACKUP_COUNT: int = 5  # Number of backup files to keep

    # Email Integration Configuration
    EMAIL_ENABLED: bool = True  # Master toggle for email processing (Tier 1: infrastructure available)

    # LiteLLM Configuration (Tier 2: Deployment Environment)
    # LiteLLM is the single source of truth for LLMs and MCP servers (ADR-011, ADR-015)
    LITELLM_BASE_URL: str = "http://localhost:4000"  # LiteLLM gateway URL
    LITELLM_MASTER_KEY: str = "sk-1234"  # Master key for LiteLLM API access

    # Default LLM Models (Tier 1: Development Defaults)
    # Single source of truth for model defaults - all other code imports from here
    DEFAULT_CHAT_MODEL: str = "gemini-3-flash-preview"
    DEFAULT_MEMORY_MODEL: str = "gemini-3-flash-preview"
    DEFAULT_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # External LLM API Configuration (Tier 2: Deployment Environment)
    # Generic OpenAI-compatible endpoint (e.g., LM Studio, Ollama, vLLM)
    LLM_API_BASE_URL: str = "http://localhost:1234"  # Default LM Studio port

    @model_validator(mode="after")
    def compute_urls(self):
        """Compute DATABASE_URL and Celery URLs if not explicitly provided"""
        # Construct DATABASE_URL for LangChain checkpointer (no driver)
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

        # Construct SQLALCHEMY_DATABASE_URL for SQLAlchemy (+asyncpg driver)
        if not self.SQLALCHEMY_DATABASE_URL:
            self.SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

        # Construct Celery URLs from REDIS_URL (already loaded from environment by pydantic-settings)
        self.CELERY_BROKER_URL = f"{self.REDIS_URL}/0"
        self.CELERY_RESULT_BACKEND = f"{self.REDIS_URL}/1"

        return self

    def _is_running_in_docker(self) -> bool:
        """Check if the application is running inside Docker."""
        return os.path.exists('/.dockerenv') or os.environ.get('DOCKER_ENV') == 'true'


settings = Settings()
