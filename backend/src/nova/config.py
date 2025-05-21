from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any
from pydantic import SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env", env_file_encoding="utf-8", extra="ignore"
    )

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Gmail MCP Server individual components
    GMAIL_MCP_SERVER_HOST: str = "localhost"
    GMAIL_MCP_SERVER_PORT: int = 8001
    GMAIL_MCP_SERVER_URL: Optional[str] = None #
    
    # Google Generative AI Settings (using API Key)
    GOOGLE_API_KEY: Optional[SecretStr] = None
    GOOGLE_MODEL_NAME: Optional[str] = None  # e.g., gemini-pro, gemini-1.5-flash

    # LangSmith Configuration
    USE_LANGSMITH: bool = False
    LANGCHAIN_TRACING_V2: Optional[str] = "true"
    LANGCHAIN_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[SecretStr] = None
    LANGCHAIN_PROJECT: Optional[str] = None

    # Agent Loop Settings
    AGENT_POLLING_INTERVAL_SECONDS: int = 30
    AGENT_ERROR_RETRY_INTERVAL_SECONDS: int = 60

    @model_validator(mode='after')
    def assemble_urls_if_not_set(cls, values: Any) -> Any:
        if values.GMAIL_MCP_SERVER_URL is None:
            host = values.GMAIL_MCP_SERVER_HOST
            port = values.GMAIL_MCP_SERVER_PORT
            values.GMAIL_MCP_SERVER_URL = f"http://{host}:{port}/mcp/"
        return values

settings = Settings()
